from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

import aioboto3
import httpx
from botocore.config import Config
from falkordb.asyncio import FalkorDB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.clustering.community_agent import CommunityAgent
from src.application.ingestion.graph_projector import GraphProjector
from src.application.ingestion.linker import LinkerAgent
from src.application.ingestion.normalizer import NormalizerAgent
from src.application.ingestion.runner import IngestionRunner
from src.application.ingestion.s3_cleanup import S3Cleanup
from src.application.services.file_storages.minio_storage import MinioFileStorage
from src.application.services.graph_storages.falkor_storage import FalkorDBStorage
from src.core.settings import Settings
from src.infrastructure.database.repositories.ingestion_store import IngestionStore
from src.infrastructure.llm.analyst import AnalystAgent
from src.infrastructure.llm.community import CommunityNamingAgent
from src.infrastructure.llm.embeddings import OpenAIEmbeddingClient
from src.pipelines.ingestion.parsing.async_parser import SubprocessParser
from src.pipelines.ingestion.pipeline.pipeline import IngestionPipeline


@dataclass(frozen=True)
class WorkerServices:
    runner: IngestionRunner
    s3_cleanup: S3Cleanup
    community_agent: CommunityAgent


@asynccontextmanager
async def worker_runtime(settings: Settings):
    async with AsyncExitStack() as stack:
        engine = create_async_engine(
            settings.postgres.url, pool_pre_ping=True, pool_size=3, max_overflow=2
        )
        stack.push_async_callback(engine.dispose)
        store = IngestionStore(
            async_sessionmaker(engine, expire_on_commit=False), settings.ingestion
        )
        s3 = await stack.enter_async_context(
            aioboto3.Session().client(
                "s3",
                endpoint_url=settings.minio.endpoint_url,
                aws_access_key_id=settings.minio.access_key.get_secret_value(),
                aws_secret_access_key=settings.minio.secret_key.get_secret_value(),
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=10,
                    read_timeout=60,
                    max_pool_connections=8,
                ),
            )
        )
        http = await stack.enter_async_context(
            httpx.AsyncClient(
                limits=httpx.Limits(
                    max_connections=settings.llm.max_concurrency,
                    max_keepalive_connections=settings.llm.max_concurrency,
                ),
                trust_env=False,
            )
        )
        storage = MinioFileStorage(s3, settings.minio)
        falkor = FalkorDB(
            host=settings.falkordb.host,
            port=settings.falkordb.port,
            username=settings.falkordb.username,
            password=(
                settings.falkordb.password.get_secret_value()
                if settings.falkordb.password
                else None
            ),
            socket_timeout=settings.falkordb.socket_timeout,
            max_connections=settings.falkordb.max_connections,
        )
        stack.push_async_callback(falkor.aclose)
        await falkor.connection.ping()
        graph_storage = FalkorDBStorage(falkor, settings.falkordb.graph_name)
        await graph_storage.ensure_schema(settings.falkordb.embedding_dim)
        pipeline = IngestionPipeline(
            SubprocessParser(settings), AnalystAgent(http, settings.llm)
        )
        embeddings = OpenAIEmbeddingClient(
            http,
            settings.llm,
            settings.falkordb.embedding_dim,
        )
        projector = GraphProjector(
            NormalizerAgent(
                graph_storage,
                embeddings,
                settings.normalization,
                max(
                    1,
                    settings.falkordb.max_connections
                    - settings.ingestion.worker_concurrency,
                ),
            ),
            LinkerAgent(graph_storage),
        )
        community_agent = CommunityAgent(
            graph_storage,
            CommunityNamingAgent(http, settings.llm),
            settings.clustering,
        )
        yield WorkerServices(
            runner=IngestionRunner(
                store,
                storage,
                pipeline,
                projector,
                settings.ingestion,
                settings.app.max_upload_size_mb * 1024 * 1024,
            ),
            s3_cleanup=S3Cleanup(store, storage, settings.ingestion),
            community_agent=community_agent,
        )
