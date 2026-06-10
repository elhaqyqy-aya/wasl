import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, set_rls_context
from app.config import settings
from dataclasses import dataclass
from typing import Optional
import os

_firebase_app = None

def init_firebase():
    global _firebase_app
    if _firebase_app is None:
        cred_path = settings.FIREBASE_SERVICE_ACCOUNT_PATH
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        else:
            # Dev mode without service account
            _firebase_app = firebase_admin.initialize_app()

VALID_ROLES = ["collaborateur", "manager", "rh", "direction", "admin", "qvt"]

@dataclass
class CurrentUser:
    uid: str
    email: str
    role: str
    dept_id: str
    employee_id: Optional[str] = None
    display_name: Optional[str] = None

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    token = credentials.credentials
    try:
        decoded = auth.verify_id_token(token)
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase invalide ou expiré")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token Firebase expiré")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Erreur d'authentification: {str(e)}")

    role = decoded.get("role")
    dept_id = decoded.get("dept_id", "")
    employee_id = decoded.get("employee_id")

    if not role or role not in VALID_ROLES:
        raise HTTPException(status_code=403, detail="Rôle non assigné ou invalide")

    from sqlalchemy import text
    try:
        await db.execute(text(f"SET LOCAL app.current_user_id = '{decoded['uid']}';"))
        await db.execute(text(f"SET LOCAL app.current_role = '{role}';"))
        await db.execute(text(f"SET LOCAL app.current_dept_id = '{dept_id}';"))
    except Exception:
        pass

    return CurrentUser(
        uid=decoded["uid"],
        email=decoded.get("email", ""),
        role=role,
        dept_id=dept_id,
        employee_id=employee_id,
        display_name=decoded.get("name"),
    )

def require_roles(*roles: str):
    """Dependency factory to restrict endpoint access by role."""
    async def checker(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Accès refusé. Rôles requis: {', '.join(roles)}"
            )
        return user
    return checker

# Shorthand dependencies
get_rh_or_admin = require_roles("rh", "admin")
get_admin = require_roles("admin")
get_rh_admin_direction = require_roles("rh", "admin", "direction")
get_manager_or_above = require_roles("manager", "rh", "admin", "direction")
