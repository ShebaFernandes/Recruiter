"""Guard the already-published legal package used by production image builds."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_FILE_HASHES = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "7cfeb57abf1ac8537c59c1b06dc8b7bbeafc90e1dba6b3979737bef069a5bad9"
    ),
    "TERMS_PUBLICATION.txt": (
        "e6276b935d62840c98084e491e072781ac9776dd1ad3011c4d4d8276b7aaac8c"
    ),
    "RESUME_AI_CONSENT_PUBLICATION.txt": (
        "c9bbf730166a2d55a91d9a219c469f3d512c3c040adf36886f709daa767498b4"
    ),
}


def test_production_dockerfile_packages_current_published_legal_copy():
    dockerfile = (ROOT / "backend" / "Dockerfile.production").read_text()
    assert "deploy/live-legal-v1.0/" not in dockerfile
    for name, expected_sha256 in PUBLISHED_FILE_HASHES.items():
        source = ROOT / "deploy" / name
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256
        assert f"deploy/{name}" in dockerfile
