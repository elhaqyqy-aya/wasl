from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.alert import HrAlert, AiSecurityEvent, AiSecurityRule, AlertSeverity
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

router = APIRouter(prefix="/alerts", tags=["Alertes"])

class RuleCreate(BaseModel):
    name: str
    condition_logic: dict
    severity: str

def alert_to_dict(a): return {"id": str(a.id), "employee_id": str(a.employee_id) if a.employee_id else None, "alert_type": a.alert_type, "severity": a.severity, "triggered_at": str(a.triggered_at), "is_read": a.is_read, "resolved_at": str(a.resolved_at) if a.resolved_at else None}
def event_to_dict(e): return {"id": str(e.id), "event_type": e.event_type, "severity": e.severity, "created_at": str(e.created_at)}
def rule_to_dict(r): return {"id": str(r.id), "name": r.name, "severity": r.severity, "is_active": r.is_active, "condition_logic": r.condition_logic}

@router.get("/")
async def list_alerts(severity: Optional[str] = Query(None), type: Optional[str] = Query(None), is_read: Optional[bool] = Query(None), page: int = Query(1), user: CurrentUser = Depends(require_roles("rh", "admin", "manager")), db: AsyncSession = Depends(get_db)):
    q = select(HrAlert)
    if severity: q = q.where(HrAlert.severity == severity)
    if type: q = q.where(HrAlert.alert_type == type)
    if is_read is not None: q = q.where(HrAlert.is_read == is_read)
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.order_by(HrAlert.triggered_at.desc()).offset((page-1)*20).limit(20))
    return {"data": [alert_to_dict(a) for a in result.scalars()], "total": total, "page": page}

@router.get("/mine")
async def my_alerts(is_read: Optional[bool] = Query(None), user: CurrentUser = Depends(require_roles("manager")), db: AsyncSession = Depends(get_db)):
    q = select(HrAlert)
    if is_read is not None: q = q.where(HrAlert.is_read == is_read)
    result = await db.execute(q.limit(50))
    return {"data": [alert_to_dict(a) for a in result.scalars()]}

@router.get("/stats")
async def alert_stats(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(HrAlert.id)))
    unread = await db.scalar(select(func.count(HrAlert.id)).where(HrAlert.is_read == False))
    critical = await db.scalar(select(func.count(HrAlert.id)).where(HrAlert.severity == "critique"))
    return {"data": {"total": total, "unread": unread, "critical": critical}}

@router.get("/{alert_id}")
async def get_alert(alert_id: str, user: CurrentUser = Depends(require_roles("rh", "admin", "manager")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HrAlert).where(HrAlert.id == uuid.UUID(alert_id)))
    a = result.scalar_one_or_none()
    if not a: raise HTTPException(404, "Alerte non trouvée")
    return {"data": alert_to_dict(a)}

@router.post("/{alert_id}/read")
async def mark_read(alert_id: str, user: CurrentUser = Depends(require_roles("rh", "admin", "manager")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HrAlert).where(HrAlert.id == uuid.UUID(alert_id)))
    a = result.scalar_one_or_none()
    if not a: raise HTTPException(404, "Non trouvée")
    a.is_read = True
    return {"message": "Marquée comme lue"}

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, payload: dict = {}, user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HrAlert).where(HrAlert.id == uuid.UUID(alert_id)))
    a = result.scalar_one_or_none()
    if not a: raise HTTPException(404, "Non trouvée")
    a.resolved_at = datetime.utcnow()
    a.resolution_notes = payload.get("resolution_notes")
    a.is_read = True
    return {"message": "Alerte résolue"}

# ---- Security ----
@router.get("/security/events")
async def list_security_events(severity: Optional[str] = Query(None), event_type: Optional[str] = Query(None), page: int = Query(1), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    q = select(AiSecurityEvent)
    if severity: q = q.where(AiSecurityEvent.severity == severity)
    if event_type: q = q.where(AiSecurityEvent.event_type == event_type)
    result = await db.execute(q.order_by(AiSecurityEvent.created_at.desc()).offset((page-1)*20).limit(20))
    return {"data": [event_to_dict(e) for e in result.scalars()], "page": page}

@router.get("/security/events/{event_id}")
async def get_security_event(event_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AiSecurityEvent).where(AiSecurityEvent.id == uuid.UUID(event_id)))
    e = result.scalar_one_or_none()
    if not e: raise HTTPException(404, "Événement non trouvé")
    return {"data": event_to_dict(e)}

@router.get("/security/rules")
async def list_rules(is_active: Optional[bool] = Query(None), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    q = select(AiSecurityRule)
    if is_active is not None: q = q.where(AiSecurityRule.is_active == is_active)
    result = await db.execute(q)
    return {"data": [rule_to_dict(r) for r in result.scalars()]}

@router.post("/security/rules")
async def create_rule(payload: RuleCreate, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    rule = AiSecurityRule(id=uuid.uuid4(), name=payload.name, condition_logic=payload.condition_logic, severity=AlertSeverity(payload.severity))
    db.add(rule)
    await db.flush()
    return {"data": rule_to_dict(rule)}

@router.put("/security/rules/{rule_id}")
async def update_rule(rule_id: str, payload: dict, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AiSecurityRule).where(AiSecurityRule.id == uuid.UUID(rule_id)))
    r = result.scalar_one_or_none()
    if not r: raise HTTPException(404, "Règle non trouvée")
    if "condition_logic" in payload: r.condition_logic = payload["condition_logic"]
    if "is_active" in payload: r.is_active = payload["is_active"]
    return {"data": rule_to_dict(r)}

@router.delete("/security/rules/{rule_id}")
async def delete_rule(rule_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AiSecurityRule).where(AiSecurityRule.id == uuid.UUID(rule_id)))
    r = result.scalar_one_or_none()
    if not r: raise HTTPException(404, "Non trouvée")
    await db.delete(r)
    return {"message": "Règle supprimée"}

@router.get("/security/stats")
async def security_stats(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(AiSecurityEvent.id)))
    injections = await db.scalar(select(func.count(AiSecurityEvent.id)).where(AiSecurityEvent.event_type == "prompt_injection"))
    unauthorized = await db.scalar(select(func.count(AiSecurityEvent.id)).where(AiSecurityEvent.event_type == "unauthorized_access"))
    return {"data": {"total_events": total, "prompt_injections": injections, "unauthorized_access": unauthorized}}
