"""Retired anonymous search must stay unreachable, even with legacy capabilities."""

from unittest.mock import patch

import pytest
from django.core import signing

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("suffix", ["", "answer/"])
def test_legacy_guest_routes_cannot_call_ai_or_grant_access(client, settings, suffix):
    settings.GUEST_SEARCH_ENABLED = True
    token = signing.dumps(
        {"query": "Backend engineer", "criteria": {"role": "Backend Engineer"}},
        salt="enter.guest-search.v1",
    )
    client.cookies["enter_guest_search"] = "legacy-browser"
    with patch("talent.search_understanding.get_ai_provider") as provider:
        response = client.post(
            f"/api/v1/guest/searches/{suffix}",
            {"query": "Backend engineer", "token": token},
            format="json",
        )
        assert response.status_code == 404
        provider.assert_not_called()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    assert client.get("/api/v1/searches/").status_code == 401
