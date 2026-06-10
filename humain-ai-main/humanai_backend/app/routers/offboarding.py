from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.offboarding import OffboardingWorkflow, OffboardingStep, DepartureReason, WorkflowStatus, StepType
from app.redis_client import queue_push
from app.utils.audit_logger import log_action
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import uuid

router = APIRouter(prefix="/offboarding", tags=["Offboarding"])

class OffboardingInitiate(BaseModel):
    employee_id: str
    departure_reason: str
    departure_date: date

class StepUpdate(BaseModel):
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

def workflow_to_dict(w: OffboardingWorkflow) -> dict:
    return {
        "id": str(w.id),
        "employee_id": str(w.employee_id),
        "departure_reason": w.departure_reason,
        "departure_date": str(w.departure_date),
        "status": w.status,
        "knowledge_transfer_doc_id": str(w.knowledge_transfer_doc_id) if w.knowledge_transfer_doc_id else None,
        "created_at": str(w.created_at) if w.created_at else None,
    }

def step_to_dict(s: OffboardingStep) -> dict:
    return {
        "id": str(s.id),
        "workflow_id": str(s.workflow_id),
        "step_type": s.step_type,
        "title": s.title,
        "assigned_to": str(s.assigned_to) if s.assigned_to else None,
        "completed_at": str(s.completed_at) if s.completed_at else None,
        "notes": s.notes,
    }

@router.get("/")
async def list_offboarding_workflows(
    status: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    q = select(OffboardingWorkflow)
    if status:
        q = q.where(OffboardingWorkflow.status == status)
    if employee_id:
        q = q.where(OffboardingWorkflow.employee_id == uuid.UUID(employee_id))
    result = await db.execute(q)
    return {"data": [workflow_to_dict(w) for w in result.scalars()]}

@router.post("/initiate")
async def initiate_offboarding(
    payload: OffboardingInitiate,
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    workflow = OffboardingWorkflow(
        id=uuid.uuid4(),
        employee_id=uuid.UUID(payload.employee_id),
        departure_reason=DepartureReason(payload.departure_reason),
        departure_date=payload.departure_date,
        status=WorkflowStatus.initiated,
    )
    db.add(workflow)
    await db.flush()
    
    # Push job to BullMQ queue for AI background compliance setup
    await queue_push("offboarding-gen", {"workflow_id": str(workflow.id), "employee_id": payload.employee_id})
    await log_action(db, user.uid, "INITIATE", "offboarding_workflow", str(workflow.id))
    
    return {"data": workflow_to_dict(workflow), "message": "Workflow d'offboarding initié"}

@router.get("/{workflow_id}")
async def get_offboarding_workflow(
    workflow_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingWorkflow).where(OffboardingWorkflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow non trouvé")
    return {"data": workflow_to_dict(workflow)}

@router.get("/{workflow_id}/steps")
async def get_offboarding_steps(
    workflow_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingStep).where(OffboardingStep.workflow_id == uuid.UUID(workflow_id)).order_by(OffboardingStep.step_type))
    return {"data": [step_to_dict(s) for s in result.scalars()]}

@router.put("/steps/{step_id}")
async def update_offboarding_step(
    step_id: str,
    payload: StepUpdate,
    user: CurrentUser = Depends(require_roles("rh", "manager", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingStep).where(OffboardingStep.id == uuid.UUID(step_id)))
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Étape d'offboarding non trouvée")
        
    step.completed_at = payload.completed_at or datetime.utcnow()
    if payload.notes:
        step.notes = payload.notes
        
    await log_action(db, user.uid, "COMPLETE", "offboarding_step", step_id)
    return {"data": step_to_dict(step)}

@router.post("/{workflow_id}/transferdoc")
async def generate_transfer_document(
    workflow_id: str,
    user: CurrentUser = Depends(require_roles("rh")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingWorkflow).where(OffboardingWorkflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow d'offboarding non trouvé")
        
    # Trigger background document generation
    await log_action(db, user.uid, "GENERATE_TRANSFER", "offboarding_workflow", workflow_id)
    return {"message": "Génération de la synthèse de transfert IA lancée"}

@router.get("/{workflow_id}/checklist")
async def get_offboarding_checklist(
    workflow_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingStep).where(OffboardingStep.workflow_id == uuid.UUID(workflow_id)))
    steps = result.scalars().all()
    
    checklist = {
        "materiel": [step_to_dict(s) for s in steps if s.step_type == StepType.materiel],
        "acces": [step_to_dict(s) for s in steps if s.step_type == StepType.acces],
        "admin": [step_to_dict(s) for s in steps if s.step_type == StepType.admin],
        "transfert": [step_to_dict(s) for s in steps if s.step_type == StepType.transfert],
        "cloture": [step_to_dict(s) for s in steps if s.step_type == StepType.cloture],
    }
    return {"data": checklist}

@router.post("/{workflow_id}/complete")
async def complete_offboarding(
    workflow_id: str,
    user: CurrentUser = Depends(require_roles("rh", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OffboardingWorkflow).where(OffboardingWorkflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow non trouvé")
        
    workflow.status = WorkflowStatus.completed
    await log_action(db, user.uid, "COMPLETE", "offboarding_workflow", workflow_id)
    return {"message": "Offboarding clôturé avec succès", "data": workflow_to_dict(workflow)}
