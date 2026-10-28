"""Candidate-owned preferences and evidence-bound resume review helpers."""

import json
import re
import unicodedata
from decimal import Decimal

MOTIVATORS = {
    "Exceptional people",
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
    "custom_motivators",
    "custom_exclusions",
    "motivators",
    "exclusions",
    "preferred_locations",
    "contact_preferences",
    "strongest_skills",
    "likely_directions",
}
TEXT_FIELDS = {"availability", "standout_signal", "portfolio_url"}
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
                "employment_type", "location",
            )}
            row["is_current"] = bool(item.get("is_current"))
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
    if resume_identity_issue(resume, profile):
        return {}
    if not data.get("_needs_review"):
        return {}
    # Existing uploads remain reviewable, but unchanged fields are not conflicts.
    proposals = data.get("_pending_fields", proposed_fields(data))
    saved = profile_values(profile)
    from .employment_reconciliation import row_equivalent

    result = {}
    for key, value in proposals.items():
        if key not in RESUME_FIELDS:
            continue
        if key == 'work_experiences':
            unresolved = [item for item in value if not any(
                row_equivalent(row, item) for row in profile.work_experiences.all())]
            if unresolved:
                result[key] = unresolved
        elif comparable(key, value) != saved[key]:
            result[key] = value
    return result


def name_tokens(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return set(re.findall(r"[^\W\d_]+", value)) - {"mr", "mrs", "ms", "dr"}


def resume_identity_issue(resume, profile):
    """Conservative replacement guard, also applied to previously processed uploads.

    Names are not identity proof. Unknown or substantially different names require a
    corrected document, not a one-click permission to combine different people's data.
    """
    recorded = resume.extracted_data.get("_identity_issue")
    if recorded == "identity_mismatch":
        return recorded
    incoming = name_tokens(resume.extracted_data.get("full_name", ""))
    saved = name_tokens(profile.full_name)
    source = resume.extracted_data.get("_identity_name_source")
    if incoming and saved and incoming != saved and source == "explicit_header":
        return "identity_mismatch"
    if resume.version <= 1:
        return None
    if not saved:
        return "identity_unverified"
    if incoming and incoming != saved:
        issue = "identity_unverified" if source in {"inferred_header", "none"} else (
            "identity_mismatch"
        )
        if issue == "identity_mismatch":
            return issue
    elif incoming == saved:
        return None
    else:
        # A verified account email appearing in the document is an independent
        # identity anchor. An auto-filled profile address may be circular.
        document_email = (resume.extracted_data.get("email") or "").strip().casefold()
        account_email = (profile.user.email or "").strip().casefold()
        if (profile.email_verified_at and document_email and account_email
                and document_email == account_email):
            return None
        issue = "identity_unverified"
    file_hash = getattr(resume, "file_sha256", "")
    confirmed_hash = getattr(resume, "ownership_confirmed_file_sha256", "")
    if (issue == "identity_unverified" and getattr(resume, "ownership_confirmed_at", None)
            and file_hash and confirmed_hash and file_hash == confirmed_hash):
        return None
    return issue


def can_confirm_resume_identity(resume, profile):
    """Ownership declaration is for missing anchors, never a conflicting name."""
    return (
        resume_identity_issue(resume, profile) == "identity_unverified"
        and not name_tokens(resume.extracted_data.get("full_name", ""))
    )


def record_candidate_edits(profile, fields):
    """Private provenance in existing resume JSON; never returned in resume metadata."""
    resume = profile.resumes.first()
    if resume:
        data = resume.extracted_data
        data["_candidate_edited_fields"] = sorted(
            set(data.get("_candidate_edited_fields", [])) | (set(fields) & RESUME_FIELDS)
        )
        resume.save(update_fields=["extracted_data"])
