"""Scan public enquiry files before saving or exposing them to administrators."""
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .resume_processing import ResumeInfectedError, ResumeScanError, get_resume_scanner


class EnquiryScannerUnavailable(APIException):
    status_code = 503
    default_detail = "File scanning is temporarily unavailable. Please try again later."
    default_code = "scanner_unavailable"


def scan_enquiry_upload(uploaded):
    try:
        result = get_resume_scanner().scan(uploaded)
        if result != "clean":
            raise ResumeScanError("Unrecognized scan result")
    except ResumeInfectedError as error:
        raise serializers.ValidationError("The file did not pass the security scan.") from error
    except ResumeScanError as error:
        raise EnquiryScannerUnavailable() from error
    finally:
        uploaded.seek(0)
