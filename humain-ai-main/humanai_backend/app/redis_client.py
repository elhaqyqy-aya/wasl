import redis.asyncio as aioredis
from app.config import settings
import json
from typing import Any, Optional

_redis_client: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client

async def cache_get(key: str) -> Optional[Any]:
    r = await get_redis()
    val = await r.get(key)
    if val:
        try:
            return json.loads(val)
        except Exception:
            return val
    return None

async def cache_set(key: str, value: Any, ttl: int = 3600):
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, default=str))

async def cache_delete(key: str):
    r = await get_redis()
    await r.delete(key)

async def cache_delete_pattern(pattern: str):
    r = await get_redis()
    keys = await r.keys(pattern)
    if keys:
        await r.delete(*keys)

async def queue_push(queue: str, payload: dict):
    """Push a job to BullMQ queue (simplified)."""
    r = await get_redis()
    import uuid, time
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "data": payload,
        "timestamp": int(time.time() * 1000),
        "attempts": 0,
    }
    await r.lpush(f"bull:{queue}:wait", json.dumps(job))
    return job_id

async def set_lock(key: str, ttl: int = 30) -> bool:
    r = await get_redis()
    result = await r.set(key, "1", nx=True, ex=ttl)
    return result is True

async def release_lock(key: str):
    r = await get_redis()
    await r.delete(key)

async def alert_push(admin_id: str, alert: dict):
    r = await get_redis()
    await r.lpush(f"alerts:pending:{admin_id}", json.dumps(alert, default=str))
