"""Apply the production fail-closed scanner to every public attachment."""
from .enquiry_uploads import scan_enquiry_upload


def scan_public_upload(uploaded):
    scan_enquiry_upload(uploaded)
    return uploaded
