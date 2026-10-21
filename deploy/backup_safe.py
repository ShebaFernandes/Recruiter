import base64
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

os.umask(0o077)
bucket = os.environ["ENTER_BACKUP_BUCKET"]
live = [
    "recruiter-db-1",
    "recruiter-backend-1",
    "recruiter-worker-1",
    "recruiter-scanner-1",
    "recruiter-frontend-1",
    "recruiter-edge-1",
]
docker = ["docker"]
stage = "preflight"
work = None
scratch = None


def output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def inspect_live():
    data = json.loads(output(docker + ["inspect"] + live))
    return {
        d["Name"]: {
            "id": d["Id"],
            "started": d["State"]["StartedAt"],
            "running": d["State"]["Running"],
            "health": d["State"].get("Health", {}).get("Status"),
        }
        for d in data
    }


def run(args, source=None, destination=None):
    with (work / "operation-errors.log").open("ab") as errors:
        subprocess.run(
            args,
            stdin=source,
            stdout=destination or subprocess.DEVNULL,
            stderr=errors,
            check=True,
            timeout=300,
        )


try:
    imds_token = (
        urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/api/token",
                method="PUT",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            )
        )
        .read()
        .decode()
    )
    identity = json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers={"X-aws-ec2-metadata-token": imds_token},
            )
        )
    )
    assert (
        identity["accountId"] == os.environ["ENTER_AWS_ACCOUNT"]
        and identity["instanceId"] == os.environ["ENTER_INSTANCE_ID"]
        and identity["region"] == os.environ["ENTER_AWS_REGION"]
    )

    def activity():
        return output(
            docker
            + [
                "exec",
                "recruiter-db-1",
                "psql",
                "-U",
                "enter",
                "-d",
                "enter",
                "-Atc",
                "SELECT relname,n_tup_ins,n_tup_upd,n_tup_del FROM pg_stat_user_tables "
                "WHERE relname <> 'talent_workerheartbeat' ORDER BY relname;",
            ]
        )

    activity_before = activity()
    before = inspect_live()
    assert all(x["running"] and x["health"] in (None, "healthy") for x in before.values())
    mem = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    assert mem["MemAvailable"] > 3 * 1024**3
    assert shutil.disk_usage("/tmp").free > 5 * 1024**3
    size = int(
        output(
            docker
            + [
                "exec",
                "recruiter-db-1",
                "psql",
                "-U",
                "enter",
                "-d",
                "enter",
                "-Atc",
                "SELECT pg_database_size(current_database());",
            ]
        )
    )
    assert size < 50 * 1024**2
    image = output(docker + ["inspect", "recruiter-db-1", "--format", "{{.Image}}"])
    output(docker + ["image", "inspect", image])
    import boto3

    session = boto3.Session(region_name=os.environ["ENTER_AWS_REGION"])
    assert session.get_credentials().method == "iam-role"
    assert session.client("sts").get_caller_identity()["Account"] == os.environ["ENTER_AWS_ACCOUNT"]
    s3 = session.client("s3")
    assert (
        s3.get_bucket_location(Bucket=bucket)["LocationConstraint"]
        == os.environ["ENTER_AWS_REGION"]
    )
    # User verified in AWS Console: Block ALL public access ON, no bucket policy.
    # EC2 role cannot read these settings; do not broaden IAM permissions.
    assert os.environ.get("ENTER_BACKUP_SECURITY_REVIEWED") == "true"
    model = json.loads(output(["aws", "s3api", "put-object", "--generate-cli-skeleton", "input"]))
    assert "IfNoneMatch" in model and "ChecksumSHA256" in model
    token = uuid.uuid4().hex
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    backup_class = os.environ.get("ENTER_BACKUP_CLASS", "hourly")
    assert backup_class in ("hourly", "daily")
    key = "postgres/" + backup_class + "/" + stamp + "-" + token + ".dump"
    work = Path(tempfile.mkdtemp(prefix="enter-backup-verified-", dir="/tmp"))
    print("SECURE_WORK_DIRECTORY", work, flush=True)
    dump = work / "database.dump"
    downloaded = work / "verified-from-s3.dump"
    stage = "consistent pg_dump"
    with dump.open("xb") as f:
        run(
            docker
            + [
                "exec",
                "recruiter-db-1",
                "pg_dump",
                "-U",
                "enter",
                "-d",
                "enter",
                "--format=custom",
                "--no-owner",
                "--lock-wait-timeout=10s",
            ],
            destination=f,
        )
    with dump.open("rb") as f:
        run(docker + ["exec", "-i", "recruiter-db-1", "pg_restore", "--list"], source=f)
    digest = hashlib.sha256(dump.read_bytes()).digest()
    checksum = base64.b64encode(digest).decode()
    stage = "conditional encrypted S3 upload"
    run(
        [
            "aws",
            "s3api",
            "put-object",
            "--region",
            os.environ["ENTER_AWS_REGION"],
            "--expected-bucket-owner",
            os.environ["ENTER_AWS_ACCOUNT"],
            "--bucket",
            bucket,
            "--key",
            key,
            "--body",
            str(dump),
            "--if-none-match",
            "*",
            "--server-side-encryption",
            "AES256",
            "--checksum-algorithm",
            "SHA256",
            "--checksum-sha256",
            checksum,
        ]
    )
    print("UPLOADED", "s3://" + bucket + "/" + key, flush=True)
    stage = "S3 readback and checksum verification"
    head = s3.head_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    assert head["ContentLength"] == dump.stat().st_size
    assert head["ServerSideEncryption"] == "AES256"
    assert head["ChecksumSHA256"] == checksum
    response = s3.get_object(Bucket=bucket, Key=key)
    with downloaded.open("xb") as f:
        for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
            f.write(chunk)
    response["Body"].close()
    assert hashlib.sha256(downloaded.read_bytes()).digest() == digest
    print("CHECKSUM_READBACK_PASS", "BYTES", dump.stat().st_size, flush=True)
    stage = "isolated restore preflight"
    assert inspect_live() == before
    assert shutil.disk_usage("/tmp").free > 5 * 1024**3
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    assert available > 3 * 1024**3
    scratch = "enter-restore-check-" + token
    db = "restore_check_" + token
    stage = "start isolated scratch container"
    run(
        docker
        + [
            "run",
            "-d",
            "--pull=never",
            "--name",
            scratch,
            "--network=none",
            "--cpus=0.5",
            "--memory=768m",
            "--memory-swap=768m",
            "--pids-limit=128",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,nosuid,noexec,size=384m",
            "--label",
            "enter.backup-verification=" + token,
            "-e",
            "POSTGRES_USER=enter",
            "-e",
            "POSTGRES_DB=" + db,
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            image,
            "postgres",
            "-c",
            "listen_addresses=",
            "-c",
            "shared_buffers=32MB",
            "-c",
            "max_connections=10",
            "-c",
            "work_mem=2MB",
        ]
    )
    info = json.loads(output(docker + ["inspect", scratch]))[0]
    assert info["HostConfig"]["NetworkMode"] == "none"
    assert not info["HostConfig"].get("PortBindings")
    assert all("/srv/enter-data" not in m.get("Source", "") for m in info["Mounts"])
    assert info["HostConfig"]["Memory"] == 768 * 1024**2
    for _attempt in range(60):
        p = subprocess.run(
            docker + ["exec", scratch, "pg_isready", "-U", "enter", "-d", db],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if (
            p.returncode == 0
            and output(docker + ["exec", scratch, "cat", "/proc/1/comm"]) == "postgres"
        ):
            break
        time.sleep(1)
    else:
        raise RuntimeError("scratch readiness timed out")
    stage = "restore downloaded archive"
    with downloaded.open("rb") as f:
        run(
            docker
            + [
                "exec",
                "-i",
                scratch,
                "pg_restore",
                "-U",
                "enter",
                "-d",
                db,
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--single-transaction",
            ],
            source=f,
        )
    stage = "verify restored structure"

    def sql(query):
        return output(
            docker
            + [
                "exec",
                scratch,
                "psql",
                "-U",
                "enter",
                "-d",
                db,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                query,
            ]
        )

    assert int(sql("SELECT count(*) FROM django_migrations;")) > 0
    assert int(sql("SELECT count(*) FROM pg_tables WHERE schemaname='public';")) > 0
    assert sql("SELECT count(*) FROM pg_index WHERE NOT indisvalid;") == "0"
    run(
        docker
        + ["exec", scratch, "pg_amcheck", "-U", "enter", "--database=" + db, "--install-missing"]
    )
    assert inspect_live() == before
    print(
        "ISOLATED_RESTORE_PASS", "LIVE_CONTAINER_IDENTITIES_AND_START_TIMES_UNCHANGED", flush=True
    )
    stage = "verify no unexpected live database writes"
    time.sleep(2)
    print("CONCURRENT_BUSINESS_ACTIVITY", activity() != activity_before, flush=True)
    # pg_dump provides a consistent snapshot despite concurrent application writes.
    # Do not stop intake or mutate live data to manufacture a quiet backup window.
    stage = "cleanup verified scratch resources"
    assert scratch == "enter-restore-check-" + token
    check = json.loads(output(docker + ["inspect", scratch]))[0]
    assert check["Config"]["Labels"].get("enter.backup-verification") == token
    run(docker + ["stop", "--time", "20", scratch])
    run(docker + ["rm", "-v", scratch])
    for path in [dump, downloaded, work / "operation-errors.log"]:
        path.unlink()
    work.rmdir()
    state = Path(os.environ["ENTER_BACKUP_STATE_FILE"])
    pending = state.with_name(state.name + "." + token)
    pending.write_text(json.dumps({"verified_at": time.time(), "key": key}))
    os.replace(pending, state)
    print(
        json.dumps(
            {
                "backup": "PASS",
                "s3": "s3://" + bucket + "/" + key,
                "size_bytes": head["ContentLength"],
                "sha256": digest.hex(),
                "checksum": "PASS",
                "restore": "PASS",
                "temporary_resources": "removed",
                "live_containers_unchanged": inspect_live() == before,
            }
        ),
        flush=True,
    )
except Exception as exc:
    print("STOPPED_STAGE", stage, "ERROR_TYPE", type(exc).__name__, flush=True)
    print("RETAINED_SECURE_DIRECTORY", str(work) if work else "none", flush=True)
    print("SCRATCH_CONTAINER_IF_CREATED", scratch or "none", flush=True)
    raise SystemExit(1) from None
