import redis.asyncio as redis
from dependency_injector import resources


class ResourceRedisClient(resources.AsyncResource):
    async def init(
        self,
        host: str,
        port: int,
        db: int,
        password: str,
        ssl: bool,
        max_connections: int,
        socket_timeout: int,
    ):
        client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )
        await client.ping()
        return client

    async def shutdown(self, client: redis.Redis) -> None:
        if client is not None:
            await client.aclose()
