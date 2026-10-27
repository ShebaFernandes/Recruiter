"""Read-only provenance for the CURRENT saved rows against the LATEST upload.

A completed job, a historical outcome, or equal row counts are not proof that
saved employment matches the latest resume. Never mutate candidate history here.
"""
from .candidate_experience import pending_fields, resume_identity_issue
from .employment_reconciliation import row_equivalent, trusted_rows


def employment_history(profile):
    saved = list(profile.work_experiences.all())
    resume = profile.resumes.first()
    confirmed = [row.pk for row in saved if row.confidence_status == 'candidate_confirmed']
    result = {
        'resume_id': resume.pk if resume else None,
        'resume_processing_status': resume.processing_status if resume else None,
        'status': 'review_required', 'source': 'unknown',
        'reason_code': 'verification_unavailable', 'accepted_role_count': 0,
        'saved_role_count': len(saved), 'profile_state': 'unchanged',
        'stale_profile_preserved': bool(saved),
        'verified_role_ids': [], 'candidate_confirmed_role_ids': confirmed,
        'unverified_role_ids': [row.pk for row in saved],
    }
    if not resume:
        result['reason_code'] = 'no_resume'
        return result
    if resume.processing_status in {'uploaded', 'queued', 'processing'}:
        result.update(status='processing', reason_code='latest_resume_processing')
        return result
    if resume.processing_status != 'completed' or resume.scan_status != 'clean':
        result['reason_code'] = 'latest_resume_failed'
        return result
    data = resume.extracted_data if isinstance(resume.extracted_data, dict) else {}
    outcome = data.get('_employment_outcome')
    if not isinstance(outcome, dict):
        return result
    for key in ('status', 'source', 'reason_code'):
        if key in outcome:
            result[key] = outcome[key]
    if resume_identity_issue(resume, profile):
        result.update(status='review_required', reason_code='resume_identity_mismatch')
        return result
    # Only rows accepted by the extraction/validation pipeline are eligible.
    signatures = trusted_rows(data)
    if result['status'] not in {'verified_ai', 'verified_fallback'}:
        signatures = []
    verified = [row.pk for row in saved if any(row_equivalent(row, item) for item in signatures)]
    result.update(
        accepted_role_count=len(signatures), verified_role_ids=verified,
        unverified_role_ids=[row.pk for row in saved if row.pk not in verified],
        stale_profile_preserved=bool(saved) and len(verified) != len(saved),
    )
    if 'work_experiences' in pending_fields(resume, profile):
        result['profile_state'] = 'pending_candidate_review'
    elif saved and not verified:
        result['profile_state'] = 'previous_history_preserved'
    elif verified and len(verified) == len(saved):
        result['profile_state'] = 'applied'
    elif verified:
        result['profile_state'] = 'previous_history_preserved'
    elif saved:
        result['profile_state'] = 'previous_history_preserved'
    else:
        result['profile_state'] = 'empty'
    return result
