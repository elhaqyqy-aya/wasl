from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def set_rls_context(session: AsyncSession, user_id: str, role: str, dept_id: str = ""):
    """Inject RLS context into PostgreSQL session."""
    from sqlalchemy import text
    try:
        await session.execute(
            text(f"SET LOCAL app.current_user_id = '{user_id}';")
        )
        await session.execute(
            text(f"SET LOCAL app.current_role = '{role}';")
        )
        await session.execute(
            text(f"SET LOCAL app.current_dept_id = '{dept_id}';")
        )
    except Exception:
        pass
