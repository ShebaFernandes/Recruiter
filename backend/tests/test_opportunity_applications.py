import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from talent.models import CandidateProfile, OpportunityApplication, Resume


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
    profile = CandidateProfile.objects.create(user=user, email_verified_at=timezone.now())
    Resume.objects.create(
        candidate=profile, file='test-only.docx', original_name='test.docx',
        processing_status='completed', scan_status='clean',
    )
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
    history = client.get('/api/v1/opportunities/applications/')
    assert history.status_code == 200
    assert [row['id'] for row in history.data] == [application.pk]
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

    source = Path(__file__).resolve().parents[2] / "frontend/src/components/opportunityRoles.ts"
    catalog = source.read_text().split("const roles = [", 1)[1].split("\n]", 1)[0]
    ids = re.findall(r"(?:\"id\"|id)\s*:\s*['\"]([^'\"]+)", catalog)
    assert len(ids) == len(set(ids))
    assert set(ids) == set(OPPORTUNITY_IDS)


@pytest.mark.django_db
def test_application_history_is_private_and_resume_required(client, candidate_account):
    response = client.post(
        '/api/v1/opportunities/applications/', {'opportunity_id': 'backend-engineer'}
    )
    assert response.status_code == 400
    assert client.get('/api/v1/opportunities/applications/').data == []
    other = User.objects.create_user(username='another-applicant')
    profile = CandidateProfile.objects.create(user=other)
    OpportunityApplication.objects.create(candidate=profile, opportunity_id='backend-engineer')
    assert client.get('/api/v1/opportunities/applications/').data == []


@pytest.mark.django_db
@pytest.mark.parametrize("path", [
    "/api/v1/opportunities/applications/",
    "/api/v1/candidate/profile/",
    "/api/v1/candidate/resumes/",
    "/api/v1/resumes/123/download/",
    "/api/v1/projects/",
    "/api/v1/searches/",
])
def test_public_browsing_does_not_open_private_api_access(client, path):
    response = client.get(path)
    assert response.status_code in (401, 403, 404)


@pytest.mark.django_db
def test_application_history_ignores_another_candidates_id(client, candidate_account):
    other = User.objects.create_user(username="other-synthetic-candidate")
    other_profile = CandidateProfile.objects.create(user=other, email_verified_at=timezone.now())
    OpportunityApplication.objects.create(
        candidate=other_profile, opportunity_id="backend-engineer",
    )
    response = client.get("/api/v1/opportunities/applications/", {"candidate_id": other_profile.pk})
    assert response.status_code == 200
    assert response.data == []
