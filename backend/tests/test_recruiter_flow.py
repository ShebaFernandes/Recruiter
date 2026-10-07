import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from talent.models import CandidateProfile, CandidateUpdateNotification, UserRole

from .test_candidate_flow import resume_docx


@pytest.mark.django_db
def test_clarified_search_profile_view_status_and_resume_update_notification(
    client, candidate_account, tmp_path
):
    with override_settings(MEDIA_ROOT=tmp_path):
        upload = SimpleUploadedFile(
            "asha.docx",
            resume_docx(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        created = client.post("/api/v1/candidate/resumes/", {"file": upload}, format="multipart")
        candidate_id = created.data["id"]
        visible = client.patch(
            "/api/v1/candidate/profile/",
            {"visibility": "approved_recruiters", "work_preferences": ["Hybrid"]},
            format="json",
        )
        assert visible.status_code == 200
        submitted = client.post(
            "/api/v1/candidate/profile/submit/", {"consent": True}, format="json"
        )
        assert submitted.status_code == 200
        assert submitted.data["profile_status"] == "submitted"
        client.post("/api/v1/auth/logout/")
        client.credentials()
        recruiter = client.post(
            "/api/v1/auth/signup/",
            {
                "email": "recruiter@company.example",
                "password": "strong-pass-123",
                "full_name": "Ritu Mehta",
                "company": "Enter Labs",
                "role": "recruiter",
            },
            format="json",
        )
        client.credentials(HTTP_AUTHORIZATION=f"Token {recruiter.data['token']}")
        search = client.post(
            "/api/v1/searches/",
            {"query": "Backend engineer with 4 years experience"},
            format="json",
        )
        assert search.status_code == 201
        assert search.data["state"] == "needs_clarification"
        assert "location" in search.data["follow_up_question"].lower()
        answered = client.post(
            f"/api/v1/searches/{search.data['id']}/answer/", {"answer": "Bengaluru"}, format="json"
        )
        assert answered.data["state"] == "complete"
        results = client.get(f"/api/v1/searches/{search.data['id']}/results/")
        assert results.status_code == 200
        assert results.data["count"] == 1

        profile = client.get(f"/api/v1/candidates/{candidate_id}/")
        assert profile.status_code == 200
        assert profile.data["viewed"] is True
        stage = client.put(
            f"/api/v1/candidates/{candidate_id}/status/", {"status": "sourced"}, format="json"
        )
        assert stage.status_code == 200
        refreshed = client.get(f"/api/v1/searches/{search.data['id']}/results/")
        assert refreshed.data["results"][0]["candidate"]["stage"] == "sourced"

        client.post("/api/v1/auth/logout/")
        client.credentials()
        login = client.post(
            "/api/v1/auth/login/",
            {"email": "asha@example.com", "password": "strong-pass-123"},
            format="json",
        )
        client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        update = SimpleUploadedFile(
            "asha-v2.docx",
            resume_docx(role="Staff Backend Engineer", extra="AWS"),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert (
            client.post(
                "/api/v1/candidate/resumes/", {"file": update}, format="multipart"
            ).status_code
            == 201
        )
        profile_update = client.patch(
            "/api/v1/candidate/profile/",
            {"meaningful_work": "Updated the reliability story after submission."},
            format="json",
        )
        assert profile_update.status_code == 200
        profile_notice = CandidateUpdateNotification.objects.get(
            candidate_id=candidate_id,
            change_type=CandidateUpdateNotification.ChangeType.PROFILE,
            is_read=False,
        )
        assert profile_notice.message == "Profile updated"
        profile_notice.is_read = True
        profile_notice.save(update_fields=["is_read"])
        availability_update = client.patch(
            "/api/v1/candidate/profile/",
            {"work_preferences": ["Remote"]},
            format="json",
        )
        assert availability_update.status_code == 200
        availability_notice = CandidateUpdateNotification.objects.get(
            candidate_id=candidate_id,
            change_type=CandidateUpdateNotification.ChangeType.PROFILE,
            is_read=False,
        )
        assert availability_notice.message == "Availability changed"
        availability_notice.is_read = True
        availability_notice.save(update_fields=["is_read"])
        experience_update = client.patch(
            "/api/v1/candidate/profile/",
            {
                "work_experiences": [
                    *profile_update.data["work_experiences"],
                    {
                        "company": "Enter Labs",
                        "role": "Platform Advisor",
                        "start_date": "2026-01-01",
                        "end_date": None,
                        "description": "Advised a platform reliability programme.",
                    },
                ]
            },
            format="json",
        )
        assert experience_update.status_code == 200
        assert CandidateUpdateNotification.objects.get(
            candidate_id=candidate_id,
            change_type=CandidateUpdateNotification.ChangeType.PROFILE,
            is_read=False,
        ).message == "New experience added"
        client.post("/api/v1/auth/logout/")
        client.credentials()
        recruiter_login = client.post(
            "/api/v1/auth/login/",
            {"email": "recruiter@company.example", "password": "strong-pass-123"},
            format="json",
        )
        client.credentials(HTTP_AUTHORIZATION=f"Token {recruiter_login.data['token']}")
        notices = client.get("/api/v1/notifications/")
        assert notices.status_code == 200
        assert all(item["candidate_name"] == "Asha Rao" for item in notices.data)
        assert any(item["message"] == "Updated resume" for item in notices.data)
        assert any(item["message"] == "Profile updated" for item in notices.data)
        assert any(item["message"] == "Availability changed" for item in notices.data)
        assert any(item["message"] == "New experience added" for item in notices.data)
        assert {item["change_type"] for item in notices.data} == {"resume", "profile"}
        read = client.post(f"/api/v1/notifications/{notices.data[0]['id']}/read/")
        assert read.status_code == 204


@pytest.mark.django_db
def test_not_looking_candidate_is_excluded_from_recruiter_search(
    client, candidate_account, tmp_path
):
    with override_settings(MEDIA_ROOT=tmp_path):
        upload = SimpleUploadedFile(
            "paused.docx",
            resume_docx(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert (
            client.post(
                "/api/v1/candidate/resumes/", {"file": upload}, format="multipart"
            ).status_code
            == 201
        )
    preference = client.patch(
        "/api/v1/candidate/profile/",
        {
            "headline": "Backend Engineer",
            "location": "Bengaluru",
            "total_experience": "6.0",
            "visibility": "not_looking",
            "work_preferences": ["Remote"],
        },
        format="json",
    )
    assert preference.status_code == 200
    submitted = client.post(
        "/api/v1/candidate/profile/submit/", {"consent": True}, format="json"
    )
    assert submitted.status_code == 200
    assert submitted.data["discovery_status"] == "not_looking"

    client.post("/api/v1/auth/logout/")
    client.credentials()
    recruiter = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "paused-search@company.example",
            "password": "strong-pass-123",
            "full_name": "Ritu Mehta",
            "company": "Enter Labs",
            "role": "recruiter",
        },
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Token {recruiter.data['token']}")
    search = client.post(
        "/api/v1/searches/",
        {"query": "Backend engineer with 4 years experience in Bengaluru"},
        format="json",
    )
    assert search.status_code == 201
    assert search.data["state"] == "complete"
    results = client.get(f"/api/v1/searches/{search.data['id']}/results/")
    assert results.status_code == 200
    assert results.data["count"] == 0


@pytest.mark.django_db
def test_draft_candidate_is_excluded_from_recruiter_search(client, candidate_account):
    profile = client.patch(
        "/api/v1/candidate/profile/",
        {
            "headline": "Backend Engineer",
            "location": "Bengaluru",
            "total_experience": "6.0",
            "visibility": "approved_recruiters",
            "work_preferences": ["Hybrid"],
        },
        format="json",
    )
    assert profile.status_code == 200
    assert profile.data["profile_status"] == "draft"

    client.post("/api/v1/auth/logout/")
    client.credentials()
    recruiter = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "draft-search@company.example",
            "password": "strong-pass-123",
            "full_name": "Ritu Mehta",
            "company": "Enter Labs",
            "role": "recruiter",
        },
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Token {recruiter.data['token']}")
    search = client.post(
        "/api/v1/searches/",
        {"query": "Backend engineer with 4 years experience in Bengaluru"},
        format="json",
    )
    results = client.get(f"/api/v1/searches/{search.data['id']}/results/")
    assert results.status_code == 200
    assert results.data["count"] == 0


def _discoverable_candidate(email, **overrides):
    user = User.objects.create_user(username=email, email=email, password="strong-pass-123")
    UserRole.objects.create(user=user, role=UserRole.Role.CANDIDATE)
    defaults = {
        "full_name": email.split("@")[0].title(),
        "headline": "Backend Engineer",
        "location": "Bengaluru",
        "total_experience": "5.0",
        "notice_period_days": 30,
        "expected_salary_lpa": "25.00",
        "employment_type": "Full-time",
        "skills": ["Python", "Django", "PostgreSQL"],
        "work_preferences": ["Hybrid"],
        "visibility": CandidateProfile.Visibility.APPROVED_RECRUITERS,
        "profile_status": CandidateProfile.ProfileStatus.SUBMITTED,
        "submitted_at": timezone.now(),
        "submission_consent_at": timezone.now(),
    }
    defaults.update(overrides)
    return CandidateProfile.objects.create(user=user, email=email, **defaults)


@pytest.mark.django_db
def test_combined_filters_progressive_clarification_and_project_shortlist(
    client, recruiter_account
):
    python_candidate = _discoverable_candidate("python@example.com")
    _discoverable_candidate(
        "java@example.com",
        total_experience="7.0",
        notice_period_days=60,
        expected_salary_lpa="36.00",
        employment_type="Contract",
        skills=["Java", "Kafka", "AWS"],
        work_preferences=["Remote"],
    )

    project = client.post(
        "/api/v1/projects/",
        {"name": "Backend shortlist", "description": "Senior product engineers"},
        format="json",
    )
    assert project.status_code == 201
    search = client.post(
        "/api/v1/searches/",
        {"query": "5 years experience", "project": project.data["id"]},
        format="json",
    )
    assert search.data["state"] == "needs_clarification"
    assert "role" in search.data["follow_up_question"].lower()
    role_answer = client.post(
        f"/api/v1/searches/{search.data['id']}/answer/",
        {"answer": "Backend Engineer"},
        format="json",
    )
    assert role_answer.data["state"] == "needs_clarification"
    assert "location" in role_answer.data["follow_up_question"].lower()
    location_answer = client.post(
        f"/api/v1/searches/{search.data['id']}/answer/",
        {"answer": "Remote is fine"},
        format="json",
    )
    assert location_answer.data["state"] == "complete"

    filtered = client.get(
        f"/api/v1/searches/{search.data['id']}/results/",
        {
            "role": "Backend Engineer",
            "skills": "Python,Django",
            "min_experience": "4",
            "max_experience": "6",
            "notice_period_days": "30",
            "min_salary_lpa": "20",
            "max_salary_lpa": "30",
            "employment_type": "Full-time",
            "work_preferences": "Hybrid",
        },
    )
    assert filtered.status_code == 200
    assert [item["candidate"]["id"] for item in filtered.data["results"]] == [
        python_candidate.id
    ]
    invalid = client.get(
        f"/api/v1/searches/{search.data['id']}/results/", {"min_experience": "many"}
    )
    assert invalid.status_code == 400

    added = client.post(
        f"/api/v1/projects/{project.data['id']}/candidates/",
        {"candidate_id": python_candidate.id},
        format="json",
    )
    assert added.status_code == 201
    assert client.post(
        f"/api/v1/projects/{project.data['id']}/candidates/",
        {"candidate_id": python_candidate.id},
        format="json",
    ).status_code == 200
    detail = client.get(f"/api/v1/projects/{project.data['id']}/")
    assert detail.status_code == 200
    assert detail.data["project"]["candidate_count"] == 1
    assert detail.data["project"]["search_count"] == 1
    assert detail.data["candidates"][0]["candidate"]["id"] == python_candidate.id
    removed = client.delete(
        f"/api/v1/projects/{project.data['id']}/candidates/{python_candidate.id}/"
    )
    assert removed.status_code == 204
