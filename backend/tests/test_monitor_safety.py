"""Synthetic operations checks; no AWS, Docker, secrets or candidate records."""

import ast
import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "monitor_safe.py"


@pytest.fixture(params=[0, 2])
def monitor(request):
    module = SimpleNamespace()
    exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec", optimize=request.param), module.__dict__)
    return module


def test_alert_delivery_dedup_and_recovery(monitor):
    calls = []

    def publish(*args):
        calls.append(args)

    state, ok = monitor.notify(["disk"], {}, 100, publish)
    assert ok and len(calls) == 1
    same, ok = monitor.notify(["disk"], state, 200, publish)
    assert ok and same == state and len(calls) == 1
    same, ok = monitor.notify([], state, 300, None)
    assert not ok and same == state
    recovered, ok = monitor.notify([], state, 300, publish)
    assert ok and recovered["delivered_issues"] == [] and len(calls) == 2
    assert "recovery" in calls[-1][0]


def test_delivery_failure_not_acknowledged(monitor):
    state = {}

    def fail(*args):
        raise RuntimeError("synthetic delivery failure")

    with pytest.raises(RuntimeError):
        monitor.notify(["queue"], state, 100, fail)
    assert state == {}
    assert monitor.notify(["queue"], state, 100, None) == ({}, False)


@pytest.mark.parametrize("age", [-1, 7201, None])
def test_backup_stale_missing_and_future(monitor, tmp_path, age):
    path = tmp_path / "marker.json"
    if age is not None:
        path.write_text(json.dumps({"verified_at": 10000 - age}))
    with pytest.raises((RuntimeError, FileNotFoundError)):
        monitor.fresh(path, 10000, 7200)


def test_memory_and_disk_pressure(monitor, monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda p: "MemTotal: 8000000 kB\nMemAvailable: 1 kB")
    with pytest.raises(RuntimeError):
        monitor.memory_ok()
    monkeypatch.setattr(
        monitor.shutil,
        "disk_usage",
        lambda p: SimpleNamespace(total=10 * 1024**3, used=9 * 1024**3, free=1024**3),
    )
    with pytest.raises(RuntimeError):
        monitor.disk_ok("/synthetic")


@pytest.mark.parametrize(
    "total,age,limit,passes",
    [
        (0, None, 100, True),
        (1, None, 100, False),
        (101, 1, 100, False),
        (1, 601, 100, False),
        (1, 10, 100, True),
        (1, 10, 0, False),
    ],
)
def test_queue_thresholds(monitor, total, age, limit, passes):
    sqs = SimpleNamespace(
        get_queue_attributes=lambda **kw: {
            "Attributes": {
                "ApproximateNumberOfMessages": str(total),
                "ApproximateNumberOfMessagesNotVisible": "0",
                "ApproximateNumberOfMessagesDelayed": "0",
            }
        }
    )
    points = (
        []
        if age is None
        else [{"Timestamp": datetime.datetime.fromtimestamp(1000, datetime.UTC), "Maximum": age}]
    )
    cw = SimpleNamespace(get_metric_statistics=lambda **kw: {"Datapoints": points})
    if passes:
        monitor.queue_ok(sqs, cw, "synthetic", 1000, max_backlog=limit)
    else:
        with pytest.raises(RuntimeError):
            monitor.queue_ok(sqs, cw, "synthetic", 1000, max_backlog=limit)


def test_no_optimization_sensitive_asserts():
    assert not any(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(SCRIPT.read_text())))


def test_retention_prefixes_only():
    config = json.loads((SCRIPT.parent / "backup-retention.proposed.json").read_text())
    assert [(r["Filter"]["Prefix"], r["Expiration"]["Days"]) for r in config["Rules"]] == [
        ("postgres/hourly/", 7),
        ("postgres/daily/", 30),
    ]


def test_unit_templates_and_independent_schedules():
    import configparser

    for name in ("enter-backup", "enter-backup-daily", "enter-monitor", "enter-recovery"):
        unit = configparser.ConfigParser(interpolation=None, strict=False)
        unit.read(SCRIPT.parent / (name + ".service"))
        assert "${ENTER_OPS_DIR}/" in unit["Service"]["ExecStart"]
        assert unit["Service"]["Type"] == "oneshot"
        timer = configparser.ConfigParser(interpolation=None)
        timer.read(SCRIPT.parent / (name + ".timer"))
        assert timer["Install"]["WantedBy"] == "timers.target"
    daily = (SCRIPT.parent / "enter-backup-daily.service").read_text()
    assert "ENTER_BACKUP_CLASS=daily" in daily
    assert "OnCalendar=*-*-01 03:30:00 UTC" in (SCRIPT.parent / "enter-recovery.timer").read_text()


