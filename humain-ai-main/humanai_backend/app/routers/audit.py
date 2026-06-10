from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.audit import AuditLog, DataConsent, DataRequest
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid, csv, io

router = APIRouter(prefix="/audit", tags=["Audit"])

class ConsentCreate(BaseModel):
    employee_id: str
    purpose: str

class DataRequestCreate(BaseModel):
    request_type: str  # access|delete|portability

def log_to_dict(l): return {"id": str(l.id), "action": l.action, "entity_type": l.entity_type, "entity_id": str(l.entity_id) if l.entity_id else None, "timestamp": str(l.timestamp), "details": l.details}
def consent_to_dict(c): return {"id": str(c.id), "employee_id": str(c.employee_id), "purpose": c.purpose, "granted_at": str(c.granted_at), "revoked_at": str(c.revoked_at) if c.revoked_at else None}
def request_to_dict(r): return {"id": str(r.id), "employee_id": str(r.employee_id), "request_type": r.request_type, "status": r.status, "submitted_at": str(r.submitted_at)}

@router.get("/logs")
async def list_logs(user_id: Optional[str] = Query(None), action: Optional[str] = Query(None), entity_type: Optional[str] = Query(None), page: int = Query(1), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    q = select(AuditLog)
    if user_id: q = q.where(AuditLog.user_id == uuid.UUID(user_id))
    if action: q = q.where(AuditLog.action == action)
    if entity_type: q = q.where(AuditLog.entity_type == entity_type)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.order_by(AuditLog.timestamp.desc()).offset((page-1)*20).limit(20))
    return {"data": [log_to_dict(l) for l in result.scalars()], "total": total, "page": page}

@router.get("/logs/export")
async def export_logs(user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10000))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "action", "entity_type", "entity_id", "timestamp"])
    writer.writeheader()
    for l in result.scalars():
        writer.writerow({"id": str(l.id), "action": l.action, "entity_type": l.entity_type, "entity_id": str(l.entity_id) if l.entity_id else "", "timestamp": str(l.timestamp)})
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_logs.csv"})

@router.get("/logs/{log_id}")
async def get_log(log_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).where(AuditLog.id == uuid.UUID(log_id)))
    l = result.scalar_one_or_none()
    if not l: return {"data": None}
    return {"data": log_to_dict(l)}

@router.get("/consents")
async def list_consents(employee_id: Optional[str] = Query(None), purpose: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    q = select(DataConsent)
    if employee_id: q = q.where(DataConsent.employee_id == uuid.UUID(employee_id))
    result = await db.execute(q)
    return {"data": [consent_to_dict(c) for c in result.scalars()]}

@router.post("/consents")
async def create_consent(payload: ConsentCreate, user: CurrentUser = Depends(require_roles("rh")), db: AsyncSession = Depends(get_db)):
    c = DataConsent(id=uuid.uuid4(), employee_id=uuid.UUID(payload.employee_id), purpose=payload.purpose)
    db.add(c)
    await db.flush()
    return {"data": consent_to_dict(c)}

@router.delete("/consents/{consent_id}")
async def revoke_consent(consent_id: str, user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataConsent).where(DataConsent.id == uuid.UUID(consent_id)))
    c = result.scalar_one_or_none()
    if not c: return {"message": "Non trouvé"}
    c.revoked_at = datetime.utcnow()
    return {"message": "Consentement révoqué"}

@router.get("/data-requests")
async def list_data_requests(user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataRequest))
    return {"data": [request_to_dict(r) for r in result.scalars()]}

@router.post("/data-requests")
async def submit_data_request(payload: DataRequestCreate, user: CurrentUser = Depends(require_roles("collaborateur")), db: AsyncSession = Depends(get_db)):
    if not user.employee_id: return {"error": "Profil non lié"}
    r = DataRequest(id=uuid.uuid4(), employee_id=uuid.UUID(user.employee_id), request_type=payload.request_type)
    db.add(r)
    await db.flush()
    return {"data": request_to_dict(r)}

@router.post("/data-requests/{request_id}/process")
async def process_data_request(request_id: str, payload: dict, user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataRequest).where(DataRequest.id == uuid.UUID(request_id)))
    r = result.scalar_one_or_none()
    if not r: return {"message": "Non trouvé"}
    r.status = "processed"
    r.processed_at = datetime.utcnow()
    r.notes = payload.get("notes")
    return {"message": "Demande traitée"}
