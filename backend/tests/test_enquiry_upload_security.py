from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from talent.models import EmployeeTransitionEnquiry, HiringEnquiry
from talent.resume_processing import ResumeInfectedError, ResumeScanError

from .test_employee_transition import request_data
from .test_hiring_enquiries import hire_data


@pytest.mark.django_db
@pytest.mark.parametrize('kind', ['hiring', 'transition'])
@pytest.mark.parametrize('error,status', [(ResumeInfectedError, 400), (ResumeScanError, 503)])
def test_public_enquiry_files_fail_closed_before_persistence(kind, error, status):
    if kind == 'hiring':
        url, data = '/api/v1/hiring/enquiries/', hire_data()
        data['jd'] = SimpleUploadedFile('role.pdf', b'%PDF-1.4\nsynthetic')
    else:
        url, data = '/api/v1/support/employee-transition/', request_data('list')
        data['employee_list'] = SimpleUploadedFile(
            'people.csv', b'name,role,email\nExample,Engineer,a@example.com'
        )
    with patch('talent.enquiry_uploads.get_resume_scanner') as scanner:
        scanner.return_value.scan.side_effect = error('synthetic scanner result')
        response = APIClient().post(url, data, format='multipart')
        scanner.return_value.scan.assert_called_once()
    assert response.status_code == status
    assert not HiringEnquiry.objects.exists()
    assert not EmployeeTransitionEnquiry.objects.exists()


@pytest.mark.django_db
def test_company_enquiries_do_not_enable_recruiter_access(settings):
    settings.CANDIDATE_ONLY = True
    client = APIClient()
    response = client.post('/api/v1/hiring/enquiries/', hire_data(), format='multipart')
    assert response.status_code == 201
    assert HiringEnquiry.objects.count() == 1
    assert client.get('/api/v1/candidates/').status_code == 404
    assert client.get('/api/v1/projects/').status_code == 404
