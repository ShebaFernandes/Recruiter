import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from talent.models import CandidateProfile, OpportunityApplication


@pytest.mark.django_db
def test_application_requires_login(client):
    response = client.post(
        "/api/v1/opportunities/applications/", {"opportunity_id": "backend-engineer"}, format="json"
    )
    assert response.status_code in (401, 403)
    assert not OpportunityApplication.objects.exists()


@pytest.mark.django_db
def test_candidate_application_persists_and_prevents_duplicates(client):
    user = User.objects.create_user(username="opportunity-candidate")
    CandidateProfile.objects.create(user=user, email_verified_at=timezone.now())
    client.force_authenticate(user)
    body = {"opportunity_id": "backend-engineer", "note": "Interested in backend systems."}
    assert (
        client.post("/api/v1/opportunities/applications/", body, format="json").status_code == 201
    )
    assert (
        client.post("/api/v1/opportunities/applications/", body, format="json").status_code == 200
    )
    application = OpportunityApplication.objects.get()
    assert application.candidate.user_id == user.id
    assert application.note == body["note"]
    assert (
        client.post(
            "/api/v1/opportunities/applications/", {"opportunity_id": "unknown"}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.django_db
@pytest.mark.parametrize("verified,active", [(False, True), (True, False)])
def test_unverified_or_disabled_candidate_cannot_apply(client, verified, active):
    user = User.objects.create_user(username="blocked-applicant", is_active=active)
    CandidateProfile.objects.create(
        user=user, email_verified_at=timezone.now() if verified else None
    )
    client.force_authenticate(user)
    response = client.post(
        "/api/v1/opportunities/applications/", {"opportunity_id": "backend-engineer"}
    )
    assert response.status_code == 403
    assert not OpportunityApplication.objects.exists()


def test_every_public_opportunity_has_one_backend_application_choice():
    import re
    from pathlib import Path

    from talent.opportunity_views import OPPORTUNITY_IDS

    source = Path(__file__).resolve().parents[2] / "frontend/src/components/Opportunities.tsx"
    catalog = source.read_text().split("const roles = [", 1)[1].split("\n]", 1)[0]
    ids = re.findall(r"(?:\"id\"|id)\s*:\s*['\"]([^'\"]+)", catalog)
    assert len(ids) == len(set(ids))
    assert set(ids) == set(OPPORTUNITY_IDS)
