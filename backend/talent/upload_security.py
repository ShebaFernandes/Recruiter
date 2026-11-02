"""Scan public attachments before creating a stored application or enquiry."""
from rest_framework import serializers
from rest_framework.exceptions import APIException


def scan_public_upload(uploaded):
    from .resume_processing import ResumeInfectedError, ResumeScanError, get_resume_scanner

    try:
        get_resume_scanner().scan(uploaded)
    except ResumeInfectedError:
        raise serializers.ValidationError(
            "The uploaded file did not pass the security scan."
        ) from None
    except ResumeScanError:
        error = APIException("File scanning is temporarily unavailable. Please try again.")
        error.status_code = 503
        raise error from None
    finally:
        uploaded.seek(0)
    return uploaded
