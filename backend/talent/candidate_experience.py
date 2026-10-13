"""Candidate-owned preferences and evidence-bound resume review helpers."""

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
