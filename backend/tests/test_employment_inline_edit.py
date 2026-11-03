from datetime import date

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from talent.employment_reconciliation import reconcile_employment
from talent.models import CandidateProfile, WorkExperience

pytestmark = pytest.mark.django_db


def _role(profile, **fields):
    return WorkExperience.objects.create(
        candidate=profile, company="Fictional Studio", role="Engineer",
        start_date=date(2020, 3, 12), end_date=None,
        date_label="Mar 2020 — End not specified", origin="resume_derived",
        confidence_status="supported", source_evidence="Private prior evidence",
        **fields,
    )


def test_inline_edit_updates_one_role_and_keeps_ids_and_other_records(client, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    first = _role(profile)
    second = WorkExperience.objects.create(
        candidate=profile, company="Another Fictional Employer", role="Intern",
        start_date=date(2019, 6, 1), end_date=date(2019, 8, 1),
        date_label="Jun 2019 — Aug 2019", origin="resume_derived",
    )
    response = client.patch(
        f"/api/v1/candidate/work-experiences/{first.pk}/",
        {"role": "Senior Engineer", "start": {"year": 2020, "month": None},
         "end": {"year": 2023, "month": 9}}, format="json",
    )
    assert response.status_code == 200, response.data
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.pk in [row["id"] for row in response.data["work_experiences"]]
    assert WorkExperience.objects.filter(candidate=profile).count() == 2
    assert (first.role, first.start_date, first.end_date, first.date_label) == (
        "Senior Engineer", None, date(2023, 9, 1), "2020 — Sep 2023"
    )
    assert (first.origin, first.confidence_status) == ("candidate", "candidate_confirmed")
    assert first.source_evidence == "Private prior evidence"
    assert (second.pk, second.company, second.origin) == (
        second.pk, "Another Fictional Employer", "resume_derived"
    )


def test_current_role_year_only_and_unknown_dates_remain_truthful(client, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    row = _role(profile)
    url = f"/api/v1/candidate/work-experiences/{row.pk}/"
    response = client.patch(url, {"is_current": True}, format="json")
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert (row.end_date, row.is_current, row.date_label) == (
        None, True, "Mar 2020 — Present"
    )
    response = client.patch(
        url, {"is_current": False, "end": {"year": 2025, "month": None}}, format="json"
    )
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert (row.end_date, row.is_current, row.date_label) == (
        None, False, "Mar 2020 — 2025"
    )
    response = client.patch(url, {"end": {"year": None, "month": None}}, format="json")
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert row.end_date is None and row.date_label == "Mar 2020 — End not specified"


def test_name_only_edit_preserves_exact_untouched_dates(client, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    row = _role(profile)
    response = client.patch(
        f"/api/v1/candidate/work-experiences/{row.pk}/",
        {"company": "Corrected Fictional Studio"}, format="json",
    )
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert row.start_date == date(2020, 3, 12)
    assert row.date_label == "Mar 2020 — End not specified"


def test_inline_edit_rejects_other_candidates_and_archived_roles(client, candidate_account):
    other_user = User.objects.create_user(username="other@example.test", password="private")
    other = CandidateProfile.objects.create(user=other_user)
    foreign = _role(other)
    response = client.patch(
        f"/api/v1/candidate/work-experiences/{foreign.pk}/",
        {"role": "Changed"}, format="json",
    )
    assert response.status_code == 404
    foreign.refresh_from_db()
    assert foreign.role == "Engineer"
    own = _role(CandidateProfile.objects.get(user_id=candidate_account["user"]["id"]))
    own.archived_at = timezone.now()
    own.save(update_fields=["archived_at"])
    assert client.patch(
        f"/api/v1/candidate/work-experiences/{own.pk}/",
        {"role": "Changed"}, format="json",
    ).status_code == 404


def test_recruiter_cannot_edit_candidate_employment(client, recruiter_account):
    assert client.patch(
        "/api/v1/candidate/work-experiences/1/", {"role": "Changed"}, format="json"
    ).status_code == 403


def test_missing_employer_and_title_can_be_filled_without_rewriting_dates(
    client, candidate_account,
):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    row = WorkExperience.objects.create(
        candidate=profile, company="", role="", date_label="Dates not specified",
        origin="resume_derived", confidence_status="partial",
    )
    response = client.patch(
        f"/api/v1/candidate/work-experiences/{row.pk}/",
        {"company": "Fictional Workshop", "role": "Developer"}, format="json",
    )
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert (row.company, row.role, row.date_label) == (
        "Fictional Workshop", "Developer", "Dates not specified"
    )
    assert row.start_date is None and row.end_date is None


def test_invalid_dates_cannot_change_saved_history(client, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    row = _role(profile)
    url = f"/api/v1/candidate/work-experiences/{row.pk}/"
    for payload in (
        {"start": {"year": None, "month": 3}},
        {"end": {"year": 2019, "month": 12}},
        {"is_current": True, "end": {"year": 2023, "month": 4}},
        {"role": ""},
    ):
        assert client.patch(url, payload, format="json").status_code == 400
    row.refresh_from_db()
    assert row.role == "Engineer" and row.start_date == date(2020, 3, 12)


def test_repeat_resume_merge_preserves_candidate_date_correction(client, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account["user"]["id"])
    row = _role(profile)
    response = client.patch(
        f"/api/v1/candidate/work-experiences/{row.pk}/",
        {"end": {"year": 2023, "month": 9}}, format="json",
    )
    assert response.status_code == 200, response.data
    incoming = {"company": "Fictional Studio", "role": "Engineer",
                "start_date": "2020-03-01", "end_date": None,
                "date_label": "Mar 2020 — End not specified", "is_current": False}
    reconcile_employment(profile, [incoming], complete=False)
    row.refresh_from_db()
    assert WorkExperience.objects.filter(candidate=profile).count() == 1
    assert (row.pk, row.end_date, row.origin, row.confidence_status) == (
        row.pk, date(2023, 9, 1), "candidate", "candidate_confirmed"
    )
