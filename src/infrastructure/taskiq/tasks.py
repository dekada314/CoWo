from src.infrastructure.taskiq.broker import broker


@broker.task
async def ingestion(s3_file_key: str) -> str:
    pass
