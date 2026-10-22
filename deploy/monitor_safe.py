"""Read-only probes. Only generic check IDs leave this host."""

import datetime
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=30).strip()


def fresh(path, now, max_age):
    data = json.loads(path.read_text())
    require(0 <= now - float(data["verified_at"]) <= max_age, "Stale backup")


def disk_ok(path):
    disk = shutil.disk_usage(path)
    require(disk.used / disk.total < 0.8 and disk.free > 5 * 1024**3, "Disk pressure")


def memory_ok():
    mem = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    require(mem["MemAvailable"] > max(1024**3, 0.15 * mem["MemTotal"]), "Memory pressure")


def queue_ok(sqs, cw, url, now, max_backlog=100, max_age=600):
    keys = [
        "ApproximateNumberOfMessages",
        "ApproximateNumberOfMessagesNotVisible",
        "ApproximateNumberOfMessagesDelayed",
    ]
    attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=keys)["Attributes"]
    total = sum(int(attrs[k]) for k in keys)
    require(total <= max_backlog, "Queue backlog")
    end = datetime.datetime.fromtimestamp(now, datetime.UTC)
    points = cw.get_metric_statistics(
        Namespace="AWS/SQS",
        MetricName="ApproximateAgeOfOldestMessage",
        Dimensions=[{"Name": "QueueName", "Value": url.rstrip("/").split("/")[-1]}],
        StartTime=end - datetime.timedelta(minutes=10),
        EndTime=end,
        Period=60,
        Statistics=["Maximum"],
    )["Datapoints"]
    recent = [p for p in points if 0 <= now - p["Timestamp"].timestamp() <= 300]
    require(not total or bool(recent), "Queue age unavailable")
    require(not recent or max(p["Maximum"] for p in recent) <= max_age, "Queue age")


def notify(issues, state, now, publish):
    previous = state.get("delivered_issues", [])
    due = issues != previous or (bool(issues) and now - state.get("sent_at", 0) >= 21600)
    if not due:
        return state, True
    if publish is None:
        return state, False
    publish(
        "ENTER operations alert" if issues else "ENTER operations recovery",
        "Checks requiring attention: " + ", ".join(issues)
        if issues
        else "Previously reported checks cleared. Failed-job window is one hour; "
        "this does not mean historical failures were repaired.",
    )
    return {"delivered_issues": issues, "sent_at": now}, True


