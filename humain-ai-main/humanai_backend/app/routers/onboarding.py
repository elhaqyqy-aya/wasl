from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.onboarding import OnboardingPlan, OnboardingStep, PlanStatus
from app.redis_client import queue_push
from app.utils.audit_logger import log_action
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import uuid

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

class PlanUpdate(BaseModel):
    day_30_calendar: Optional[dict] = None
    status: Optional[str] = None

class StepUpdate(BaseModel):
    completed_at: Optional[datetime] = None

class AlertTrigger(BaseModel):
    step_id: str
    message: str

class GeneratePlan(BaseModel):
    employee_id: str

def plan_to_dict(p: OnboardingPlan) -> dict:
    return {
        "id": str(p.id),
        "employee_id": str(p.employee_id),
        "status": p.status,
        "day_30_calendar": p.day_30_calendar,
        "created_at": str(p.created_at) if p.created_at else None,
    }

def step_to_dict(s: OnboardingStep) -> dict:
    return {
        "id": str(s.id),
        "plan_id": str(s.plan_id),
        "title": s.title,
        "description": s.description,
        "due_date": str(s.due_date) if s.due_date else None,
        "completed_at": str(s.completed_at) if s.completed_at else None,
        "is_alert_triggered": s.is_alert_triggered,
        "day_number": s.day_number,
    }

@router.get("/")
async def list_onboarding_plans(
    status: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(OnboardingPlan)
    if status:
        q = q.where(OnboardingPlan.status == status)
    if employee_id:
        q = q.where(OnboardingPlan.employee_id == uuid.UUID(employee_id))
    result = await db.execute(q)
    return {"data": [plan_to_dict(p) for p in result.scalars()]}

@router.post("/generate")
async def generate_onboarding_plan(
    payload: GeneratePlan,
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    # Verify employee profile is valid
    emp_id = uuid.UUID(payload.employee_id)
    plan = OnboardingPlan(
        id=uuid.uuid4(),
        employee_id=emp_id,
        status=PlanStatus.draft,
        day_30_calendar={"weeks": []},
    )
    db.add(plan)
    await db.flush()
    
    # Trigger AI background agent for 30d plan generation
    await queue_push("onboarding-gen", {"plan_id": str(plan.id), "employee_id": str(emp_id)})
    await log_action(db, user.uid, "GENERATE", "onboarding_plan", str(plan.id))
    
    return {"message": "Génération du plan en cours via l'agent IA", "plan_id": str(plan.id)}

@router.get("/me")
async def get_my_onboarding_plan(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="Profil collaborateur non lié")
        
    result = await db.execute(select(OnboardingPlan).where(OnboardingPlan.employee_id == uuid.UUID(user.employee_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan d'onboarding non trouvé")
        
    return {"data": plan_to_dict(plan)}

@router.get("/{plan_id}")
async def get_onboarding_plan(
    plan_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OnboardingPlan).where(OnboardingPlan.id == uuid.UUID(plan_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan d'onboarding non trouvé")
        
    # Security check: collaborateur can only view their own
    if user.role == "collaborateur" and str(plan.employee_id) != user.employee_id:
        raise HTTPException(status_code=403, detail="Accès interdit")
        
    return {"data": plan_to_dict(plan)}

@router.put("/{plan_id}")
async def update_onboarding_plan(
    plan_id: str,
    payload: PlanUpdate,
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OnboardingPlan).where(OnboardingPlan.id == uuid.UUID(plan_id)))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan d'onboarding non trouvé")
        
    if payload.day_30_calendar is not None:
        plan.day_30_calendar = payload.day_30_calendar
    if payload.status:
        plan.status = PlanStatus(payload.status)
        
    await log_action(db, user.uid, "UPDATE", "onboarding_plan", plan_id)
    return {"data": plan_to_dict(plan)}

@router.get("/{plan_id}/steps")
async def get_onboarding_steps(
    plan_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Retrieve steps
    result = await db.execute(select(OnboardingStep).where(OnboardingStep.plan_id == uuid.UUID(plan_id)).order_by(OnboardingStep.due_date))
    return {"data": [step_to_dict(s) for s in result.scalars()]}

@router.put("/steps/{step_id}")
async def complete_onboarding_step(
    step_id: str,
    payload: StepUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OnboardingStep).where(OnboardingStep.id == uuid.UUID(step_id)))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Étape d'onboarding non trouvée")
        
    step.completed_at = payload.completed_at or datetime.utcnow()
    await log_action(db, user.uid, "COMPLETE", "onboarding_step", step_id)
    return {"data": step_to_dict(step)}

@router.get("/{plan_id}/progress")
async def get_onboarding_progress(
    plan_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pid = uuid.UUID(plan_id)
    total = await db.scalar(select(func.count(OnboardingStep.id)).where(OnboardingStep.plan_id == pid))
    completed = await db.scalar(select(func.count(OnboardingStep.id)).where(OnboardingStep.plan_id == pid).where(OnboardingStep.completed_at != None))
    
    percentage = round((completed / total * 100) if total else 0.0, 2)
    return {"data": {"plan_id": plan_id, "total_steps": total, "completed_steps": completed, "progress_percentage": percentage}}

@router.post("/{plan_id}/alert")
async def trigger_onboarding_alert(
    plan_id: str,
    payload: AlertTrigger,
    user: CurrentUser = Depends(require_roles("rh", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OnboardingStep).where(OnboardingStep.id == uuid.UUID(payload.step_id)))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Étape non trouvée")
        
    step.is_alert_triggered = True
    await log_action(db, user.uid, "ALERT", "onboarding_alert", payload.step_id, {"message": payload.message})
    return {"message": "Alerte déclenchée avec succès", "step_id": payload.step_id}
