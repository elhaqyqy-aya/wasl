from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.employee import Employee, EmployeeStatus
from app.utils.audit_logger import log_action
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import uuid, csv, io

router = APIRouter(prefix="/employees", tags=["Employees"])

class EmployeeCreate(BaseModel):
    matricule: str
    full_name: str
    position_id: Optional[str] = None
    department_id: Optional[str] = None
    hire_date: Optional[date] = None
    contract_type: str = "cdi"

class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    position_id: Optional[str] = None
    department_id: Optional[str] = None
    hire_date: Optional[date] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None

def employee_to_dict(e: Employee) -> dict:
    return {
        "id": str(e.id), "matricule": e.matricule, "full_name": e.full_name,
        "department_id": str(e.department_id) if e.department_id else None,
        "position_id": str(e.position_id) if e.position_id else None,
        "hire_date": str(e.hire_date) if e.hire_date else None,
        "contract_type": e.contract_type, "status": e.status,
    }

@router.get("/")
async def list_employees(
    dept_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(require_roles("rh", "admin", "direction")),
    db: AsyncSession = Depends(get_db),
):
    q = select(Employee)
    if dept_id:
        q = q.where(Employee.department_id == uuid.UUID(dept_id))
    if status:
        q = q.where(Employee.status == status)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.offset((page - 1) * limit).limit(limit))
    items = [employee_to_dict(e) for e in result.scalars()]
    return {"data": items, "total": total, "page": page, "limit": limit}

@router.get("/team")
async def list_team(user: CurrentUser = Depends(require_roles("manager")), db: AsyncSession = Depends(get_db)):
    q = select(Employee).where(Employee.department_id == uuid.UUID(user.dept_id) if user.dept_id else False)
    result = await db.execute(q)
    return {"data": [employee_to_dict(e) for e in result.scalars()]}

@router.get("/me")
async def get_my_profile(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not user.employee_id:
        raise HTTPException(status_code=404, detail="Profil collaborateur non trouvé")
    result = await db.execute(select(Employee).where(Employee.id == uuid.UUID(user.employee_id)))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Collaborateur non trouvé")
    return {"data": employee_to_dict(emp)}

@router.post("/")
async def create_employee(
    payload: EmployeeCreate,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    emp = Employee(id=uuid.uuid4(), matricule=payload.matricule, full_name=payload.full_name,
        department_id=uuid.UUID(payload.department_id) if payload.department_id else None,
        position_id=uuid.UUID(payload.position_id) if payload.position_id else None,
        hire_date=payload.hire_date, contract_type=payload.contract_type)
    db.add(emp)
    await db.flush()
    await log_action(db, user.uid, "CREATE", "employee", str(emp.id))
    return {"data": employee_to_dict(emp)}

@router.get("/export")
async def export_employees(
    user: CurrentUser = Depends(require_roles("rh", "direction", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id","matricule","full_name","department_id","status","contract_type","hire_date"])
    writer.writeheader()
    for e in result.scalars():
        writer.writerow(employee_to_dict(e))
    from fastapi.responses import Response
    return Response(content=output.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees.csv"})

@router.get("/{employee_id}")
async def get_employee(
    employee_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == uuid.UUID(employee_id)))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Collaborateur non trouvé")
    return {"data": employee_to_dict(emp)}

@router.put("/{employee_id}")
async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == uuid.UUID(employee_id)))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Non trouvé")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(emp, field, val)
    await log_action(db, user.uid, "UPDATE", "employee", employee_id)
    return {"data": employee_to_dict(emp)}

@router.delete("/{employee_id}")
async def archive_employee(
    employee_id: str,
    user: CurrentUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Employee).where(Employee.id == uuid.UUID(employee_id)))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Non trouvé")
    emp.status = EmployeeStatus.inactif
    await log_action(db, user.uid, "ARCHIVE", "employee", employee_id)
    return {"message": "Collaborateur archivé"}

@router.get("/{employee_id}/history")
async def get_employee_history(
    employee_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.audit import AuditLog
    result = await db.execute(
        select(AuditLog).where(AuditLog.entity_id == uuid.UUID(employee_id)).order_by(AuditLog.timestamp.desc())
    )
    logs = [{"id": str(l.id), "action": l.action, "timestamp": str(l.timestamp), "details": l.details} for l in result.scalars()]
    return {"data": logs}

@router.post("/import")
async def import_employees(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    created = 0
    for row in reader:
        emp = Employee(id=uuid.uuid4(), matricule=row.get("matricule",""), full_name=row.get("full_name",""))
        db.add(emp)
        created += 1
    return {"message": f"{created} collaborateurs importés"}
