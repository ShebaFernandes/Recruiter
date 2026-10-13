"""Candidate-owned preferences and evidence-bound resume review helpers."""

import json
from decimal import Decimal

MOTIVATORS = {
    "Exceptional team",
    "Harder problems",
    "More ownership",
    "Compensation",
    "Founding team",
    "Leadership",
    "Product",
    "Global exposure",
    "Founder",
}
LIST_FIELDS = {
    "custom_exclusions",
    "motivators",
    "exclusions",
    "preferred_locations",
    "contact_preferences",
    "strongest_skills",
    "likely_directions",
}
TEXT_FIELDS = {"availability", "standout_signal"}
RESUME_FIELDS = {
    "full_name",
    "headline",
    "current_company",
    "email",
    "phone",
    "location",
    "total_experience",
    "notice_period_days",
    "current_salary_lpa",
    "expected_salary_lpa",
    "linkedin_url",
    "github_url",
    "work_preferences",
    "skills",
    "education",
    "summary",
    "work_experiences",
}


def proposed_fields(extracted):
    # Zero is a real value. Missing values never clear saved information.
    return {
        key: value
        for key, value in extracted.items()
        if key in RESUME_FIELDS and value not in (None, "", [])
    }


def comparable(field, value):
    """Compare saved/extracted values without row IDs or decimal/date formatting noise."""
    if field in {"total_experience", "current_salary_lpa", "expected_salary_lpa"}:
        return str(Decimal(str(value)).normalize()) if value is not None else None
    if field == "work_experiences":
        from .services import parse_date

        rows = []
        for item in value:
            row = {key: item.get(key) or "" for key in (
                "company", "role", "description", "date_label", "gap_reason",
            )}
            for key in ("start_date", "end_date"):
                date = item.get(key)
                parsed = parse_date(str(date)) if date else None
                row[key] = parsed.isoformat() if parsed else None
            rows.append(row)
        unique = {json.dumps(row, sort_keys=True): row for row in rows}
        return [unique[key] for key in sorted(unique)]
    return value


def profile_values(profile):
    return {
        field: comparable(field, list(profile.work_experiences.values())
                          if field == "work_experiences" else getattr(profile, field))
        for field in RESUME_FIELDS
    }


def pending_fields(resume, profile):
    data = resume.extracted_data
    if not data.get("_needs_review"):
        return {}
    # Existing uploads remain reviewable, but unchanged fields are not conflicts.
    proposals = data.get("_pending_fields", proposed_fields(data))
    saved = profile_values(profile)
    return {key: value for key, value in proposals.items()
            if key in RESUME_FIELDS and comparable(key, value) != saved[key]}


def record_candidate_edits(profile, fields):
    """Private provenance in existing resume JSON; never returned in resume metadata."""
    resume = profile.resumes.first()
    if resume:
        data = resume.extracted_data
        data["_candidate_edited_fields"] = sorted(
            set(data.get("_candidate_edited_fields", [])) | (set(fields) & RESUME_FIELDS)
        )
        resume.save(update_fields=["extracted_data"])
