"""Destructive recovery checks ONLY against the disposable local rehearsal."""
import os
import subprocess
import time
import urllib.error
import urllib.request

from container_stack_smoke import COMPOSE, STACK, Client, command


def sql(query, database="enter"):
    return command("exec", "-T", "db", "psql", "-U", "enter", "-d", database,
                   "-At", "-v", "ON_ERROR_STOP=1", "-c", query).strip()


def ready():
    for _ in range(60):
        try:
            if sql("SELECT 1") == "1":
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(1)
    raise AssertionError("Disposable database did not recover")


def main():
    assert os.environ.get("STACK_DIR") and "enter-stack." in str(STACK)
    assert "17." in sql("SHOW server_version")
    assert sql("SHOW password_encryption") == "scram-sha-256"
    assert sql("SELECT extname FROM pg_extension ORDER BY extname") == "plpgsql"
    result = subprocess.run([*COMPOSE, "exec", "-T", "-e", "PGPASSWORD=wrong",
                             "db", "psql", "-h", "db", "-U", "enter",
                             "-d", "enter", "-c", "SELECT 1"], capture_output=True)
    assert result.returncode != 0 and b"password authentication failed" in result.stderr
    # Quiesce writes (including worker heartbeats) for deterministic restore comparison.
    command("stop", "worker", "backend")
    sql("CREATE TABLE recovery_probe (id integer PRIMARY KEY, note text); "
        "INSERT INTO recovery_probe VALUES (1, 'fictional durable record')")
    dump = subprocess.check_output([*COMPOSE, "exec", "-T", "db", "pg_dump",
                                    "-U", "enter", "-Fc", "enter"])
    sql("CREATE DATABASE enter_restore_probe", "postgres")
    subprocess.run([*COMPOSE, "exec", "-T", "db", "pg_restore", "-U", "enter",
                    "--exit-on-error", "-d", "enter_restore_probe"], input=dump, check=True)
    # Compare schema/data dumps, not merely whether pg_restore exited successfully.
    def snapshot(database):
        output = command("exec", "-T", "db", "pg_dump", "-U", "enter", "--no-owner",
                         "--no-privileges", database)
        return "\n".join(line for line in output.splitlines()
                         if not line.startswith(("--", "\\restrict", "\\unrestrict")))
    assert snapshot("enter") == snapshot("enter_restore_probe")
    container = command("ps", "-q", "db").strip()
    # PID 1 can ignore a signal sent from inside its namespace. Kill from Docker.
    # Docker treats this as a manual stop, so explicitly start it afterward.
    subprocess.run(["docker", "kill", "--signal=KILL", container], check=True,
                   capture_output=True)
    exit_code = subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.ExitCode}}", container], text=True)
    assert exit_code.strip() == "137"
    command("start", "db")
    ready()
    recovery_log = command("logs", "db")
    assert "database system was interrupted" in recovery_log
    assert "redo starts at" in recovery_log
    assert sql("SELECT note FROM recovery_probe") == "fictional durable record"
    command("up", "-d", "--force-recreate", "--no-deps", "db")
    ready()
    assert sql("SELECT note FROM recovery_probe") == "fictional durable record"
    command("restart", "edge", "backend", "worker")
    client = Client()
    for _ in range(60):
        try:
            if client.request("/api/v1/auth/csrf/")[0] == 200:
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    else:
        raise AssertionError("HTTPS application did not recover")
    response = client.opener.open("https://localhost:8447/", timeout=15)
    assert response.status == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert client.request("/admin/")[0] == 404
    assert client.request("/api/v1/candidate/profile/")[0] in (401, 403)
    sql("DROP TABLE recovery_probe")
    sql("DROP DATABASE enter_restore_probe", "postgres")
    print("PASS: PG17/SCRAM/extensions, full dump/restore equality, SIGKILL WAL recovery, "
          "volume persistence after container recreation, proxy/API/worker restart, HTTPS headers")


if __name__ == "__main__":
    main()
