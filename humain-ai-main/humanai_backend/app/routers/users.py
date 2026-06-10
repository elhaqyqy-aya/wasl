from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from firebase_admin import auth as fb_auth
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser, require_roles
from app.models.user import User, UserRole
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/users", tags=["Users"])

class UserUpdate(BaseModel):
    role: Optional[str] = None
    dept_id: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = None

class RolesUpdate(BaseModel):
    role: str
    dept_id: Optional[str] = None

def user_to_dict(u): return {"id": str(u.id), "email": u.email, "display_name": u.display_name, "role": u.role, "department_id": str(u.department_id) if u.department_id else None, "is_active": u.is_active}

@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.firebase_uid == user.uid))
    u = result.scalar_one_or_none()
    return {"data": user_to_dict(u) if u else {"uid": user.uid, "email": user.email, "role": user.role}}

@router.put("/me")
async def update_me(payload: UserUpdate, user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.firebase_uid == user.uid))
    u = result.scalar_one_or_none()
    if not u: raise HTTPException(404, "Utilisateur non trouvé")
    if payload.display_name: u.display_name = payload.display_name
    return {"data": user_to_dict(u)}

@router.get("/")
async def list_users(page: int = Query(1), limit: int = Query(20), role: Optional[str] = Query(None), dept: Optional[str] = Query(None), user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    q = select(User)
    if role: q = q.where(User.role == role)
    if dept: q = q.where(User.department_id == uuid.UUID(dept))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(q.offset((page-1)*limit).limit(limit))
    return {"data": [user_to_dict(u) for u in result.scalars()], "total": total, "page": page}

@router.post("/")
async def create_user(payload: dict, user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    return {"message": "Utiliser /auth/signup pour créer un utilisateur"}

@router.get("/{user_id}")
async def get_user(user_id: str, user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    u = result.scalar_one_or_none()
    if not u: raise HTTPException(404, "Utilisateur non trouvé")
    return {"data": user_to_dict(u)}

@router.put("/{user_id}")
async def update_user(user_id: str, payload: UserUpdate, user: CurrentUser = Depends(require_roles("admin", "rh")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    u = result.scalar_one_or_none()
    if not u: raise HTTPException(404, "Non trouvé")
    if payload.is_active is not None: u.is_active = payload.is_active
    if payload.role: u.role = UserRole(payload.role)
    return {"data": user_to_dict(u)}

@router.delete("/{user_id}")
async def deactivate_user(user_id: str, user: CurrentUser = Depends(require_roles("admin")), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    u = result.scalar_one_or_none()
    if not u: raise HTTPException(404, "Non trouvé")
    u.is_active = False
    return {"message": "Utilisateur désactivé"}

@router.get("/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    user: CurrentUser = Depends(require_roles("admin", "rh")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "Utilisateur non trouvé")
    try:
        fb_user = fb_auth.get_user(u.firebase_uid)
        custom_claims = fb_user.custom_claims or {}
    except Exception as e:
        custom_claims = {"error": f"Impossible de récupérer les claims Firebase: {str(e)}"}
    
    return {
        "data": {
            "user_id": user_id,
            "database_role": u.role,
            "firebase_custom_claims": custom_claims
        }
    }

@router.put("/{user_id}/roles")
async def update_user_roles(
    user_id: str,
    payload: RolesUpdate,
    user: CurrentUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(404, "Utilisateur non trouvé")
    
    u.role = UserRole(payload.role)
    if payload.dept_id:
        u.department_id = uuid.UUID(payload.dept_id)
        
    try:
        claims = {"role": payload.role}
        if payload.dept_id:
            claims["dept_id"] = payload.dept_id
        fb_auth.set_custom_user_claims(u.firebase_uid, claims)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de mise à jour des claims Firebase: {str(e)}")
        
    return {
        "message": "Rôles mis à jour avec succès",
        "data": user_to_dict(u)
    }
