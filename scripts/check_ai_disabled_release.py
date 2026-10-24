"""Offline invariants for the AI-disabled production release candidate.

This check reads repository files only. It never connects to production, a cloud
provider, or an AI provider, and it never prints environment values or secrets.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_ROOT = ROOT / "deploy" / "live-legal-v1.0"
PENDING_ROOT = ROOT / "deploy"

LIVE_HASHES = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "ebbafdb80abbcaf856490d1385b74b2cf8e15ec8826e7297753c836c7f8db49e"
    ),
    "TERMS_PUBLICATION.txt": ("55b5b1ebca80a523218760499bedd2c93650b9ff04350f4355c483d313e825ef"),
}
PENDING_HASHES = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "6549ab6514b940459b8b853ee63643fc97c91f9dfc2d62aac511083c6b1bf574"
    ),
    "TERMS_PUBLICATION.txt": ("c545340b49350c664d0073e081dd4314a6464238adc6a61f9fc8a87b5647dd53"),
    "RESUME_AI_CONSENT_PUBLICATION.txt": (
        "e9ba89892b3b29aa738ef7dc7ff2913149be87c44080a058ddfa3cc677041040"
    ),
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def public_text(path):
    source = path.read_text()
    lines = source.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "PROPOSED PUBLIC COPY"]
    ends = [
        index for index, line in enumerate(lines) if line.strip() == "END OF PROPOSED PUBLIC COPY"
    ]
    require(
        len(starts) == 1 and len(ends) == 1 and ends[0] > starts[0],
        f"Invalid boundary: {path}",
    )
    return source, "".join(lines[starts[0] + 1 : ends[0]]).strip() + "\n"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def parse_env(path):
    values = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip()
    return values


def verify_legal_files():
    for name, expected in LIVE_HASHES.items():
        source, text = public_text(LIVE_ROOT / name)
        statuses = [
            line.strip() for line in source.splitlines() if line.startswith("PUBLICATION STATUS:")
        ]
        require(
            statuses == ["PUBLICATION STATUS: APPROVED"],
            f"Live legal snapshot is not approved: {name}",
        )
        require(digest(text) == expected, f"Live legal snapshot hash changed: {name}")

    for name, expected in PENDING_HASHES.items():
        source, text = public_text(PENDING_ROOT / name)
        statuses = [
            line.strip() for line in source.splitlines() if line.startswith("PUBLICATION STATUS:")
        ]
        require(
            statuses == ["PUBLICATION STATUS: PENDING REVIEW"],
            f"Pending Gemini document status changed: {name}",
        )
        require(digest(text) == expected, f"CEO-approved pending document hash changed: {name}")


def verify_packaging():
    dockerfile = (ROOT / "backend" / "Dockerfile.production").read_text()
    require(
        "deploy/live-legal-v1.0/PRIVACY_POLICY_PUBLICATION.txt" in dockerfile
        and "deploy/live-legal-v1.0/TERMS_PUBLICATION.txt" in dockerfile,
        "Production image does not package the approved live v1.0 legal snapshot",
    )
    require(
        "deploy/RESUME_AI_CONSENT_PUBLICATION.txt" not in dockerfile,
        "Pending Gemini consent must not be packaged in the AI-disabled image",
    )

    compose = (ROOT / "compose.production.yaml").read_text()
    required_lines = (
        "AI_PROVIDER: disabled",
        'ANTHROPIC_API_KEY: ""',
        'OPENAI_API_KEY: ""',
        'GEMINI_API_KEY: ""',
        'RESUME_AI_API_KEY: ""',
        'RESUME_AI_ENABLED: "false"',
        'RESUME_AI_EXTERNAL_PROCESSING_APPROVED: "false"',
        'RESUME_AI_ALLOW_PAID: "false"',
    )
    for line in required_lines:
        require(line in compose, f"Missing fail-closed production setting: {line}")

    release_override = (ROOT / "deploy" / "compose.ai-disabled-release.yaml").read_text()
    override_lines = required_lines + (
        'OPENROUTER_API_KEY: ""',
        'RESUME_AI_GEMINI_FREE_TIER_APPROVED: "false"',
    )
    for line in override_lines:
        require(line in release_override, f"Missing release-override setting: {line}")
    require(
        "db:" not in release_override
        and "scanner:" not in release_override
        and "edge:" not in release_override,
        "Application release override must not target stateful or edge services",
    )


def verify_environment(path):
    values = parse_env(path)
    expected = {
        "LEGAL_CONTENT_APPROVED": "true",
        "LEGAL_PRIVACY_VERSION": "enter-candidate-privacy-v1.0",
        "LEGAL_TERMS_VERSION": "enter-candidate-terms-v1.0",
        "LEGAL_PRIVACY_SHA256": LIVE_HASHES["PRIVACY_POLICY_PUBLICATION.txt"],
        "LEGAL_TERMS_SHA256": LIVE_HASHES["TERMS_PUBLICATION.txt"],
        "LEGAL_RESUME_AI_APPROVED": "false",
        "RESUME_AI_ENABLED": "false",
        "RESUME_AI_EXTERNAL_PROCESSING_APPROVED": "false",
        "RESUME_AI_ALLOW_PAID": "false",
        "CANDIDATE_REGISTRATION_PAUSED": "false",
        "RESUME_UPLOADS_PAUSED": "false",
    }
    for name, expected_value in expected.items():
        require(values.get(name, "").lower() == expected_value, f"Unsafe release value: {name}")
    require(values.get("LEGAL_EFFECTIVE_DATE"), "LEGAL_EFFECTIVE_DATE is missing")
    require(values.get("LEGAL_RESUME_AI_SHA256", "") == "", "Pending AI consent hash must not load")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optionally verify a populated production env file without printing its values.",
    )
    args = parser.parse_args()
    verify_legal_files()
    verify_packaging()
    if args.env_file:
        require(args.env_file.is_file(), "Production env file does not exist")
        verify_environment(args.env_file)
    print(
        json.dumps(
            {
                "ai_disabled_release": "PASS",
                "live_legal": "v1.0 hash-pinned",
                "pending_gemini_documents": "preserved and unpublished",
                "candidate_intake": "verify-unpaused-env" if not args.env_file else "unpaused",
                "external_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
