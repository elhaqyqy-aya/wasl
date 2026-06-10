from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.engagement import EngagementSurvey, SurveyResponse, AnnualReview, DisengagementSignal, RiskLevel
from app.redis_client import queue_push
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

router = APIRouter(prefix="/engagement", tags=["Engagement"])

class SurveyCreate(BaseModel):
    title: str
    questions: List[dict]
    anonymous: bool = False

class ReviewCreate(BaseModel):
    employee_id: str
    rating: float
    workload_score: int
    notes: Optional[str] = None

def survey_to_dict(s): return {"id": str(s.id), "title": s.title, "is_anonymous": s.is_anonymous, "created_at": str(s.created_at)}
def review_to_dict(r): return {"id": str(r.id), "employee_id": str(r.employee_id), "rating": float(r.rating) if r.rating else None, "workload_score": r.workload_score, "review_date": str(r.review_date)}
def signal_to_dict(s): return {"id": str(s.id), "employee_id": str(s.employee_id), "risk_score": float(s.risk_score), "risk_level": s.risk_level, "signals": s.signals, "action_plan": s.action_plan, "computed_at": str(s.computed_at)}

# ---- Surveys ----
@router.get("/surveys/")
async def list_surveys(page: int = Query(1), period: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EngagementSurvey).offset((page-1)*20).limit(20))
    return {"data": [survey_to_dict(s) for s in result.scalars()], "page": page}

@router.post("/surveys/")
async def create_survey(payload: SurveyCreate, user: CurrentUser = Depends(require_roles("rh")), db: AsyncSession = Depends(get_db)):
    survey = EngagementSurvey(id=uuid.uuid4(), title=payload.title, questions=payload.questions, is_anonymous=payload.anonymous, created_by=uuid.uuid4())
    db.add(survey)
    await db.flush()
    return {"data": survey_to_dict(survey)}

@router.get("/surveys/{survey_id}")
async def get_survey(survey_id: str, user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EngagementSurvey).where(EngagementSurvey.id == uuid.UUID(survey_id)))
    s = result.scalar_one_or_none()
    if not s: raise HTTPException(404, "Survey non trouvé")
    return {"data": {**survey_to_dict(s), "questions": s.questions}}

@router.post("/surveys/{survey_id}/respond")
async def respond_survey(survey_id: str, payload: dict, user: CurrentUser = Depends(require_roles("collaborateur")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EngagementSurvey).where(EngagementSurvey.id == uuid.UUID(survey_id)))
    survey = result.scalar_one_or_none()
    if not survey: raise HTTPException(404, "Survey non trouvé")
    answers = payload.get("answers", [])
    score = sum(a.get("value", 0) for a in answers) // max(len(answers), 1) if answers else 0
    response = SurveyResponse(id=uuid.uuid4(), survey_id=uuid.UUID(survey_id), employee_id=uuid.UUID(user.employee_id) if user.employee_id and not survey.is_anonymous else None, answers={"answers": answers}, score=score)
    db.add(response)
    return {"message": "Réponse enregistrée", "score": score}

@router.get("/surveys/{survey_id}/results")
async def survey_results(survey_id: str, user: CurrentUser = Depends(require_roles("rh", "direction", "admin")), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(SurveyResponse.id)).where(SurveyResponse.survey_id == uuid.UUID(survey_id)))
    avg_score = await db.scalar(select(func.avg(SurveyResponse.score)).where(SurveyResponse.survey_id == uuid.UUID(survey_id)))
    return {"data": {"total_responses": total, "avg_score": round(float(avg_score), 2) if avg_score else 0}}

# ---- Annual Reviews ----
@router.get("/annual-reviews/")
async def list_reviews(dept_id: Optional[str] = Query(None), year: Optional[int] = Query(None), user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnnualReview))
    return {"data": [review_to_dict(r) for r in result.scalars()]}

