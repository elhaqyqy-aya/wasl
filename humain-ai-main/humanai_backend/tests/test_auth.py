import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import patch, MagicMock

client = TestClient(app)

def test_signup(mock_firebase_claims):
    # Mock firebase auth return for create_user
    fb_user_mock = MagicMock()
    fb_user_mock.uid = "test-uid-123"
    
    with patch("firebase_admin.auth.create_user", return_value=fb_user_mock):
        response = client.post(
            "/api/v1/auth/signup",
            json={
                "email": "test@humanai.com",
                "password": "strongPassword123",
                "display_name": "John Doe",
                "role": "collaborateur",
                "dept_id": "890538f9-d1cb-4df9-8902-69019623e111"
            }
        )
        assert response.status_code == 200
        assert response.json()["uid"] == "test-uid-123"

def test_login():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "idToken": "mock_id_token",
        "refreshToken": "mock_refresh_token",
        "expiresIn": "3600"
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@humanai.com", "password": "strongPassword123"}
        )
        assert response.status_code == 200
        assert "idToken" in response.json()

def test_logout(mock_firebase_claims):
    mock_firebase_claims(role="collaborateur")
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Déconnecté"}

def test_get_me(mock_firebase_claims):
    mock_firebase_claims(role="collaborateur", email="test@humanai.com")
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@humanai.com"
    assert response.json()["role"] == "collaborateur"
