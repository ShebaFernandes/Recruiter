import pytest

from .test_candidate_experience import upload
from .test_candidate_flow import resume_docx

pytestmark = pytest.mark.django_db


def test_latest_resume_replaces_manual_profile_correction(client, candidate_account):
    upload(client)
    response = client.patch('/api/v1/candidate/profile/', {
        'headline': 'Manually corrected title',
    }, format='json')
    assert response.status_code == 200
    updated = upload(client, resume_docx(role='Principal Engineer')).data
    assert updated['headline'] == 'Principal Engineer'
    assert updated['resume_review'] is None
