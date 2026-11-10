"""Read-only validation of prepared artifacts; does not authorize activation."""

import hashlib
import json
import os
import re
from pathlib import Path

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from rest_framework.exceptions import ValidationError  # noqa: E402
from talent import google_signup as signup  # noqa: E402
from talent import legal  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sections(text):
    parts = re.split(r"(?m)^(\d+\. [^\n]+)\n", text)
    return {
        int(parts[i].split(".")[0]): parts[i] + "\n" + parts[i + 1] for i in range(1, len(parts), 2)
    }


for name, source in [
    ("live-v1.0", ROOT / "deploy/live-legal-v1.0"),
    ("root-v1.2", ROOT / "deploy"),
]:
    folder = OUT / name
    manifest = json.loads((folder / "bundle-manifest.json").read_text())
    pending = json.loads((folder / "approval-record.pending.json").read_text())
    for purpose, filename, unchanged in [
        ("terms", "TERMS_PUBLICATION.txt", [3, 4, 5, 6, 7, 8, 10]),
        ("privacy", "PRIVACY_POLICY_PUBLICATION.txt", [1, 3, 4, 6, 8]),
    ]:
        path = folder / filename
        raw = path.read_text()
        text = raw.split("PROPOSED PUBLIC COPY\n", 1)[1].split("END OF PROPOSED PUBLIC COPY", 1)[0]
        assert hashlib.sha256(text.encode()).hexdigest() == manifest["documents"][purpose]["sha256"]
        assert manifest["documents"][purpose] == pending["documents"][purpose]
        base = legal._published_text(source / filename)
        assert all(sections(base)[n] == sections(text)[n] for n in unchanged)
        assert (
            hashlib.sha256((source / filename).read_bytes()).hexdigest()
            == manifest["baseline_file_sha256"][purpose]
        )
        try:
            legal._published_text(path)
        except ValidationError:
            pass
        else:
            raise AssertionError("An unapproved prepared bundle was accepted")
    current = legal.documents()
    for purpose in ["age", "submission"]:
        assert manifest["documents"][purpose]["sha256"] == current[purpose]["sha256"]
        from django.conf import settings

        assert manifest["documents"][purpose]["version"] == getattr(
            settings, f"LEGAL_{purpose.upper()}_VERSION"
        )
    assert manifest["notice_sha256"] == signup.sha(signup.NOTICE)
    assert pending["approved_at"] is None and pending["reviewer_name"] is None
    assert pending["decision"] is None and pending["effective_date"] is None
    print(
        name + ": document hashes and unchanged sections PASS; pending status rejected as required"
    )
print("Activation authorization: NOT SATISFIED. No runtime settings or candidate records changed.")
