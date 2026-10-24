import asyncio

from taskiq_aio_pika import AioPikaBroker
from taskiq_redis import RedisAsyncResultBackend

from src.core.settings import get_settings

settings = get_settings()

broker = AioPikaBroker(url=settings.rabbit.url).with_result_backend(
    RedisAsyncResultBackend(redis_url=settings.redis.url)
)


@broker.task
async def ingestion(name: str):
    await asyncio.sleep(2)
    return f"Привет, {name}! Все проблемы решены."
