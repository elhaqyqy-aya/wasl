from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.absence import Absence, AbsenceStatus, AbsenceType
from app.models.employee import Employee
from app.utils.audit_logger import log_action
from app.redis_client import queue_push
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import uuid

router = APIRouter(prefix="/absences", tags=["Absences"])

class AbsenceCreate(BaseModel):
    type: str
    start_date: date
    end_date: date
    motif: Optional[str] = None

class AbsenceUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    motif: Optional[str] = None

class AbsenceRejection(BaseModel):
    rejection_reason: str

def absence_to_dict(a: Absence) -> dict:
    return {
        "id": str(a.id), "employee_id": str(a.employee_id), "type": a.type,
        "start_date": str(a.start_date), "end_date": str(a.end_date),
        "duration_days": float(a.duration_days) if a.duration_days else None,
        "status": a.status, "motif": a.motif,
        "created_at": str(a.created_at) if a.created_at else None,
    }

def calc_days(start: date, end: date) -> float:
    from datetime import timedelta
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days

@router.get("/")
async def list_absences(
    employee_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20),
    user: CurrentUser = Depends(require_roles("rh", "admin", "direction")),
    db: AsyncSession = Depends(get_db),
):
    q = select(Absence)
    if employee_id:
        q = q.where(Absence.employee_id == uuid.UUID(employee_id))
    if status:
        q = q.where(Absence.status == status)
    if year:
        q = q.where(func.extract("year", Absence.start_date) == year)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.offset((page-1)*limit).limit(limit))
    return {"data": [absence_to_dict(a) for a in result.scalars()], "total": total, "page": page}

@router.get("/team")
async def list_team_absences(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    user: CurrentUser = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
):
    emp_q = select(Employee.id).where(Employee.department_id == uuid.UUID(user.dept_id) if user.dept_id else False)
    emp_ids = (await db.execute(emp_q)).scalars().all()
    q = select(Absence).where(Absence.employee_id.in_(emp_ids))
    if status:
        q = q.where(Absence.status == status)
    result = await db.execute(q)
    return {"data": [absence_to_dict(a) for a in result.scalars()]}

