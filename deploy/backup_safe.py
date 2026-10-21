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


class BackupSafetyError(RuntimeError):
    """A safe, non-sensitive failure; never embed provider responses or SQL."""


def require(condition, message):
    if not condition:
        raise BackupSafetyError(message)


def output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=30).strip()


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
    require(bucket == "enter-staging-backups-2021", "Unreviewed backup bucket")
    require(os.environ["ENTER_AWS_ACCOUNT"] == "431988153216", "Unreviewed account")
    require(os.environ["ENTER_INSTANCE_ID"] == "i-08f84202dbb6b4cce", "Unreviewed instance")
    require(os.environ["ENTER_AWS_REGION"] == "ap-southeast-2", "Unreviewed region")
    imds_token = (
        urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/api/token",
                method="PUT",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
            ),
            timeout=5,
        )
        .read()
        .decode()
    )
    identity = json.load(
        urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers={"X-aws-ec2-metadata-token": imds_token},
            ),
            timeout=5,
        )
    )
    require(
        identity["accountId"] == os.environ["ENTER_AWS_ACCOUNT"]
        and identity["instanceId"] == os.environ["ENTER_INSTANCE_ID"]
        and identity["region"] == os.environ["ENTER_AWS_REGION"],
        "Backup safety check failed at check 79",
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
    db_info = json.loads(output(docker + ["inspect", "recruiter-db-1"]))[0]
    require(db_info["Name"] == "/recruiter-db-1", "Wrong database container")
    require(
        any(
            m.get("Source") == "/srv/enter-data/postgres"
            and m.get("Destination") == "/var/lib/postgresql/data"
            for m in db_info["Mounts"]
        ),
        "Unreviewed live database storage",
    )
    require(
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
                "SELECT current_database();",
            ]
        )
        == "enter",
        "Wrong database",
    )
    before = inspect_live()
    require(
        all(x["running"] and x["health"] in (None, "healthy") for x in before.values()),
        "Backup safety check failed at check 104",
    )
    mem = {
        line.split(":")[0]: int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
    }
    require(mem["MemAvailable"] > 3 * 1024**3, "Backup safety check failed at check 109")
    require(shutil.disk_usage("/tmp").free > 5 * 1024**3, "Backup safety check failed at check 110")
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
    require(size < 50 * 1024**2, "Backup safety check failed at check 127")
    image = output(docker + ["inspect", "recruiter-db-1", "--format", "{{.Image}}"])
    output(docker + ["image", "inspect", image])
    import boto3

    session = boto3.Session(region_name=os.environ["ENTER_AWS_REGION"])
    require(
        session.get_credentials().method == "iam-role", "Backup safety check failed at check 133"
    )
    require(
        session.client("sts").get_caller_identity()["Account"] == os.environ["ENTER_AWS_ACCOUNT"],
        "Backup safety check failed at check 134",
    )
    s3 = session.client("s3")
    require(
        s3.get_bucket_location(Bucket=bucket)["LocationConstraint"]
        == os.environ["ENTER_AWS_REGION"],
        "Backup safety check failed at check 136",
    )
    # User verified in AWS Console: Block ALL public access ON, no bucket policy.
    # EC2 role cannot read these settings; do not broaden IAM permissions.
    require(
        os.environ.get("ENTER_BACKUP_SECURITY_REVIEWED") == "true",
        "Backup safety check failed at check 142",
    )
    model = json.loads(output(["aws", "s3api", "put-object", "--generate-cli-skeleton", "input"]))
    require(
        "IfNoneMatch" in model and "ChecksumSHA256" in model,
        "Backup safety check failed at check 144",
    )
    token = uuid.uuid4().hex
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    backup_class = os.environ.get("ENTER_BACKUP_CLASS", "hourly")
    require(backup_class in ("hourly", "daily"), "Backup safety check failed at check 148")
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
    head = s3.head_object(
        Bucket=bucket,
        Key=key,
        ChecksumMode="ENABLED",
        ExpectedBucketOwner=os.environ["ENTER_AWS_ACCOUNT"],
    )
    require(head["ContentLength"] == dump.stat().st_size, "Backup safety check failed at check 205")
    require(head["ServerSideEncryption"] == "AES256", "Backup safety check failed at check 206")
    require(head["ChecksumSHA256"] == checksum, "Backup safety check failed at check 207")
    response = s3.get_object(
        Bucket=bucket, Key=key, ExpectedBucketOwner=os.environ["ENTER_AWS_ACCOUNT"]
    )
    with downloaded.open("xb") as f:
        for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
            f.write(chunk)
    response["Body"].close()
    require(
        hashlib.sha256(downloaded.read_bytes()).digest() == digest,
        "Backup safety check failed at check 213",
    )
    print("CHECKSUM_READBACK_PASS", "BYTES", dump.stat().st_size, flush=True)
    stage = "isolated restore preflight"
    require(inspect_live() == before, "Backup safety check failed at check 216")
    require(shutil.disk_usage("/tmp").free > 5 * 1024**3, "Backup safety check failed at check 217")
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    require(available > 3 * 1024**3, "Backup safety check failed at check 223")
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
    require(
        all(
            m.get("Type") == "tmpfs" and m.get("Destination") == "/var/lib/postgresql/data"
            for m in info["Mounts"]
        ),
        "Restore has unexpected mounts",
    )
    require(
        info["HostConfig"]["Tmpfs"].get("/var/lib/postgresql/data") == "rw,nosuid,noexec,size=384m",
        "Restore tmpfs is not bounded",
    )
    require(info["HostConfig"]["NanoCpus"] == 500000000, "Restore CPU is not bounded")
    require(info["HostConfig"]["NetworkMode"] == "none", "Backup safety check failed at check 263")
    require(not info["HostConfig"].get("PortBindings"), "Backup safety check failed at check 264")
    require(
        all("/srv/enter-data" not in m.get("Source", "") for m in info["Mounts"]),
        "Backup safety check failed at check 265",
    )
    require(
        info["HostConfig"]["Memory"] == 768 * 1024**2, "Backup safety check failed at check 266"
    )
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

    require(
        int(sql("SELECT count(*) FROM django_migrations;")) > 0,
        "Backup safety check failed at check 322",
    )
    require(
        int(sql("SELECT count(*) FROM pg_tables WHERE schemaname='public';")) > 0,
        "Backup safety check failed at check 323",
    )
    require(
        sql("SELECT count(*) FROM pg_index WHERE NOT indisvalid;") == "0",
        "Backup safety check failed at check 324",
    )
    run(
        docker
        + ["exec", scratch, "pg_amcheck", "-U", "enter", "--database=" + db, "--install-missing"]
    )
    require(inspect_live() == before, "Backup safety check failed at check 329")
    print(
        "ISOLATED_RESTORE_PASS", "LIVE_CONTAINER_IDENTITIES_AND_START_TIMES_UNCHANGED", flush=True
    )
    stage = "verify no unexpected live database writes"
    time.sleep(2)
    print("CONCURRENT_BUSINESS_ACTIVITY", activity() != activity_before, flush=True)
    # pg_dump provides a consistent snapshot despite concurrent application writes.
    # Do not stop intake or mutate live data to manufacture a quiet backup window.
    stage = "cleanup verified scratch resources"
    state = Path(os.environ["ENTER_BACKUP_STATE_FILE"])
    require(state.is_absolute() and not state.is_symlink(), "Unsafe backup marker")
    require(state.parent.is_dir() and not state.parent.is_symlink(), "Unsafe marker directory")
    require(state.parent.stat().st_mode & 0o077 == 0, "Marker directory must be private")
    require(scratch == "enter-restore-check-" + token, "Backup safety check failed at check 339")
    check = json.loads(output(docker + ["inspect", scratch]))[0]
    require(
        check["Config"]["Labels"].get("enter.backup-verification") == token,
        "Backup safety check failed at check 341",
    )
    run(docker + ["stop", "--time", "20", scratch])
    run(docker + ["rm", "-v", scratch])
    pending = state.with_name(state.name + "." + token)
    with pending.open("x") as marker:
        marker.write(
            json.dumps(
                {
                    "verified_at": time.time(),
                    "key": key,
                    "sha256": digest.hex(),
                    "bytes": head["ContentLength"],
                }
            )
        )
    os.replace(pending, state)
    for path in [dump, downloaded, work / "operation-errors.log"]:
        path.unlink()
    work.rmdir()
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
