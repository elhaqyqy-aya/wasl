from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert, select
from app.models.audit import AuditLog
from app.models.user import User
import uuid

async def log_action(
    db: AsyncSession,
    user_id: str,
    action: str,
    entity_type: str = None,
    entity_id: str = None,
    details: dict = None,
    ip_address: str = None
):
    db_user_id = None
    if user_id:
        try:
            db_user_id = uuid.UUID(user_id)
        except ValueError:
            # Resolve Firebase UID to DB User ID
            result = await db.execute(select(User.id).where(User.firebase_uid == user_id))
            db_user_id = result.scalar_one_or_none()

    db_entity_id = None
    if entity_id:
        try:
            db_entity_id = uuid.UUID(entity_id)
        except ValueError:
            pass

    await db.execute(insert(AuditLog).values(
        id=uuid.uuid4(),
        user_id=db_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=db_entity_id,
        details=details or {},
        ip_address=ip_address,
    ))
