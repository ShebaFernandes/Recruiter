"""The pre-0026 backend must remain able to insert resumes after an image rollback."""

from django.db import connection
from django.utils import timezone
from talent.candidate_experience import resume_identity_issue
from talent.models import CandidateProfile, Resume


def test_resume_hash_columns_keep_database_defaults(db):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'talent_resume'
              AND column_name IN ('file_sha256', 'ownership_confirmed_file_sha256')
            """
        )
        columns = {name: (default, nullable) for name, default, nullable in cursor.fetchall()}

    assert set(columns) == {'file_sha256', 'ownership_confirmed_file_sha256'}
    for default, nullable in columns.values():
        assert default is not None and default.startswith("''")
        assert nullable == 'NO'


def test_empty_database_hashes_never_confirm_resume_ownership(db, candidate_account):
    profile = CandidateProfile.objects.get(user_id=candidate_account['user']['id'])
    resume = Resume.objects.create(
        candidate=profile,
        file='quarantine/fictional-resume.docx',
        original_name='fictional-resume.docx',
        extracted_data={'email': 'unrelated@example.test'},
        version=2,
        processing_status=Resume.ProcessingStatus.COMPLETED,
        scan_status=Resume.ScanStatus.CLEAN,
        ownership_confirmed_at=timezone.now(),
    )

    assert resume.file_sha256 == ''
    assert resume.ownership_confirmed_file_sha256 == ''
    assert resume_identity_issue(resume, profile) == 'identity_unverified'

    resume.file_sha256 = 'a' * 64
    resume.ownership_confirmed_file_sha256 = 'b' * 64
    assert resume_identity_issue(resume, profile) == 'identity_unverified'
