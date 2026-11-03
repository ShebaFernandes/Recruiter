import pytest
from rest_framework import serializers
from talent.hiring_views import BaseHiringSerializer
from talent.support_views import EmployeeTransitionEnquirySerializer
from talent.work_email import PERSONAL_EMAIL_DOMAINS


@pytest.mark.parametrize("serializer", [BaseHiringSerializer, EmployeeTransitionEnquirySerializer])
@pytest.mark.parametrize("domain", sorted(PERSONAL_EMAIL_DOMAINS))
def test_personal_email_rejected(serializer, domain):
    with pytest.raises(serializers.ValidationError):
        serializer().validate_work_email(f"person@{domain.upper()}")


@pytest.mark.parametrize("serializer", [BaseHiringSerializer, EmployeeTransitionEnquirySerializer])
def test_company_email_accepted(serializer):
    assert serializer().validate_work_email("person@company.example") == "person@company.example"
