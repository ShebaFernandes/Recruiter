"""Real HTTP integration against the LOCAL isolated production-like stack only.

Requires STACK_DIR (compose.yaml + cert.pem), local HTTPS on 8447, and the test
mail sink proxied at /test-mail/. Never point this at staging or real candidates.
No mocks: actual Gunicorn, PostgreSQL, ClamAV, local S3/SQS and SMTP STARTTLS.
"""
import http.cookiejar
import io
import json
import os
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

STACK = Path(os.environ["STACK_DIR"]).resolve()
if not str(STACK).startswith(("/tmp/enter-stack.", "/private/tmp/enter-stack.")):
    raise SystemExit("Only an explicitly created /tmp/enter-stack.* rehearsal is allowed.")
ORIGIN = "https://localhost:8447"
COMPOSE = ["docker", "compose", "-f", str(STACK / "compose.yaml")]
PASSWORD = "Orchid!72-Cobalt!91-Zebra"


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context(
                cafile=str(STACK / "cert.pem"))),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

    def request(self, path, method="GET", data=None, filename=None, content=None):
        headers = {"Origin": ORIGIN, "Referer": ORIGIN + "/"}
        if method != "GET":
            headers["X-CSRFToken"] = self.request("/api/v1/auth/csrf/")[1]["csrfToken"]
        if filename:
            boundary = "enter-" + uuid.uuid4().hex
            data = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                    f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
                    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        elif data is not None:
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(ORIGIN + path, data=data, method=method, headers=headers)
        try:
            response = self.opener.open(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        body = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            body = json.loads(body)
        return response.status, body


def command(*args):
    return subprocess.check_output([*COMPOSE, *args], text=True, stderr=subprocess.STDOUT)


def account(label):
    client = Client()
    email = f"container-{label}-{uuid.uuid4().hex[:8]}@example.test"
    status, body = client.request("/api/v1/auth/signup/", "POST", {
        "email": email, "password": PASSWORD, "full_name": "Synthetic Candidate",
        "role": "candidate",
    })
    assert status == 201, (status, body)
    assert "local_verification_url" not in body
    messages = client.request("/test-mail/api/v1/messages")[1]["messages"]
    match = next(item for item in messages if any(x["Address"] == email for x in item["To"]))
    message = client.request("/test-mail/api/v1/message/" + match["ID"])[1]
    token = re.search(r"[?&]verify-email=([^\s]+)", message["Text"]).group(1)
    assert client.request("/api/v1/auth/verify-email/", "POST", {"token": token})[0] == 200
    status, body = client.request("/api/v1/auth/login/", "POST", {
        "email": email, "password": PASSWORD,
    })
    assert status == 200 and "token" not in body
    return client, email


def documents(email):
    lines = ["Name: Synthetic Candidate", f"Email: {email}", "Role: Backend Engineer",
             "Company: Fictional Systems", "Location: Bengaluru", "6 years of experience",
             "Skills: Python, Django, PostgreSQL", "Notice period: 30 days",
             "Current salary: 20", "Expected salary: 25",
             "Education: B.Tech Computer Science, Fictional University",
             "Experience: Backend Engineer|Fictional Systems|2022-01-01|Present|Built APIs",
             "Experience: Engineer|Example Labs|2020-01-01|2021-12-01|Built services"]
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    docx = io.BytesIO()
    doc.save(docx)
    pdf = PdfWriter()
    page = pdf.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
        NameObject("/F1"): pdf._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(("BT /F1 9 Tf 40 750 Td " + " 0 -18 Td ".join(
        f"({line}) Tj" for line in lines) + " ET").encode())
    page[NameObject("/Contents")] = pdf._add_object(stream)
    out = io.BytesIO()
    pdf.write(out)
    return out.getvalue(), docx.getvalue()


def completed(client, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, body = client.request("/api/v1/candidate/resume-status/")
        assert status == 200
        resume = body["resume"]
        if resume["processing_status"] == "completed":
            assert resume["scan_status"] == "clean"
            return resume["id"]
        assert resume["processing_status"] != "failed", resume
        time.sleep(1)
    raise AssertionError("Worker did not finish within bounded test time")


def main():
    client, email = account("owner")
    pdf, docx = documents(email)
    command("stop", "worker")
    # Let any outstanding two-second long poll finish before sending a new message.
    # Otherwise SQS may hide a delivered-but-unclaimed message for its 360s lease.
    time.sleep(3)
    assert client.request("/api/v1/candidate/resumes/", "POST", filename="fictional.pdf",
                          content=pdf)[0] == 202
    assert client.request("/api/v1/candidate/resume-status/")[1]["resume"][
        "processing_status"] == "queued"
    command("start", "worker")
    pdf_id = completed(client)
    assert client.request(f"/api/v1/resumes/{pdf_id}/download/")[1].startswith(b"%PDF")
    profile = client.request("/api/v1/candidate/profile/")[1]
    assert len(profile["work_experiences"]) == 2
    print("PASS: real STARTTLS email verification, cookie auth, SQS queued recovery, PDF/S3/ClamAV")

    # A real process crash must restart through Docker's policy.
    worker_id = command("ps", "-q", "worker").strip()
    def restarts():
        return int(subprocess.check_output(
            ["docker", "inspect", "--format", "{{.RestartCount}}", worker_id], text=True))
    before = restarts()
    kill_script = (
        "import os,signal,pathlib; "
        "p=next(p for p in pathlib.Path('/proc').iterdir() if p.name.isdigit() and int(p.name)>1 "
        "and (p/'cmdline').exists() and b'run_resume_worker' in "
        "(p/'cmdline').read_bytes().split(bytes([0]))); "
        "os.kill(int(p.name),signal.SIGKILL)"
    )
    subprocess.run([*COMPOSE, "exec", "-T", "worker", "python", "-c", kill_script],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if restarts() > before:
            break
        time.sleep(1)
    assert restarts() > before, "Docker restart policy did not restart the crashed worker"
    time.sleep(3)  # Let the killed receiver's outstanding local-emulator long poll expire.
    command("stop", "scanner")
    assert client.request("/api/v1/candidate/resumes/", "POST", filename="fictional.docx",
                          content=docx)[0] == 202
    resume_id = client.request("/api/v1/candidate/resume-status/")[1]["resume"]["id"]
    for _ in range(20):
        probe = ("import json;from talent.models import ResumeProcessingJob;"
                 f"j=ResumeProcessingJob.objects.get(resume_id={resume_id});"
                 "print(json.dumps({'attempts':j.attempts,'state':j.state,'error':j.last_error}))")
        state = json.loads(command("exec", "-T", "backend", "python", "manage.py", "shell",
                                   "-c", probe).strip().splitlines()[-1])
        if state["attempts"] and state["state"] == "queued" and "scann" in state["error"]:
            break
        time.sleep(1)
    pending = client.request("/api/v1/candidate/resume-status/")[1]["resume"]
    command("start", "scanner")
    assert state["attempts"] and "scann" in state["error"], state
    assert pending["scan_status"] != "clean" and pending["processing_status"] != "completed"
    docx_id = completed(client, timeout=150)
    assert client.request(f"/api/v1/candidate/resumes/{docx_id}/preview/")[0] == 200
    print("PASS: worker crash/restart; scanner outage fail-closed and recovery; DOCX preview")
    for fmt in ["JPEG", "PNG", "WEBP"]:
        image = io.BytesIO()
        Image.new("RGB", (100, 100), color="purple").save(image, format=fmt)
        assert client.request("/api/v1/candidate/photo/", "POST",
                              filename="photo." + fmt.lower(), content=image.getvalue())[0] == 200
        assert client.request("/api/v1/candidate/photo/")[0] == 200
    assert client.request("/api/v1/candidate/photo/", "POST", filename="invalid.png",
                          content=b"not an image")[0] == 400
    other, _ = account("other")
    assert other.request(f"/api/v1/resumes/{docx_id}/download/")[0] in (403, 404)
    assert Client().request(f"/api/v1/resumes/{docx_id}/download/")[0] == 401
    assert client.request("/api/v1/projects/")[0] == 403
    status, profile = client.request("/api/v1/candidate/profile/", "PATCH", {
        "meaningful_work": "Built a fictional service for a test.", "visibility": "matching_roles",
        "work_preferences": ["Remote"], "build_lead_preference": 50,
    })
    assert status == 200 and profile["can_submit"], profile.get("missing_fields")
    assert client.request("/api/v1/candidate/profile/submit/", "POST", {"consent": True})[0] == 200
    fresh = Client()
    assert fresh.request("/api/v1/auth/login/", "POST", {
        "email": email, "password": PASSWORD})[0] == 200
    assert fresh.request("/api/v1/candidate/profile/")[1]["profile_status"] == "submitted"
    assert fresh.request("/api/v1/candidate/profile/")[1]["build_lead_preference"] == 50
    for user in [fresh, other]:
        assert user.request("/api/v1/candidate/account/", "DELETE", {
            "confirmation": "DELETE", "password": PASSWORD})[0] == 204
    print("PASS: JPG/PNG/WebP, invalid-image rejection, private ownership, "
          "settings, submission, deletion")

    # Standard harmless antivirus test signature, never a real malware sample.
    infected, infected_email = account("eicar")
    _, infected_docx = documents(infected_email)
    eicar = bytes.fromhex(
        "58354f2150254041505b345c505a58353428505e2937434329377d2445494341522d"
        "5354414e444152442d414e544956495255532d544553542d46494c452124482b482a"
    )
    archive = io.BytesIO(infected_docx)
    with ZipFile(archive, "a") as zipped:
        zipped.writestr("word/embeddings/eicar.com", eicar)
    assert infected.request("/api/v1/candidate/resumes/", "POST", filename="av-test.docx",
                            content=archive.getvalue())[0] == 202
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        rejected = infected.request("/api/v1/candidate/resume-status/")[1]["resume"]
        if rejected["scan_status"] == "infected":
            break
        time.sleep(1)
    assert rejected["scan_status"] == "infected", rejected
    assert rejected["processing_status"] == "failed", rejected
    assert infected.request(f"/api/v1/resumes/{rejected['id']}/download/")[0] != 200
    assert infected.request(f"/api/v1/resumes/{rejected['id']}/preview/")[0] != 200
    assert infected.request("/api/v1/candidate/account/", "DELETE", {
        "confirmation": "DELETE", "password": PASSWORD})[0] == 204
    print("PASS: embedded EICAR DOCX rejected by real worker; no infected preview/download")
    check_updater_recovery()


def check_updater_recovery():
    # The custom scanner supervisor must also recover a failed signature updater.
    scanner_id = command("ps", "-q", "scanner").strip()
    inspect = ["docker", "inspect", "--format"]
    before = int(subprocess.check_output(
        [*inspect, "{{.RestartCount}}", scanner_id], text=True))
    command("exec", "-T", "scanner", "bash", "-c", 'kill -TERM "$(pgrep -x freshclam)"')
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        count = int(subprocess.check_output(
            [*inspect, "{{.RestartCount}}", scanner_id], text=True))
        health = subprocess.check_output(
            [*inspect, "{{.State.Health.Status}}", scanner_id], text=True).strip()
        if count > before and health == "healthy":
            break
        time.sleep(1)
    assert count > before and health == "healthy", (count, health)
    command("exec", "-T", "scanner", "pgrep", "-x", "freshclam")
    print("PASS: signature updater failure restarts scanner and updater; healthy again")


if __name__ == "__main__":
    main()
