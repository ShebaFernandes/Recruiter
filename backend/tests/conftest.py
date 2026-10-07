import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def candidate_account(client):
    response = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "asha@example.com",
            "password": "strong-pass-123",
            "full_name": "Asha Rao",
            "role": "candidate",
        },
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(username="asha@example.com")
    user.is_active = True
    user.save(update_fields=["is_active"])
    user.candidate_profile.email_verified_at = timezone.now()
    user.candidate_profile.save(update_fields=["email_verified_at", "profile_updated_at"])
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return {
        "token": token.key,
        "user": {"id": user.id, "email": user.email, "role": "candidate", "full_name": "Asha Rao"},
    }


@pytest.fixture
def recruiter_account(client):
    response = client.post(
        "/api/v1/auth/signup/",
        {
            "email": "recruiter@company.example",
            "password": "strong-pass-123",
            "full_name": "Ritu Mehta",
            "company": "Enter Labs",
            "role": "recruiter",
        },
        format="json",
    )
    assert response.status_code == 201
    client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
    return response.data
