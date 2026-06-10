import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_admin_config_forbidden(mock_firebase_claims):
    # Non-admin user should receive 403 Forbidden
    mock_firebase_claims(role="collaborateur")
    response = client.get(
        "/api/v1/admin/config",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 403

def test_admin_config_authorized(mock_firebase_claims):
    mock_firebase_claims(role="admin")
    response = client.get(
        "/api/v1/admin/config",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert "firebase_project_id" in response.json()["data"]

def test_admin_health(mock_firebase_claims):
    mock_firebase_claims(role="admin")
    response = client.get(
        "/api/v1/admin/health",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert "status" in response.json()
    assert "services" in response.json()

def test_admin_queues(mock_firebase_claims):
    mock_firebase_claims(role="admin")
    response = client.get(
        "/api/v1/admin/queues",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert "onboarding-gen" in response.json()["data"]

def test_admin_flush_cache(mock_firebase_claims):
    mock_firebase_claims(role="admin")
    response = client.delete(
        "/api/v1/admin/cache/flush?scope=kpi",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert "Cache vidé" in response.json()["message"]
