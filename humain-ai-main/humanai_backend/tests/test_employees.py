import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.employee import Employee
from app.models.user import User, UserRole
import uuid

client = TestClient(app)

@pytest.fixture
async def create_test_employee(db):
    # Create user
    user = User(
        id=uuid.uuid4(),
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
    return emp

def test_list_employees_forbidden(mock_firebase_claims):
    # Collaborateur cannot list all employees
    mock_firebase_claims(role="collaborateur")
    response = client.get(
        "/api/v1/employees/",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 403

def test_list_employees_authorized(mock_firebase_claims, create_test_employee):
    # RH can list all employees
    mock_firebase_claims(role="rh")
    response = client.get(
        "/api/v1/employees/",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["total"] >= 1

def test_get_employee_detail(mock_firebase_claims, create_test_employee):
    mock_firebase_claims(role="rh")
    response = client.get(
        f"/api/v1/employees/11111111-1111-1111-1111-111111111111",
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["full_name"] == "Jane Doe"

def test_create_employee(mock_firebase_claims):
    mock_firebase_claims(role="rh")
    response = client.post(
        "/api/v1/employees/",
        json={
            "matricule": "EMP999",
            "full_name": "New Hire",
            "contract_type": "cdi"
        },
        headers={"Authorization": "Bearer mock_token"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["matricule"] == "EMP999"
