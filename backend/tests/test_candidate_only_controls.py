import pytest
from django.test import override_settings
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.mark.django_db(transaction=True)
def test_queued_job_completes_while_intake_paused(client, candidate_account):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from talent.models import ResumeProcessingJob
    from talent.worker_runtime import run_bounded_job
    from tests.test_candidate_flow import resume_pdf

    response = client.post('/api/v1/candidate/resumes/', {
        'file': SimpleUploadedFile('synthetic.pdf', resume_pdf()),
    }, format='multipart')
    job = ResumeProcessingJob.objects.get(resume_id=response.data['latest_resume']['id'])
    with override_settings(CANDIDATE_ONLY=True, CANDIDATE_REGISTRATION_PAUSED=True,
                           RESUME_UPLOADS_PAUSED=True):
        assert run_bounded_job(job.pk) == 'completed'
        assert run_bounded_job(job.pk) == 'duplicate'


@pytest.mark.parametrize(
    "path",
    [
        "/recruiter",
        "/recruiter/account",
        "/api/v1/projects/",
        "/api/v1/searches/",
        "/api/v1/candidates/999/",
        "/api/v1/notifications/",
    ],
)
def test_direct_routes_denied(client, path):
    with override_settings(CANDIDATE_ONLY=True):
        assert client.get(path).status_code == 404
        assert client.post(path, {}, format="json").status_code == 404


def test_existing_recruiter_and_login_denied(client, recruiter_account):
    with override_settings(CANDIDATE_ONLY=True):
        assert client.get("/api/v1/auth/me/").status_code == 401
        assert client.get("/api/v1/resumes/999/download/").status_code == 401
        anonymous = APIClient()
        response = anonymous.post(
            "/api/v1/auth/login/",
            {
                "email": "recruiter@company.example",
                "password": "strong-pass-123",
            },
            format="json",
        )
        assert response.status_code == 403
    assert client.get("/api/v1/projects/").status_code == 200


def test_intake_switches_independent_and_existing_candidate_works(client, candidate_account):
    with override_settings(CANDIDATE_ONLY=True, CANDIDATE_REGISTRATION_PAUSED=True):
        assert client.post("/api/v1/auth/signup/", {}).status_code == 503
        assert client.get("/api/v1/candidate/profile/").status_code == 200
        assert client.post("/api/v1/candidate/resumes/", {}).status_code != 503
        assert (
            APIClient()
            .post(
                "/api/v1/auth/login/",
                {
                    "email": "asha@example.com",
                    "password": "strong-pass-123",
                },
                format="json",
            )
            .status_code
            == 200
        )
        from rest_framework.authtoken.models import Token

        token = Token.objects.get(user_id=candidate_account["user"]["id"])
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    with override_settings(RESUME_UPLOADS_PAUSED=True):
        assert client.post("/api/v1/candidate/resumes/", {}).status_code == 503
        assert client.post("/api/v1/candidate/resumes/1/retry/", {}).status_code == 503
        assert client.get("/api/v1/candidate/resume-status/").status_code == 200
        assert client.post("/api/v1/auth/signup/", {}).status_code != 503