@router.get("/me")
async def list_my_absences(
    year: Optional[int] = Query(None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.employee_id:
        return {"data": []}
    q = select(Absence).where(Absence.employee_id == uuid.UUID(user.employee_id))
    if year:
        q = q.where(func.extract("year", Absence.start_date) == year)
    result = await db.execute(q)
    return {"data": [absence_to_dict(a) for a in result.scalars()]}

@router.post("/")
async def create_absence(
    payload: AbsenceCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in ["collaborateur", "rh"]:
        raise HTTPException(status_code=403, detail="Accès refusé")
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="Profil collaborateur non lié")
    emp_id = uuid.UUID(user.employee_id)
    absence = Absence(
        id=uuid.uuid4(), employee_id=emp_id,
        type=AbsenceType(payload.type), start_date=payload.start_date,
        end_date=payload.end_date, motif=payload.motif,
        duration_days=calc_days(payload.start_date, payload.end_date),
    )
    db.add(absence)
    await db.flush()
    await log_action(db, user.uid, "CREATE", "absence", str(absence.id))
    return {"data": absence_to_dict(absence)}

@router.get("/stats")
async def absence_stats(
    scope: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    user: CurrentUser = Depends(require_roles("rh", "direction", "admin")),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count(Absence.id)))
    approved = await db.scalar(select(func.count(Absence.id)).where(Absence.status == AbsenceStatus.approved))
    pending = await db.scalar(select(func.count(Absence.id)).where(Absence.status == AbsenceStatus.pending))
    rejected = await db.scalar(select(func.count(Absence.id)).where(Absence.status == AbsenceStatus.rejected))
    
    # Calculate days by absence type
    result = await db.execute(
        select(Absence.type, func.sum(Absence.duration_days)).group_by(Absence.type)
    )
    duration_by_type = {row[0]: float(row[1]) if row[1] else 0.0 for row in result.all()}
    
    return {
        "total_requests": total,
        "approved_requests": approved or 0,
        "pending_requests": pending or 0,
        "rejected_requests": rejected or 0,
        "duration_by_type": duration_by_type
    }

@router.post("/{absence_id}/approve")
async def approve_absence(
    absence_id: str,
    user: CurrentUser = Depends(require_roles("rh", "manager", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == uuid.UUID(absence_id)))
    absence = result.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence non trouvée")
        
    absence.status = AbsenceStatus.approved
    from app.models.user import User
    user_result = await db.execute(select(User.id).where(User.firebase_uid == user.uid))
    db_user_id = user_result.scalar_one_or_none()
    absence.approved_by = db_user_id
    absence.approved_at = datetime.utcnow()
    
    await log_action(db, user.uid, "APPROVE", "absence", absence_id)
    return {"message": "Absence approuvée", "data": absence_to_dict(absence)}

@router.post("/{absence_id}/reject")
async def reject_absence(
    absence_id: str,
    payload: AbsenceRejection,
    user: CurrentUser = Depends(require_roles("rh", "manager", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == uuid.UUID(absence_id)))
    absence = result.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence non trouvée")
        
    absence.status = AbsenceStatus.rejected
    absence.rejection_reason = payload.rejection_reason
    
    await log_action(db, user.uid, "REJECT", "absence", absence_id)
    return {"message": "Absence rejetée", "data": absence_to_dict(absence)}

@router.put("/{absence_id}")
async def update_absence(
    absence_id: str,
    payload: AbsenceUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == uuid.UUID(absence_id)))
    absence = result.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence non trouvée")
    
    # Check if pending
    if absence.status != AbsenceStatus.pending:
        raise HTTPException(status_code=400, detail="Seules les demandes en attente peuvent être modifiées")
        
    # Check ownership unless user is RH
    if user.role != "rh" and str(absence.employee_id) != user.employee_id:
        raise HTTPException(status_code=403, detail="Accès interdit")
        
    if payload.start_date:
        absence.start_date = payload.start_date
    if payload.end_date:
        absence.end_date = payload.end_date
    if payload.motif:
        absence.motif = payload.motif
        
    if payload.start_date or payload.end_date:
        absence.duration_days = calc_days(absence.start_date, absence.end_date)
        
    await log_action(db, user.uid, "UPDATE", "absence", absence_id)
    return {"data": absence_to_dict(absence)}

@router.delete("/{absence_id}")
async def cancel_absence(
    absence_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Absence).where(Absence.id == uuid.UUID(absence_id)))
    absence = result.scalar_one_or_none()
    if not absence:
        raise HTTPException(status_code=404, detail="Absence non trouvée")
        
    # Check ownership
    if str(absence.employee_id) != user.employee_id and user.role != "rh":
        raise HTTPException(status_code=403, detail="Accès interdit")
        
    if absence.status != AbsenceStatus.pending:
        raise HTTPException(status_code=400, detail="Seules les demandes en attente peuvent être annulées")
        
    absence.status = AbsenceStatus.cancelled
    await log_action(db, user.uid, "CANCEL", "absence", absence_id)
    return {"message": "Demande d'absence annulée"}

@router.get("/calendar")
async def get_absence_calendar(
    team_id: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    user: CurrentUser = Depends(require_roles("manager", "rh")),
    db: AsyncSession = Depends(get_db),
):
    # Fetch team members
    t_id = team_id or user.dept_id
    if not t_id:
        return {"data": []}
        
    emp_q = select(Employee.id).where(Employee.department_id == uuid.UUID(t_id))
    emp_ids = (await db.execute(emp_q)).scalars().all()
    
    q = select(Absence).where(Absence.employee_id.in_(emp_ids))
    if month:
        q = q.where(func.extract("month", Absence.start_date) == month)
        
    result = await db.execute(q)
    return {"data": [absence_to_dict(a) for a in result.scalars()]}
