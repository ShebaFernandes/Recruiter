import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from talent.models import CandidateProfile, Resume

from .test_candidate_flow import complete_resume_upload, resume_docx

PASSWORD = "strong-pass-123"


def _signup_candidate(email, name):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/signup/",
        {"email": email, "password": PASSWORD, "full_name": name, "role": "candidate"},
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(username=email)
    user.is_active = True
    user.save(update_fields=["is_active"])
    user.candidate_profile.email_verified_at = timezone.now()
    user.candidate_profile.save(update_fields=["email_verified_at", "profile_updated_at"])
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, token.key


def _upload_resume(client, name, marker):
    upload = SimpleUploadedFile(
        f"{marker}.docx",
        resume_docx(name=name, extra=f"PRIVATE-{marker}"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response = client.post("/api/v1/candidate/resumes/", {"file": upload}, format="multipart")
    response = complete_resume_upload(client, response)
    return response.data["id"], response.data["latest_resume"]["id"]


def _assert_candidate_cannot_access_other(
    client, own_profile_id, other_profile_id, other_resume_id, marker
):
    private_profile_url = f"/api/v1/candidates/{other_profile_id}/"
    for method in (client.get, client.patch, client.delete):
        response = method(private_profile_url, {}, format="json")
        assert response.status_code == 403
        assert marker not in str(getattr(response, "data", ""))

    status_url = f"/api/v1/candidates/{other_profile_id}/status/"
    assert client.put(status_url, {"status": "sourced"}, format="json").status_code == 403
    assert client.delete(status_url).status_code == 403

    # Candidate writes are deliberately unaddressed: this URL can only ever
    # read/update the authenticated candidate's own one-to-one profile.
    for method in (client.get, client.patch, client.delete):
        response = method(
            f"/api/v1/candidate/profile/{other_profile_id}/", {}, format="json"
        )
        assert response.status_code == 404

    # Read-only identifiers in a payload cannot redirect the owner-scoped
    # endpoint to another profile.
    other_name = CandidateProfile.objects.get(pk=other_profile_id).full_name
    own_update = client.patch(
        "/api/v1/candidate/profile/",
        {"id": other_profile_id, "full_name": f"Owner {own_profile_id}"},
        format="json",
    )
    assert own_update.status_code == 200
    assert own_update.data["id"] == own_profile_id
    assert CandidateProfile.objects.get(pk=other_profile_id).full_name == other_name
    assert client.delete("/api/v1/candidate/profile/").status_code == 405

    download_url = f"/api/v1/resumes/{other_resume_id}/download/"
    response = client.get(download_url)
    assert response.status_code == 404
    assert response.status_code == client.get("/api/v1/resumes/99999999/download/").status_code
    assert marker not in str(getattr(response, "data", ""))

    # No resume mutation route exists. Existing and unknown IDs respond alike,
    # so method probing cannot reveal ownership or record existence.
    for method in (client.put, client.patch, client.delete):
        existing = method(download_url, {}, format="json")
        unknown = method("/api/v1/resumes/99999999/download/", {}, format="json")
        assert existing.status_code == unknown.status_code == 405

    for path in (
        f"/api/v1/candidate/resumes/{other_resume_id}/",
        f"/api/v1/candidate/applications/{other_profile_id}/",
    ):
        for method in (client.get, client.patch, client.delete):
            assert method(path, {}, format="json").status_code == 404

    assert client.post(
        "/api/v1/candidates/compare/",
        {"candidate_ids": [other_profile_id, other_profile_id + 1]},
        format="json",
    ).status_code == 403
    assert client.get("/api/v1/searches/").status_code == 403
    assert client.post(
        "/api/v1/searches/", {"query": "enumerate candidates"}, format="json"
    ).status_code == 403
    assert client.get("/api/v1/searches/99999999/results/").status_code == 403
    assert client.get("/api/v1/projects/").status_code == 403
    assert client.get("/api/v1/projects/99999999/").status_code == 403
    assert client.post(
        "/api/v1/projects/99999999/candidates/",
        {"candidate_id": other_profile_id},
        format="json",
    ).status_code == 403
    assert client.get("/api/v1/notifications/").status_code == 403


@pytest.mark.django_db
def test_candidates_are_strictly_isolated_in_both_directions(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        candidate_a, _ = _signup_candidate("candidate-a@example.com", "Candidate A")
        profile_a_id, resume_a_id = _upload_resume(candidate_a, "Candidate A", "A-SECRET")
        candidate_b, _ = _signup_candidate("candidate-b@example.com", "Candidate B")
        profile_b_id, resume_b_id = _upload_resume(candidate_b, "Candidate B", "B-SECRET")

        _assert_candidate_cannot_access_other(
            candidate_a, profile_a_id, profile_b_id, resume_b_id, "B-SECRET"
        )
        _assert_candidate_cannot_access_other(
            candidate_b, profile_b_id, profile_a_id, resume_a_id, "A-SECRET"
        )

        assert CandidateProfile.objects.filter(user__email="candidate-a@example.com").count() == 1
        assert CandidateProfile.objects.filter(user__email="candidate-b@example.com").count() == 1
        assert Resume.objects.filter(pk__in=[resume_a_id, resume_b_id]).count() == 2


@pytest.mark.django_db
def test_anonymous_users_and_direct_file_urls_cannot_access_candidate_data(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        owner, _ = _signup_candidate("private-owner@example.com", "Private Owner")
        profile_id, resume_id = _upload_resume(owner, "Private Owner", "OWNER-SECRET")
        profile = owner.get("/api/v1/candidate/profile/")
        resume = Resume.objects.get(pk=resume_id)

        assert profile.data["latest_resume"]["url"].endswith(
            f"/api/v1/resumes/{resume_id}/download/"
        )
        assert resume.file.name not in profile.data["latest_resume"]["url"]
        assert settings.MEDIA_URL not in profile.data["latest_resume"]["url"]

        anonymous = APIClient()
        private_requests = [
            anonymous.get("/api/v1/candidate/profile/"),
            anonymous.patch("/api/v1/candidate/profile/", {"full_name": "Intruder"}),
            anonymous.get(f"/api/v1/resumes/{resume_id}/download/"),
            anonymous.get(f"/api/v1/candidates/{profile_id}/"),
            anonymous.get("/api/v1/searches/"),
            anonymous.post("/api/v1/candidates/compare/", {"candidate_ids": [profile_id, 999]}),
        ]
        assert all(response.status_code == 401 for response in private_requests)

        # MEDIA_ROOT is never mounted by Django, even in local DEBUG mode.
        assert anonymous.get(f"{settings.MEDIA_URL}{resume.file.name}").status_code == 404
        assert anonymous.get("/api/v1/health/").data == {"status": "ok"}


@pytest.mark.django_db
def test_recruiter_resume_access_follows_submission_and_visibility_rules(tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        records = {}
        for label in ("approved", "draft", "paused", "matching"):
            client, _ = _signup_candidate(f"{label}@example.com", label.title())
            profile_id, resume_id = _upload_resume(client, label.title(), f"{label}-SECRET")
            records[label] = (profile_id, resume_id)

        CandidateProfile.objects.filter(pk=records["approved"][0]).update(
            profile_status="submitted",
            visibility="approved_recruiters",
            submission_consent_at=timezone.now(),
        )
        CandidateProfile.objects.filter(pk=records["draft"][0]).update(
            profile_status="draft", visibility="approved_recruiters"
        )
        CandidateProfile.objects.filter(pk=records["paused"][0]).update(
            profile_status="submitted",
            visibility="not_looking",
            submission_consent_at=timezone.now(),
        )
        CandidateProfile.objects.filter(pk=records["matching"][0]).update(
            profile_status="submitted",
            visibility="matching_roles",
            submission_consent_at=timezone.now(),
        )

        recruiter = APIClient()
        signup = recruiter.post(
            "/api/v1/auth/signup/",
            {
                "email": "privacy-recruiter@example.com",
                "password": PASSWORD,
                "full_name": "Privacy Recruiter",
                "company": "Enter",
                "role": "recruiter",
            },
            format="json",
        )
        recruiter.credentials(HTTP_AUTHORIZATION=f"Token {signup.data['token']}")

        project = recruiter.post(
            "/api/v1/projects/", {"name": "Private shortlist"}, format="json"
        )
        assert project.status_code == 201
        assert recruiter.post(
            f"/api/v1/projects/{project.data['id']}/candidates/",
            {"candidate_id": records["approved"][0]},
            format="json",
        ).status_code == 201

        assert recruiter.get(
            f"/api/v1/resumes/{records['approved'][1]}/download/"
        ).status_code == 200
        for label in ("draft", "paused", "matching"):
            assert recruiter.get(
                f"/api/v1/resumes/{records[label][1]}/download/"
            ).status_code == 404
            assert recruiter.get(f"/api/v1/candidates/{records[label][0]}/").status_code == 404
            assert recruiter.post(
                f"/api/v1/projects/{project.data['id']}/candidates/",
                {"candidate_id": records[label][0]},
                format="json",
            ).status_code == 404

        search = recruiter.post(
            "/api/v1/searches/",
            {"query": "Backend engineer with 4 years experience"},
            format="json",
        )
        assert search.status_code == 201
        answer = recruiter.post(
            f"/api/v1/searches/{search.data['id']}/answer/",
            {"answer": "Remote candidates are acceptable"},
            format="json",
        )
        assert answer.status_code == 200

        assert recruiter.get(
            f"/api/v1/resumes/{records['matching'][1]}/download/"
        ).status_code == 200
        assert recruiter.get(f"/api/v1/candidates/{records['matching'][0]}/").status_code == 200

        compared = recruiter.post(
            "/api/v1/candidates/compare/",
            {"candidate_ids": [profile_id for profile_id, _ in records.values()]},
            format="json",
        )
        assert compared.status_code == 200
        assert {item["id"] for item in compared.data} == {
            records["approved"][0],
            records["matching"][0],
        }


@pytest.mark.django_db
def test_resume_content_and_candidate_secrets_are_not_logged(tmp_path, caplog):
    with override_settings(MEDIA_ROOT=tmp_path):
        client, token = _signup_candidate("log-private@example.com", "Log Private")
        caplog.clear()
        _upload_resume(client, "Log Private", "DO-NOT-LOG-THIS-RESUME-TEXT")
        messages = "\n".join(record.getMessage() for record in caplog.records)
        assert "DO-NOT-LOG-THIS-RESUME-TEXT" not in messages
        assert "log-private@example.com" not in messages
        assert token not in messages
