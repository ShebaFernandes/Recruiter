"""Regression coverage for the offline AI-disabled release gate."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ai_disabled_release_check_accepts_approved_but_unloaded_gemini_documents():
    result = subprocess.run(
        [sys.executable, "scripts/check_ai_disabled_release.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '"ai_disabled_release": "PASS"' in result.stdout
    assert '"approved_gemini_documents": "preserved and not loaded"' in result.stdout
