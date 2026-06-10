from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.employee import Employee, EmployeeStatus
from app.models.absence import Absence, AbsenceStatus
from app.models.engagement import DisengagementSignal, EngagementSurvey, SurveyResponse
from app.redis_client import cache_get, cache_set
from typing import Optional
import uuid

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

async def get_cached_or_compute(key: str, ttl: int, compute_fn):
    cached = await cache_get(key)
    if cached: return cached
    result = await compute_fn()
    await cache_set(key, result, ttl=ttl)
    return result

@router.get("/overview")
async def get_overview(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    async def compute():
        headcount = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.actif))
        absences = await db.scalar(select(func.count(Absence.id)).where(Absence.status == AbsenceStatus.approved))
        return {"headcount": headcount or 0, "absences_approved": absences or 0, "period": period}
    return {"data": await get_cached_or_compute(f"kpi:overview:{period}", 3600, compute)}

@router.get("/kpis")
async def get_kpis(scope: Optional[str] = Query(None), dept_id: Optional[str] = Query(None), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    async def compute():
        total = await db.scalar(select(func.count(Employee.id)))
        actif = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.actif))
        return {"total_employees": total or 0, "active_employees": actif or 0, "scope": scope, "dept_id": dept_id, "period": period}
    cache_key = f"kpi:kpis:{scope}:{dept_id}:{period}"
    return {"data": await get_cached_or_compute(cache_key, 3600, compute)}

@router.get("/team")
async def get_team_kpis(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("manager")), db: AsyncSession = Depends(get_db)):
    if not user.dept_id: return {"data": {}}
    team_count = await db.scalar(select(func.count(Employee.id)).where(Employee.department_id == uuid.UUID(user.dept_id)))
    return {"data": {"team_headcount": team_count or 0, "dept_id": user.dept_id}}

@router.get("/headcount")
async def get_headcount(dept_id: Optional[str] = Query(None), start: Optional[str] = Query(None), end: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    q = select(func.count(Employee.id))
    if dept_id: q = q.where(Employee.department_id == uuid.UUID(dept_id))
    count = await db.scalar(q)
    return {"data": {"headcount": count or 0, "dept_id": dept_id, "start": start, "end": end}}

@router.get("/turnover")
async def get_turnover(dept_id: Optional[str] = Query(None), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    inactif = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.inactif))
    total = await db.scalar(select(func.count(Employee.id)))
    rate = round((inactif / total * 100) if total else 0, 2)
    return {"data": {"turnover_rate": rate, "inactive": inactif, "total": total}}

@router.get("/absenteeism")
async def get_absenteeism(scope: Optional[str] = Query(None), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin", "manager")), db: AsyncSession = Depends(get_db)):
    approved = await db.scalar(select(func.count(Absence.id)).where(Absence.status == AbsenceStatus.approved))
    total_emp = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.actif))
    rate = round((approved / total_emp * 100) if total_emp else 0, 2)
    return {"data": {"absenteeism_rate": rate, "approved_absences": approved}}

@router.get("/payroll")
async def get_payroll(period: Optional[str] = Query(None), dept_id: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("direction", "rh", "admin")), db: AsyncSession = Depends(get_db)):
    return {"data": {"note": "Données agrégées — chiffrées en base", "period": period, "dept_id": dept_id}}

@router.get("/age-pyramid")
async def get_age_pyramid(dept_id: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction")), db: AsyncSession = Depends(get_db)):
    return {"data": {"note": "Pyramide des âges — calculée depuis hire_date", "dept_id": dept_id}}

@router.get("/mobility")
async def get_mobility(period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction")), db: AsyncSession = Depends(get_db)):
    return {"data": {"internal_mobility_count": 0, "period": period}}

@router.get("/engagement")
async def get_engagement(scope: Optional[str] = Query(None), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "manager")), db: AsyncSession = Depends(get_db)):
    avg = await db.scalar(select(func.avg(SurveyResponse.score)))
    return {"data": {"engagement_score": round(float(avg), 2) if avg else 0, "scope": scope}}

@router.get("/predictions/turnover")
async def predict_turnover(dept_id: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    inactif = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.inactif)) or 0
    total = await db.scalar(select(func.count(Employee.id))) or 1
    base_rate = inactif / total * 100
    return {"data": {"current_rate": round(base_rate, 2), "n3_projection": round(base_rate * 1.05, 2), "n6_projection": round(base_rate * 1.10, 2), "note": "Projection linéaire — modèle IA à affiner"}}

@router.get("/predictions/headcount")
async def predict_headcount(scenario: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "direction")), db: AsyncSession = Depends(get_db)):
    current = await db.scalar(select(func.count(Employee.id)).where(Employee.status == EmployeeStatus.actif)) or 0
    return {"data": {"current": current, "n3_projection": current, "n6_projection": current, "scenario": scenario}}

@router.post("/predictions/simulate")
async def simulate_scenario(payload: dict, user: CurrentUser = Depends(require_roles("rh", "direction")), db: AsyncSession = Depends(get_db)):
    return {"data": {"scenario_type": payload.get("scenario_type"), "params": payload.get("params"), "result": "Simulation IA — à implémenter avec l'agent"}}

@router.get("/anomalies")
async def detect_anomalies(threshold: Optional[float] = Query(70.0), user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    from app.models.engagement import DisengagementSignal
    result = await db.execute(select(DisengagementSignal).where(DisengagementSignal.risk_score >= threshold))
    signals = [{"employee_id": str(s.employee_id), "risk_score": float(s.risk_score), "risk_level": s.risk_level} for s in result.scalars()]
    return {"data": signals, "threshold": threshold}
