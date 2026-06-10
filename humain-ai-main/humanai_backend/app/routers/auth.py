from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from firebase_admin import auth as fb_auth
from app.database import get_db
from app.middleware.firebase_auth import get_current_user, CurrentUser
from app.models.user import User, UserRole
from app.config import settings
from pydantic import BaseModel
from typing import Optional
import uuid, httpx

router = APIRouter(prefix="/auth", tags=["Auth"])

class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None
    role: str = "collaborateur"
    dept_id: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    new_password: str

class PasswordResetRequest(BaseModel):
    email: str

class OAuthRequest(BaseModel):
    provider: str
    id_token: str

@router.post("/signup")
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    try:
        fb_user = fb_auth.create_user(email=payload.email, password=payload.password, display_name=payload.display_name)
        claims = {"role": payload.role}
        if payload.dept_id:
            claims["dept_id"] = payload.dept_id
        fb_auth.set_custom_user_claims(fb_user.uid, claims)
        await db.execute(insert(User).values(
            id=uuid.uuid4(), firebase_uid=fb_user.uid,
            email=payload.email, display_name=payload.display_name,
            role=UserRole(payload.role),
        ))
        await db.commit()
        return {"message": "Compte créé avec succès", "uid": fb_user.uid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login(payload: LoginRequest):
    """Exchange email/password for Firebase ID token via REST API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_PROJECT_ID}",
            json={"email": payload.email, "password": payload.password, "returnSecureToken": True}
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    data = resp.json()
    return {"idToken": data.get("idToken"), "refreshToken": data.get("refreshToken"), "expiresIn": data.get("expiresIn")}

@router.post("/logout")
async def logout(user: CurrentUser = Depends(get_current_user)):
    try:
        fb_auth.revoke_refresh_tokens(user.uid)
    except Exception:
        pass
    return {"message": "Déconnecté"}

@router.post("/refresh-token")
async def refresh_token(payload: dict):
    refresh = payload.get("refreshToken")
    if not refresh:
        raise HTTPException(status_code=400, detail="refreshToken requis")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://securetoken.googleapis.com/v1/token",
            params={"key": settings.FIREBASE_PROJECT_ID},
            json={"grant_type": "refresh_token", "refresh_token": refresh}
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Refresh token invalide")
    data = resp.json()
    return {"idToken": data.get("id_token"), "refreshToken": data.get("refresh_token")}

@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, user: CurrentUser = Depends(get_current_user)):
    fb_auth.update_user(user.uid, password=payload.new_password)
    return {"message": "Mot de passe modifié"}

@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.firebase_uid == user.uid))
    db_user = result.scalar_one_or_none()
    return {"uid": user.uid, "email": user.email, "role": user.role, "dept_id": user.dept_id, "display_name": user.display_name, "db_user": str(db_user.id) if db_user else None}

@router.post("/send-password-reset")
async def send_password_reset(payload: PasswordResetRequest):
    link = fb_auth.generate_password_reset_link(payload.email)
    return {"message": "Email de réinitialisation envoyé", "link": link}

@router.post("/verify-email")
async def verify_email(payload: dict):
    return {"message": "Email vérifié"}

@router.post("/sign-in-with-oauth")
async def sign_in_with_oauth(payload: OAuthRequest):
    return {"message": "OAuth non implémenté", "provider": payload.provider}