@pytest.mark.parametrize(
    "failed", [None, "delivery", "sns_missing", "old_daily", "jobs", "https", "tls", "url"]
)
def test_monitor_orchestration(monitor, monkeypatch, tmp_path, capsys, failed):
    import boto3

    tmp_path.chmod(0o700)
    now = 10000000
    monkeypatch.setattr(monitor.time, "time", lambda: now)
    for key, value in {
        "ENTER_MONITOR_STATE_FILE": str(tmp_path / "monitor.json"),
        "ENTER_BACKUP_STATE_FILE": str(tmp_path / "backup.json"),
        "ENTER_FRONTEND_URL": "https://example.invalid/"
        if failed == "url"
        else "https://enter.careers/",
        "ENTER_HTTPS_URL": "https://enter.careers/api/v1/health/ready/",
        "ENTER_SQS_URL": "https://sqs.ap-southeast-2.amazonaws.com/431988153216/main",
        "ENTER_DLQ_URL": "https://sqs.ap-southeast-2.amazonaws.com/431988153216/dlq",
        "ENTER_ALERT_TOPIC_ARN": ""
        if failed == "sns_missing"
        else "arn:aws:sns:ap-southeast-2:431988153216:operator",
    }.items():
        monkeypatch.setenv(key, value)
    for kind in ("hourly", "daily", "recovery"):
        timestamp = 0 if failed == "old_daily" and kind == "daily" else now
        (tmp_path / f"backup-{kind}.json").write_text(json.dumps({"verified_at": timestamp}))
    monkeypatch.setattr(monitor, "disk_ok", lambda p: None)
    monkeypatch.setattr(monitor, "memory_ok", lambda: None)
    seen = []

    def command(args):
        seen.append(args)
        if "shell" in args:
            return json.dumps(
                dict(
                    worker=True,
                    overdue=False,
                    cleanup=False,
                    recent_failed=failed in ("jobs", "delivery", "sns_missing"),
                )
            )
        if "curl" in args:
            assert args[args.index("--noproxy") + 1] == "*"
            assert args[args.index("--resolve") + 1] == "enter.careers:443:127.0.0.1"
            assert args[-1].startswith("https://enter.careers/")
            assert not set(args) & {"-k", "--insecure", "-L", "--location"}
            if failed == "tls":
                raise RuntimeError("synthetic certificate validation failure")
            return "503" if failed == "https" else "200"
        return "success"

    monkeypatch.setattr(monitor, "command", command)
    messages = []

    def publish(**kw):
        if failed == "delivery":
            raise RuntimeError("synthetic")
        messages.append(kw)
        return {"MessageId": "synthetic"}

    sqs = SimpleNamespace(
        get_queue_attributes=lambda **kw: {"Attributes": {k: "0" for k in kw["AttributeNames"]}}
    )
    clients = {
        "sts": SimpleNamespace(get_caller_identity=lambda: {"Account": "431988153216"}),
        "sqs": sqs,
        "cloudwatch": SimpleNamespace(get_metric_statistics=lambda **kw: {"Datapoints": []}),
        "sns": SimpleNamespace(publish=publish),
    }
    monkeypatch.setattr(
        boto3,
        "Session",
        lambda **kw: SimpleNamespace(
            get_credentials=lambda: SimpleNamespace(method="iam-role"),
            client=lambda name, **kw: clients[name],
        ),
    )
    expected = 0 if failed is None else (2 if failed in ("delivery", "sns_missing") else 1)
    assert monitor.main() == expected
    output = json.loads(capsys.readouterr().out)
    assert ("backup_daily" in output["failed_checks"]) == (failed == "old_daily")
    assert ("frontend_https" in output["failed_checks"]) == (failed in ("https", "tls", "url"))
    assert ("api_https" in output["failed_checks"]) == (failed in ("https", "tls"))
    state = json.loads((tmp_path / "monitor.json").read_text())
    if failed in ("delivery", "sns_missing"):
        assert state == {}
    else:
        assert monitor.main() == expected
        assert len(messages) == (0 if failed is None else 1)
    shell_code = next(c[-1] for c in seen if "shell" in c)
    assert "updated_at__gte=n-timedelta(hours=1)" in shell_code
    assert ".delete(" not in shell_code and ".save(" not in shell_code
