from enum import IntEnum

from redis.asyncio import Redis

from src.core.settings import AuthSettings


class RotationResult(IntEnum):
    MISSING = 0
    ROTATED = 1
    REUSED = -1


class RefreshSessionStore:
    _ROTATE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if not current then
    return 0
end
if current ~= ARGV[1] then
    redis.call('DEL', KEYS[1])
    return -1
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""

    def __init__(self, client: Redis, config: AuthSettings) -> None:
        self._client = client
        self._prefix = config.redis_prefix

    async def create(self, session_id: str, jti: str, ttl: int) -> None:
        await self._client.set(self._key(session_id), jti, ex=ttl)

    async def rotate(
        self,
        session_id: str,
        current_jti: str,
        next_jti: str,
        ttl: int,
    ) -> RotationResult:
        result = await self._client.eval(
            self._ROTATE_SCRIPT,
            1,
            self._key(session_id),
            current_jti,
            next_jti,
            ttl,
        )
        return RotationResult(result)

    async def revoke(self, session_id: str) -> None:
        await self._client.delete(self._key(session_id))

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"