def main():
    os.umask(0o077)
    now = time.time()
    path = Path(os.environ["ENTER_MONITOR_STATE_FILE"])
    require(path.is_absolute() and not path.is_symlink(), "Unsafe state path")
    require(
        path.parent.is_dir()
        and not path.parent.is_symlink()
        and path.parent.stat().st_mode & 0o077 == 0,
        "Unsafe state directory",
    )
    state = json.loads(path.read_text()) if path.exists() else {}
    issues = []

    def probe(name, action):
        try:
            action()
        except Exception:
            issues.append(name)

    base = Path(os.environ["ENTER_BACKUP_STATE_FILE"])
    for kind, age in [("hourly", 7200), ("daily", 93600), ("recovery", 35 * 86400)]:
        probe(
            "backup_" + kind,
            lambda k=kind, a=age: fresh(base.with_name(base.stem + "-" + k + base.suffix), now, a),
        )
    for unit in ("enter-backup.service", "enter-backup-daily.service", "enter-recovery.service"):
        probe(
            unit,
            lambda u=unit: require(
                command(["systemctl", "show", u, "--property=Result", "--value"]) == "success",
                "Backup service failed",
            ),
        )
    probe("database_disk", lambda: disk_ok("/srv/enter-data/postgres"))
    probe("temporary_disk", lambda: disk_ok("/tmp"))
    probe("memory", memory_ok)
    compose = [
        "docker",
        "compose",
        "--project-name",
        "recruiter",
        "--env-file",
        ".env.production",
        "-f",
        "compose.production.yaml",
        "exec",
        "-T",
    ]
    probe("postgres", lambda: command(compose + ["db", "pg_isready", "-U", "enter", "-d", "enter"]))
    probe("scanner", lambda: command(compose + ["scanner", "clamdscan", "--ping=3"]))
    for name, variable in [
        ("frontend_https", "ENTER_FRONTEND_URL"),
        ("api_https", "ENTER_HTTPS_URL"),
    ]:

        def https(v=variable):
            url = os.environ[v]
            require(url.startswith("https://"), "HTTPS required")
            require(
                command(
                    [
                        "curl",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        "15",
                        "--output",
                        "/dev/null",
                        "--write-out",
                        "%{http_code}",
                        url,
                    ]
                )
                == "200",
                "HTTPS unavailable",
            )

        probe(name, https)
    code = (
        "from datetime import timedelta; from django.utils import timezone; "
        "from talent.models import ResumeProcessingJob,FileCleanupJob; "
        "from talent.worker_runtime import worker_available; "
        "from django.conf import settings; import json; n=timezone.now(); "
        "print(json.dumps(dict(worker=worker_available(), "
        'overdue=ResumeProcessingJob.objects.filter(state__in=["queued","processing"],'
        "created_at__lt=n-timedelta(seconds=settings.RESUME_QUEUE_ALERT_SECONDS)).exists(),"
        'recent_failed=ResumeProcessingJob.objects.filter(state="failed",'
        "updated_at__gte=n-timedelta(hours=1)).exists(),"
        "cleanup=FileCleanupJob.objects.filter(created_at__lt=n-timedelta(hours=24)).exists())))"
    )

    def jobs():
        report = json.loads(
            command(compose + ["backend", "python", "manage.py", "shell", "-c", code]).splitlines()[
                -1
            ]
        )
        for key in ("overdue", "recent_failed", "cleanup"):
            if report[key]:
                issues.append("jobs_" + key)
        require(report["worker"], "Worker unavailable")

    probe("worker_or_job_probe", jobs)
    publish = None
    try:
        import boto3
        from botocore.config import Config

        session = boto3.Session(region_name="ap-southeast-2")
        require(session.get_credentials().method == "iam-role", "Instance role required")
        config = Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 1})
        require(
            session.client("sts", config=config).get_caller_identity()["Account"] == "431988153216",
            "Wrong AWS account",
        )
        sqs = session.client("sqs", config=config)
        cw = session.client("cloudwatch", config=config)
        for name, variable, limit in [
            ("queue", "ENTER_SQS_URL", 100),
            ("dead_letter_queue", "ENTER_DLQ_URL", 0),
        ]:

            def queue(v=variable, maximum=limit):
                url = os.environ[v]
                require(
                    url.startswith("https://sqs.ap-southeast-2.amazonaws.com/431988153216/"),
                    "Unreviewed queue",
                )
                queue_ok(sqs, cw, url, now, max_backlog=maximum)

            probe(name, queue)
        topic = os.environ.get("ENTER_ALERT_TOPIC_ARN", "")
        if topic:
            require(topic.startswith("arn:aws:sns:ap-southeast-2:431988153216:"), "Wrong topic")
            sns = session.client("sns", config=config)

            def publish(subject, message):
                return sns.publish(TopicArn=topic, Subject=subject, Message=message)
    except Exception:
        issues.append("aws_monitor_configuration")
    try:
        state, delivered = notify(sorted(set(issues)), state, now, publish)
    except Exception:
        delivered = False
    pending = path.with_name(path.name + "." + uuid.uuid4().hex)
    with pending.open("x") as f:
        json.dump(state, f)
    os.replace(pending, path)
    delivery = "unconfigured" if publish is None else ("ok" if delivered else "failed")
    print(json.dumps({"failed_checks": sorted(set(issues)), "alert_delivery": delivery}))
    return 2 if not delivered or publish is None else (1 if issues else 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("MONITOR_FAILED: private configuration/state/probe failure; delivery not confirmed")
        raise SystemExit(2) from None
