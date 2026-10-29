"""Guard the approved legal package used by AI-disabled production image builds."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE_SNAPSHOT_FILE_HASHES = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "d1c43d6d463335d30d31d4bc1233bec83f9c8bc43a939ff4087b0b60d381d26c"
    ),
    "TERMS_PUBLICATION.txt": (
        "c3d509227aa02272912175005f06e2ef7f675de09c8d37c705546476b513f572"
    ),
}


def test_production_dockerfile_packages_approved_live_legal_snapshot():
    dockerfile = (ROOT / "backend" / "Dockerfile.production").read_text()
    for name, expected_sha256 in LIVE_SNAPSHOT_FILE_HASHES.items():
        source = ROOT / "deploy" / "live-legal-v1.0" / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
        assert f"deploy/live-legal-v1.0/{name}" in dockerfile
    assert "deploy/RESUME_AI_CONSENT_PUBLICATION.txt" not in dockerfile
