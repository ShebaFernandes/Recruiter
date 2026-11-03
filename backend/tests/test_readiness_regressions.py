from unittest.mock import patch

import pytest
from django.db import OperationalError


@pytest.mark.django_db
def test_readiness_returns_safe_service_unavailable_when_database_fails(client):
    with patch("talent.views.connection.cursor", side_effect=OperationalError("private endpoint")):
        response = client.get("/api/v1/health/ready/")
    assert response.status_code == 503
    assert response.data == {"status": "not_ready", "database": "unavailable"}
    assert "private endpoint" not in str(response.content)


@pytest.mark.django_db
def test_health_and_readiness_are_public_and_small(client):
    assert client.get("/api/v1/health/").data == {"status": "ok"}
    response = client.get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.data["database"] == "ok"
