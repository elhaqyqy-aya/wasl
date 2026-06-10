import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.absence import Absence, AbsenceStatus
from app.models.employee import Employee
from app.models.user import User, UserRole
import uuid
from datetime import date

client = TestClient(app)

@pytest.fixture
async def setup_absence(db):
    # Create user
    user = User(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        firebase_uid="test-uid-123",
        email="emp@humanai.com",
        display_name="Jane Doe",
        role=UserRole.collaborateur,
    )
    db.add(user)
    await db.flush()
    
    # Create employee record linked to user
    emp = Employee(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_id=user.id,
        matricule="EMP001",
        full_name="Jane Doe",
        contract_type="cdi",
    )
    db.add(emp)
    await db.flush()

    absence = Absence(
        id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
        employee_id=emp.id,
        type="conge_paye",
        start_date=date(2026, 6, 8),
        end_date=date(2026, 6, 12),
        duration_days=5.0,
        status=AbsenceStatus.pending
    )
    db.add(absence)
    await db.flush()
    return absence

def test_create_absence(mock_firebase_claims, setup_absence):
    mock_firebase_claims(role="collaborateur")
    response = client.post(
        "/api/v1/absences/",
        json={
            "type": "conge_paye",
            "start_date": "2026-06-15",
            "end_date": "2026-06-19",
            "motif": "Vacances d'été"
        },
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["duration_days"] == 5.0

def test_approve_absence(mock_firebase_claims, setup_absence):
    mock_firebase_claims(role="rh")
    response = client.post(
        "/api/v1/absences/33333333-3333-3333-3333-333333333333/approve",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"

def test_update_absence(mock_firebase_claims, setup_absence):
    mock_firebase_claims(role="collaborateur")
    response = client.put(
        "/api/v1/absences/33333333-3333-3333-3333-333333333333",
        json={"motif": "Nouveau motif"},
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["motif"] == "Nouveau motif"

def test_cancel_absence(mock_firebase_claims, setup_absence):
    mock_firebase_claims(role="collaborateur")
    response = client.delete(
        "/api/v1/absences/33333333-3333-3333-3333-333333333333",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Demande d'absence annulée"