@router.get("/annual-reviews/team")
async def list_team_reviews(year: Optional[int] = Query(None), user: CurrentUser = Depends(require_roles("manager")), db: AsyncSession = Depends(get_db)):
    from app.models.employee import Employee
    emp_ids_q = select(Employee.id).where(Employee.department_id == uuid.UUID(user.dept_id) if user.dept_id else False)
    emp_ids = (await db.execute(emp_ids_q)).scalars().all()
    result = await db.execute(select(AnnualReview).where(AnnualReview.employee_id.in_(emp_ids)))
    return {"data": [review_to_dict(r) for r in result.scalars()]}

@router.post("/annual-reviews/")
async def create_review(payload: ReviewCreate, user: CurrentUser = Depends(require_roles("manager", "rh")), db: AsyncSession = Depends(get_db)):
    review = AnnualReview(id=uuid.uuid4(), employee_id=uuid.UUID(payload.employee_id), reviewer_id=uuid.uuid4(), rating=payload.rating, workload_score=payload.workload_score, notes=payload.notes)
    db.add(review)
    await db.flush()
    return {"data": review_to_dict(review)}

@router.put("/annual-reviews/{review_id}")
async def update_review(review_id: str, payload: dict, user: CurrentUser = Depends(require_roles("manager", "rh")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AnnualReview).where(AnnualReview.id == uuid.UUID(review_id)))
    r = result.scalar_one_or_none()
    if not r: raise HTTPException(404, "Entretien non trouvé")
    if "rating" in payload: r.rating = payload["rating"]
    if "notes" in payload: r.notes = payload["notes"]
    return {"data": review_to_dict(r)}

# ---- Disengagement ----
@router.get("/disengagement/signals")
async def list_signals(risk_level: Optional[str] = Query(None), dept_id: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("rh", "admin", "qvt")), db: AsyncSession = Depends(get_db)):
    q = select(DisengagementSignal)
    if risk_level: q = q.where(DisengagementSignal.risk_level == risk_level)
    result = await db.execute(q.order_by(DisengagementSignal.risk_score.desc()))
    return {"data": [signal_to_dict(s) for s in result.scalars()]}

@router.get("/disengagement/signals/team")
async def list_team_signals(user: CurrentUser = Depends(require_roles("manager")), db: AsyncSession = Depends(get_db)):
    from app.models.employee import Employee
    if not user.dept_id: return {"data": []}
    emp_ids = (await db.execute(select(Employee.id).where(Employee.department_id == uuid.UUID(user.dept_id)))).scalars().all()
    result = await db.execute(select(DisengagementSignal).where(DisengagementSignal.employee_id.in_(emp_ids)))
    return {"data": [signal_to_dict(s) for s in result.scalars()]}

@router.get("/disengagement/signals/{signal_id}")
async def get_signal(signal_id: str, user: CurrentUser = Depends(require_roles("rh", "manager", "qvt")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DisengagementSignal).where(DisengagementSignal.id == uuid.UUID(signal_id)))
    s = result.scalar_one_or_none()
    if not s: raise HTTPException(404, "Signal non trouvé")
    return {"data": signal_to_dict(s)}

@router.post("/disengagement/scan")
async def trigger_scan(payload: dict = {}, user: CurrentUser = Depends(require_roles("rh", "admin")), db: AsyncSession = Depends(get_db)):
    await queue_push("disengagement-scan", {"dept_id": payload.get("dept_id"), "full_scan": payload.get("full_scan", False)})
    return {"message": "Scan de désengagement lancé"}

@router.put("/disengagement/signals/{signal_id}/action")
async def update_action_plan(signal_id: str, payload: dict, user: CurrentUser = Depends(require_roles("rh", "manager")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DisengagementSignal).where(DisengagementSignal.id == uuid.UUID(signal_id)))
    s = result.scalar_one_or_none()
    if not s: raise HTTPException(404, "Non trouvé")
    s.action_plan = payload.get("action_plan", {})
    return {"data": signal_to_dict(s)}
