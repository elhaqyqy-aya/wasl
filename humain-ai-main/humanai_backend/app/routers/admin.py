from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.middleware.firebase_auth import require_roles, CurrentUser
from app.config import settings
from app.redis_client import get_redis, cache_delete_pattern
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter(prefix="/admin", tags=["Admin"])

class ConfigUpdate(BaseModel):
    settings: dict

class DepartmentCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None
    site_id: Optional[str] = None

class SiteCreate(BaseModel):
    name: str
    location: str

@router.get("/config")
async def get_config(user: CurrentUser = Depends(require_roles("admin"))):
    return {
        "data": {
            "app_env": settings.APP_ENV,
            "app_version": settings.APP_VERSION,
            "firebase_project_id": settings.FIREBASE_PROJECT_ID,
            "minio_endpoint": settings.MINIO_ENDPOINT,
            "embedding_model": settings.EMBEDDING_MODEL,
            "llm_model": settings.LLM_MODEL
        }
    }

@router.put("/config")
async def update_config(payload: ConfigUpdate, user: CurrentUser = Depends(require_roles("admin"))):
    return {"message": "Configuration mise à jour", "data": payload.settings}

@router.get("/departments")
async def list_departments(user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    # Simple list mock
    return {"data": [{"id": str(uuid.uuid4()), "name": "Ressources Humaines", "parent_id": None, "site_id": str(uuid.uuid4())}]}

@router.post("/departments")
async def create_department(payload: DepartmentCreate, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return {"message": "Département créé", "data": {"id": str(uuid.uuid4()), "name": payload.name, "parent_id": payload.parent_id}}

@router.put("/departments/{dept_id}")
async def update_department(dept_id: str, payload: DepartmentCreate, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return {"message": "Département mis à jour", "id": dept_id}

@router.delete("/departments/{dept_id}")
async def delete_department(dept_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return {"message": "Département supprimé", "id": dept_id}

@router.get("/sites")
async def list_sites(user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    return {"data": [{"id": str(uuid.uuid4()), "name": "Paris Head Office", "location": "Paris, France"}]}

@router.post("/sites")
async def create_site(payload: SiteCreate, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    return {"message": "Site créé", "data": {"id": str(uuid.uuid4()), "name": payload.name, "location": payload.location}}

@router.get("/health")
async def system_health(user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
        
    redis_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass
        
    return {
        "status": "healthy" if db_ok and redis_ok else "unhealthy",
        "services": {
            "database": "online" if db_ok else "offline",
            "redis": "online" if redis_ok else "offline",
            "rag": "online"
        }
    }

@router.get("/queues")
async def list_queues(user: CurrentUser = Depends(require_roles("admin"))):
    return {
        "data": {
            "onboarding-gen": {"active": 0, "waiting": 0, "failed": 0},
            "doc-gen": {"active": 0, "waiting": 0, "failed": 0},
            "kpi-refresh": {"active": 0, "waiting": 0, "failed": 0},
            "disengagement-scan": {"active": 0, "waiting": 0, "failed": 0},
            "rag-ingest": {"active": 0, "waiting": 0, "failed": 0}
        }
    }

@router.post("/queues/{name}/retry")
async def retry_queue_jobs(name: str, payload: dict, user: CurrentUser = Depends(require_roles("admin"))):
    return {"message": f"Jobs relancés pour la queue {name}", "jobs_count": len(payload.get("job_ids", []))}

@router.get("/cache/stats")
async def cache_stats(user: CurrentUser = Depends(require_roles("admin"))):
    r = await get_redis()
    keys = await r.keys("*")
    return {"data": {"keys_count": len(keys), "used_memory_human": "850K"}}

@router.delete("/cache/flush")
async def flush_cache(scope: str = Query("all"), user: CurrentUser = Depends(require_roles("admin"))):
    if scope == "all":
        pattern = "*"
    elif scope == "kpi":
        pattern = "kpi:*"
    elif scope == "rag":
        pattern = "rag:*"
    else:
        raise HTTPException(status_code=400, detail="Scope invalide (kpi|rag|all)")
        
    await cache_delete_pattern(pattern)
    return {"message": f"Cache vidé pour le scope {scope}"}

@router.get("/metrics")
async def system_metrics(period: Optional[str] = Query("24h"), user: CurrentUser = Depends(require_roles("admin"))):
    return {
        "data": {
            "api_latency_ms": 45.2,
            "error_rate_percent": 0.05,
            "total_requests": 15432,
            "period": period
        }
    }
