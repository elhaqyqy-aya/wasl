from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import require_roles, CurrentUser
from app.models.alert import AiInteraction, AiSecurityEvent
from typing import Optional
import uuid

router = APIRouter(prefix="/supervision", tags=["Supervision IA"])

@router.get("/interactions")
async def list_interactions(user_id: Optional[str] = Query(None), session_id: Optional[str] = Query(None), page: int = Query(1), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    q = select(AiInteraction)
    if user_id: q = q.where(AiInteraction.user_id == uuid.UUID(user_id))
    if session_id: q = q.where(AiInteraction.session_id == uuid.UUID(session_id))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.order_by(AiInteraction.timestamp.desc()).offset((page-1)*20).limit(20))
    items = [{"id": str(i.id), "session_id": str(i.session_id), "role": i.role_at_time, "timestamp": str(i.timestamp), "response_summary": i.response_summary} for i in result.scalars()]
    return {"data": items, "total": total, "page": page}

@router.get("/interactions/stats")
async def interaction_stats(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(AiInteraction.id)))
    by_role = {}
    for role in ["collaborateur", "manager", "rh", "direction", "admin"]:
        count = await db.scalar(select(func.count(AiInteraction.id)).where(AiInteraction.role_at_time == role))
        by_role[role] = count or 0
    return {"data": {"total_interactions": total, "by_role": by_role}}

@router.get("/interactions/{interaction_id}")
async def get_interaction(interaction_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AiInteraction).where(AiInteraction.id == uuid.UUID(interaction_id)))
    i = result.scalar_one_or_none()
    if not i: return {"data": None}
    return {"data": {"id": str(i.id), "session_id": str(i.session_id), "role": i.role_at_time, "timestamp": str(i.timestamp), "query_text": "[chiffré]", "response_summary": i.response_summary}}

@router.get("/unauthorized-attempts")
async def unauthorized_attempts(severity: Optional[str] = Query(None), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    q = select(AiSecurityEvent).where(AiSecurityEvent.event_type == "unauthorized_access")
    if severity: q = q.where(AiSecurityEvent.severity == severity)
    result = await db.execute(q.order_by(AiSecurityEvent.created_at.desc()).limit(50))
    return {"data": [{"id": str(e.id), "severity": e.severity, "created_at": str(e.created_at)} for e in result.scalars()]}

@router.get("/prompt-injections")
async def prompt_injections(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AiSecurityEvent).where(AiSecurityEvent.event_type == "prompt_injection").order_by(AiSecurityEvent.created_at.desc()).limit(50))
    return {"data": [{"id": str(e.id), "severity": e.severity, "created_at": str(e.created_at)} for e in result.scalars()]}

@router.get("/top-queries")
async def top_queries(period: Optional[str] = Query(None), role: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    return {"data": {"note": "Top queries anonymisées — à implémenter avec agrégation", "period": period}}

@router.get("/risk-score")
async def global_risk_score(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    total_events = await db.scalar(select(func.count(AiSecurityEvent.id))) or 0
    critical = await db.scalar(select(func.count(AiSecurityEvent.id)).where(AiSecurityEvent.severity == "critique")) or 0
    score = min(100, (critical * 10) + (total_events * 0.5))
    return {"data": {"risk_score": round(score, 2), "total_events": total_events, "critical_events": critical}}
