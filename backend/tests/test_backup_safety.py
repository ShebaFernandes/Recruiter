"""Offline orchestration tests: no Docker, AWS, real database or credentials used."""

import ast
import base64
import hashlib
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import boto3
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "backup_safe.py"


@pytest.mark.parametrize("optimized", [0, 2])
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "target",
        "bucket",
        "database",
        "space",
        "dump",
        "collision",
        "encryption",
        "checksum",
        "readback",
        "network",
        "mount",
        "restore",
        "schema",
        "cleanup_label",
    ],
)
def test_backup_orchestration_fail_closed(monkeypatch, tmp_path, capsys, optimized, failure):
    import tempfile
    import urllib.request

    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)
    state = state_dir / "verified.json"
    for key, value in {
        "ENTER_BACKUP_BUCKET": "wrong" if failure == "bucket" else "enter-staging-backups-2021",
        "ENTER_AWS_ACCOUNT": "431988153216",
        "ENTER_INSTANCE_ID": "i-08f84202dbb6b4cce",
        "ENTER_AWS_REGION": "ap-southeast-2",
        "ENTER_BACKUP_SECURITY_REVIEWED": "true",
        "ENTER_BACKUP_STATE_FILE": str(state),
    }.items():
        monkeypatch.setenv(key, value)
    calls = []
    identity = {
        "accountId": "wrong" if failure == "target" else "431988153216",
        "instanceId": "i-08f84202dbb6b4cce",
        "region": "ap-southeast-2",
    }
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda r, **kw: io.BytesIO(
            b"token" if r.get_method() == "PUT" else json.dumps(identity).encode()
        ),
    )
    original_read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda p, *a, **kw: (
            "MemAvailable: 8000000 kB\n"
            if str(p) == "/proc/meminfo"
            else original_read(p, *a, **kw)
        ),
    )
    monkeypatch.setattr(
        "shutil.disk_usage",
        lambda p: SimpleNamespace(free=0 if failure == "space" else 10 * 1024**3),
    )
    original_temp = tempfile.mkdtemp
    monkeypatch.setattr(
        tempfile, "mkdtemp", lambda **kw: original_temp(prefix=kw["prefix"], dir=tmp_path)
    )
    monkeypatch.setattr("time.sleep", lambda _: None)
    digest = hashlib.sha256(b"SYNTHETIC ARCHIVE").digest()
    checksum = base64.b64encode(digest).decode()

    class Body(io.BytesIO):
        def iter_chunks(self, **kw):
            yield self.read()

    s3 = SimpleNamespace(
        get_bucket_location=lambda **kw: {"LocationConstraint": "ap-southeast-2"},
        head_object=lambda **kw: {
            "ContentLength": len(b"SYNTHETIC ARCHIVE"),
            "ServerSideEncryption": "none" if failure == "encryption" else "AES256",
            "ChecksumSHA256": "wrong" if failure == "checksum" else checksum,
        },
        get_object=lambda **kw: {
            "Body": Body(b"BAD" if failure == "readback" else b"SYNTHETIC ARCHIVE")
        },
    )
    session = SimpleNamespace(
        get_credentials=lambda: SimpleNamespace(method="iam-role"),
        client=lambda name: (
            s3
            if name == "s3"
            else SimpleNamespace(get_caller_identity=lambda: {"Account": "431988153216"})
        ),
    )
    monkeypatch.setattr(boto3, "Session", lambda **kw: session)

    def inspect(name):
        row = {
            "Name": "/" + name,
            "Id": name,
            "State": {"StartedAt": "unchanged", "Running": True, "Health": {"Status": "healthy"}},
            "Mounts": [
                {
                    "Source": "/srv/enter-data/postgres",
                    "Destination": "/var/lib/postgresql/data",
                    "Type": "bind",
                }
            ],
        }
        if name.startswith("enter-restore-check-"):
            row.update(
                {
                    "Mounts": [
                        {
                            "Type": "bind" if failure == "mount" else "tmpfs",
                            "Destination": "/var/lib/postgresql/data",
                        }
                    ],
                    "HostConfig": {
                        "NetworkMode": "bridge" if failure == "network" else "none",
                        "PortBindings": {},
                        "Memory": 768 * 1024**2,
                        "NanoCpus": 500000000,
                        "Tmpfs": {"/var/lib/postgresql/data": "rw,nosuid,noexec,size=384m"},
                    },
                    "Config": {
                        "Labels": {
                            "enter.backup-verification": "wrong"
                            if failure == "cleanup_label"
                            else name.removeprefix("enter-restore-check-")
                        }
                    },
                }
            )
        return row

    def output(args, **kw):
        calls.append(args)
        if args[:2] == ["aws", "s3api"]:
            return json.dumps({"IfNoneMatch": "", "ChecksumSHA256": ""})
        if args[:3] == ["docker", "image", "inspect"]:
            return "[]"
        if args[:2] == ["docker", "inspect"]:
            if "--format" in args:
                return "sha256:existing-image"
            return json.dumps([inspect(n) for n in args[2:]])
        if args[-1] == "/proc/1/comm":
            return "postgres"
        query = args[-1]
        if "pg_database_size" in query:
            return "10000"
        if "current_database" in query:
            return "wrong" if failure == "database" else "enter"
        if "NOT indisvalid" in query:
            return "1" if failure == "schema" else "0"
        if "count(*)" in query:
            return "3"
        return "stable counters"

    def run(args, **kw):
        calls.append(args)
        if "pg_dump" in args:
            if failure == "dump":
                raise subprocess.CalledProcessError(1, args)
            kw["stdout"].write(b"SYNTHETIC ARCHIVE")
        if "put-object" in args:
            assert args[args.index("--if-none-match") + 1] == "*"
            assert args[args.index("--server-side-encryption") + 1] == "AES256"
            if failure == "collision":
                raise subprocess.CalledProcessError(1, args)
        if "pg_restore" in args and "--list" not in args:
            assert args[3].startswith("enter-restore-check-")
            if failure == "restore":
                raise subprocess.CalledProcessError(1, args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "check_output", output)
    monkeypatch.setattr(subprocess, "run", run)
    code = compile(SCRIPT.read_text(), str(SCRIPT), "exec", optimize=optimized)
    if failure:
        with pytest.raises(SystemExit) as error:
            exec(code, {"__name__": "__main__"})
        assert error.value.code == 1
        assert not state.exists()
        expected_stage = {
            "dump": "consistent pg_dump",
            "collision": "conditional encrypted S3 upload",
            "encryption": "S3 readback and checksum verification",
            "checksum": "S3 readback and checksum verification",
            "readback": "S3 readback and checksum verification",
            "network": "start isolated scratch container",
            "mount": "start isolated scratch container",
            "restore": "restore downloaded archive",
            "schema": "verify restored structure",
            "cleanup_label": "cleanup verified scratch resources",
        }.get(failure, "preflight")
        assert "STOPPED_STAGE " + expected_stage + " ERROR_TYPE" in capsys.readouterr().out
        assert not any(c[:2] == ["docker", "rm"] for c in calls)
    else:
        exec(code, {"__name__": "__main__"})
        assert json.loads(state.read_text())["sha256"] == digest.hex()
        assert not list(tmp_path.glob("enter-backup-verified-*"))
    # No production restore, lifecycle edit or S3 deletion ever occurs.
    assert not any("delete-object" in c or "put-bucket-lifecycle-configuration" in c for c in calls)
    assert not any("stop" in c and "recruiter-db-1" in c for c in calls)


def test_backup_has_no_optimization_sensitive_assertions():
    assert not any(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(SCRIPT.read_text())))
