import pytest
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sqlalchemy.types as types

# Mock pgvector for SQLite testing
class MockVector(types.UserDefinedType):
    def __init__(self, dim=None):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"

import pgvector.sqlalchemy
pgvector.sqlalchemy.Vector = MockVector

# Mock ARRAY for SQLite testing
class MockARRAY(types.UserDefinedType):
    def __init__(self, item_type, *args, **kwargs):
        self.item_type = item_type
    def get_col_spec(self, **kw):
        return "TEXT"

import sqlalchemy
import sqlalchemy.types
import sqlalchemy.sql.sqltypes
import sqlalchemy.dialects.postgresql
import sqlalchemy.dialects.postgresql.base

# Mock UUID for SQLite testing to get TEXT affinity instead of NUMERIC
class MockUUID(types.UserDefinedType):
    cache_ok = True
    def __init__(self, as_uuid=True, *args, **kwargs):
        self.as_uuid = as_uuid
    def get_col_spec(self, **kw):
        return "VARCHAR(36)"
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            import uuid
            if isinstance(value, uuid.UUID):
                return str(value)
            return value
        return process
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            import uuid
            if isinstance(value, uuid.UUID):
                return value
            if isinstance(value, float):
                try:
                    return uuid.UUID(int=int(value))
                except Exception:
                    pass
            try:
                return uuid.UUID(value)
            except (ValueError, TypeError, AttributeError):
                try:
                    return uuid.UUID(str(value))
                except Exception:
                    try:
                        return uuid.UUID(int=int(float(value)))
                    except Exception:
                        return value
        return process

sqlalchemy.ARRAY = MockARRAY
sqlalchemy.dialects.postgresql.ARRAY = MockARRAY
sqlalchemy.dialects.postgresql.JSONB = sqlalchemy.JSON

sqlalchemy.types.UUID = MockUUID
sqlalchemy.UUID = MockUUID
sqlalchemy.sql.sqltypes.UUID = MockUUID
sqlalchemy.dialects.postgresql.UUID = MockUUID
sqlalchemy.dialects.postgresql.base.UUID = MockUUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base, get_db
import app.models # Register all models
from app.main import app

# Set testing environment variables
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["APP_ENV"] = "testing"

# Mock Firebase admin SDK
mock_fb_auth = MagicMock()
mock_fb_auth.verify_id_token = MagicMock()
mock_fb_auth.create_user = MagicMock()
mock_fb_auth.set_custom_user_claims = MagicMock()

# Mock Redis Client
mock_redis = AsyncMock()
mock_redis.get = AsyncMock(return_value=None)
mock_redis.set = AsyncMock(return_value=True)
mock_redis.setex = AsyncMock(return_value=True)
mock_redis.delete = AsyncMock(return_value=True)
mock_redis.keys = AsyncMock(return_value=[])

# Override database engine for tests (SQLite in-memory)
from sqlalchemy.pool import StaticPool
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    echo=False,
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(autouse=True)
def mock_external_services():
    with patch("firebase_admin.auth.verify_id_token", mock_fb_auth.verify_id_token), \
         patch("firebase_admin.auth.create_user", mock_fb_auth.create_user), \
         patch("firebase_admin.auth.set_custom_user_claims", mock_fb_auth.set_custom_user_claims), \
         patch("app.redis_client.get_redis", return_value=mock_redis), \
         patch("app.redis_client.cache_get", AsyncMock(return_value=None)), \
         patch("app.redis_client.cache_set", AsyncMock(return_value=True)), \
         patch("app.redis_client.queue_push", AsyncMock(return_value="mock-job-id")):
        yield

@pytest.fixture
def mock_firebase_claims():
    def _set_claims(role="collaborateur", email="user@humanai.com", employee_id=None, dept_id=None):
        mock_fb_auth.verify_id_token.return_value = {
            "uid": "test-uid-123",
            "email": email,
            "role": role,
            "dept_id": dept_id or "00000000-0000-0000-0000-000000000000",
            "employee_id": employee_id or "11111111-1111-1111-1111-111111111111",
            "name": "Test User",
        }
    return _set_claims

@pytest.fixture
async def db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
