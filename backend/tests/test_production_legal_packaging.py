"""Bind the deployable package to the unchanged production-approved snapshots."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory
from talent import legal, views

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "deploy" / "live-legal-v1.0"
RAW = {
    "PRIVACY_POLICY_PUBLICATION.txt": (
        "d1c43d6d463335d30d31d4bc1233bec83f9c8bc43a939ff4087b0b60d381d26c"
    ),
    "TERMS_PUBLICATION.txt": "c3d509227aa02272912175005f06e2ef7f675de09c8d37c705546476b513f572",
}
INTEGRITY = dict(
    LEGAL_CONTENT_APPROVED=True,
    LEGAL_WORKFLOW_PREVIEW=False,
    LEGAL_DOCUMENT_ROOT=SNAPSHOTS,
    LEGAL_RESUME_AI_APPROVED=False,
    LEGAL_PRIVACY_SHA256="ebbafdb80abbcaf856490d1385b74b2cf8e15ec8826e7297753c836c7f8db49e",
    LEGAL_TERMS_SHA256="55b5b1ebca80a523218760499bedd2c93650b9ff04350f4355c483d313e825ef",
    LEGAL_AGE_SHA256="66b79e5cc63ddd3760ed02abb947604bf28ca152fc991dd09e59e5711e960bdf",
    LEGAL_SUBMISSION_SHA256="d1beaf60fbea2b351f039dc64f37a54e76d8e42083fe216da199ece72b1b70ba",
)


def test_dockerfile_packages_only_exact_approved_legal_snapshots():
    dockerfile = (ROOT / "backend/Dockerfile.production").read_text()
    for name, digest in RAW.items():
        assert hashlib.sha256((SNAPSHOTS / name).read_bytes()).hexdigest() == digest
        assert f"deploy/live-legal-v1.0/{name}" in dockerfile
        assert f"COPY deploy/{name}" not in dockerfile
    assert "deploy/RESUME_AI_CONSENT_PUBLICATION.txt" not in dockerfile


def test_readiness_accepts_approved_snapshots_with_production_hashes():
    with override_settings(**INTEGRITY), patch("talent.views.connection.cursor") as cursor:
        documents = legal.documents()
        assert documents["terms"]["sha256"] == INTEGRITY["LEGAL_TERMS_SHA256"]
        assert documents["privacy"]["sha256"] == INTEGRITY["LEGAL_PRIVACY_SHA256"]
        response = views.readiness(APIRequestFactory().get("/api/v1/health/ready/"))
        assert response.status_code == 200
        cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")


@pytest.mark.parametrize("root", [ROOT / "deploy", "modified"])
def test_readiness_rejects_wrong_or_modified_legal_copy(root, tmp_path):
    if root == "modified":
        for name in RAW:
            (tmp_path / name).write_bytes((SNAPSHOTS / name).read_bytes())
        terms = tmp_path / "TERMS_PUBLICATION.txt"
        terms.write_text(
            terms.read_text().replace(
                "The candidate service is free", "The candidate service remains free"
            )
        )
        root = tmp_path
    with (
        override_settings(**{**INTEGRITY, "LEGAL_DOCUMENT_ROOT": root}),
        patch("talent.views.connection.cursor") as cursor,
    ):
        response = views.readiness(APIRequestFactory().get("/api/v1/health/ready/"))
        assert response.status_code == 503
        assert response.data == {"status": "not_ready", "legal_documents": "unavailable"}
        cursor.assert_not_called()
