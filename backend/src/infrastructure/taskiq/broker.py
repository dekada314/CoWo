from taskiq_aio_pika import AioPikaBroker, Queue

from src.core.settings import get_settings

settings = get_settings()

broker = AioPikaBroker(
    url=settings.rabbit.url,
    qos=settings.ingestion.worker_concurrency,
    task_queues=[
        Queue(
            name=settings.ingestion.queue_name,
            arguments={
                "x-max-length": settings.ingestion.queue_max_messages,
                "x-overflow": "reject-publish",
            },
        )
    ],
    dead_letter_queue=Queue(
        name=f"{settings.ingestion.queue_name}.dead",
        arguments={
            "x-message-ttl": 60000,
            "x-max-length": 1000,
        },
    ),
)
