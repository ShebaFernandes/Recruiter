import logging

import pytest
from talent.logging_filters import SensitiveValueFilter


@pytest.mark.parametrize(
    "message",
    [
        "client_secret=synthetic-sensitive-value",
        '{"client_secret": "synthetic-sensitive-value"}',
        "{'id_token': 'synthetic-sensitive-value'}",
        "https://local.invalid/callback?code=synthetic-sensitive-value&state=synthetic-state",
        "Authorization: Bearer synthetic-sensitive-value",
        "code_verifier=synthetic-sensitive-value",
        "notice_challenge=synthetic-sensitive-value",
        '{"challenge": "synthetic-sensitive-value"}',
    ],
)
def test_oauth_credential_shapes_are_redacted(message):
    record = logging.LogRecord("synthetic", logging.WARNING, __file__, 1, message, (), None)
    assert SensitiveValueFilter().filter(record)
    assert "synthetic-sensitive-value" not in record.getMessage()
    assert "synthetic-state" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()


def test_unrelated_profile_state_diagnostics_remain_available():
    record = logging.LogRecord(
        "synthetic", logging.INFO, __file__, 1, "profile_state=pending_candidate_review", (), None
    )
    SensitiveValueFilter().filter(record)
    assert record.getMessage() == "profile_state=pending_candidate_review"
