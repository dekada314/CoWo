from pathlib import Path

from pydantic import (
    AmqpDsn,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "postgres"
    migration_host: str | None = None
    port: int = 5432
    user: str
    password: SecretStr
    db: str

    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True
    echo: bool = False

    @computed_field
    @property
    def url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.user,
                password=self.password.get_secret_value(),
                host=self.host,
                port=self.port,
                path=self.db,
            )
        )

    @computed_field
    @property
    def alembic_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.user,
                password=self.password.get_secret_value(),
                host=self.migration_host or self.host,
                port=self.port,
                path=self.db,
            )
        )


class MinioSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MINIO_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )
    host: str = "minio"
    port: int = 9000

    access_key: SecretStr
    secret_key: SecretStr
    bucket: str = "documents"
    secure: bool = False

    @computed_field
    @property
    def endpoint_url(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.host}:{self.port}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None
    ssl: bool = False

    max_connections: int = 10
    socket_timeout: int = 5

    @computed_field
    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        password = (self.password.get_secret_value() if self.password else None) or None
        return str(
            RedisDsn.build(
                scheme=scheme,
                password=password,
                host=self.host,
                port=self.port,
                path=str(self.db),
            )
        )


class FalkorDBSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FALKORDB_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "falkor"
    port: int = 6379
    password: SecretStr | None = None
    username: str | None = None
    graph_name: str = "knowledge_graph_qwen35"

    max_connections: int = 10
    socket_timeout: int = 5

    embedding_dim: int = 1024

    @computed_field
    @property
    def url(self) -> str:
        password = (self.password.get_secret_value() if self.password else None) or None
        return str(
            RedisDsn.build(
                scheme="redis",
                username=self.username,
                password=password,
                host=self.host,
                port=self.port,
            )
        )


class RabbitSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "rabbitmq"
    port: int = 5672
    path: str = ""

    default_user: str
    default_pass: SecretStr

    @computed_field
    @property
    def url(self) -> str:
        return str(
            AmqpDsn.build(
                scheme="amqp",
                username=self.default_user,
                password=self.default_pass.get_secret_value()
                if self.default_pass
                else None,
                host=self.host,
                port=self.port,
                path=self.path,
            )
        )


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    base_url: str = "http://localhost:11434/v1"
    api_key: SecretStr | None = None
    model_analyst: str = "qwen3.5:9b"
    model_responder: str = "qwen3.5:9b"
    reasoning_effort: str = "none"
    timeout_seconds: float = Field(default=600, gt=0)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    max_output_tokens: int = Field(default=2048, ge=256)
    evidence_output_tokens: int = Field(default=512, ge=256)
    responder_output_tokens: int = Field(default=1024, ge=256)
    community_output_tokens: int = Field(default=384, ge=128)
    input_chars: int = Field(default=12000, ge=6000, le=100000)
    max_calls_per_document: int = Field(default=128, ge=1, le=1024)
    model_embedding: str = "qwen3-embedding:0.6b"
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_dimensions: int | None = Field(default=1024, ge=1)


class RetrievalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RETRIEVAL_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    entry_top_k: int = Field(default=5, ge=1, le=50)
    min_entry_similarity: float = Field(default=0.5, ge=0, le=1)
    max_hops: int = Field(default=2, ge=1, le=3)
    beam_width: int = Field(default=20, ge=1, le=200)
    neighbors_per_concept: int = Field(default=8, ge=1, le=50)
    max_cards: int = Field(default=8, ge=1, le=50)
    path_decay: float = Field(default=0.7, gt=0, le=1)


class NormalizationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NORMALIZATION_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    similarity_threshold: float = Field(default=0.92, ge=0, le=1)
    candidates: int = Field(default=3, ge=1, le=20)


class ClusteringSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLUSTERING_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = True
    cron: str = "0 0 * * *"
    max_iterations: int = Field(default=10, ge=1, le=100)
    min_community_size: int = Field(default=2, ge=2, le=1000)
    max_communities: int = Field(default=50, ge=1, le=1000)


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INGESTION_", env_file=ENV_FILE, extra="ignore"
    )

    queue_name: str = "cowo.ingestion.v1"
    queue_max_messages: int = Field(default=10000, ge=1)
    pipeline_version: str = "analyst-v2"
    max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_seconds: int = Field(default=30, ge=1)
    lease_seconds: int = Field(default=120, ge=10)
    heartbeat_seconds: int = Field(default=20, ge=1)
    job_timeout_seconds: int = Field(default=1800, ge=1)
    parse_timeout_seconds: int = Field(default=180, ge=1)
    max_text_chars: int = Field(default=500000, ge=1000)
    worker_concurrency: int = Field(default=2, ge=1, le=32)
    cleanup_enabled: bool = True
    cleanup_grace_hours: int = Field(default=24, ge=1)
    cleanup_batch_size: int = Field(default=500, ge=1, le=10000)
    cleanup_prefix: str = "originals/"

    @model_validator(mode="after")
    def check_lease(self):
        if self.heartbeat_seconds * 3 > self.lease_seconds:
            raise ValueError("lease_seconds must be >= 3 * heartbeat_seconds")
        return self


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: SecretStr = Field(min_length=32)
    algorithm: str = "HS256"
    issuer: str = "cowo"
    audience: str = "cowo-api"
    access_ttl_minutes: int = Field(default=5, ge=1, le=1440)
    refresh_ttl_days: int = Field(default=30, ge=1, le=365)
    clock_skew_seconds: int = Field(default=5, ge=0, le=300)
    refresh_cookie_name: str = "cowo_refresh"
    refresh_cookie_path: str = "/api/v1/auth"
    cookie_secure: bool = False
    cookie_samesite: str = "strict"
    cookie_domain: str | None = None
    redis_prefix: str = "auth:refresh:"

    @model_validator(mode="after")
    def validate_auth(self):
        if self.algorithm != "HS256":
            raise ValueError("only HS256 is supported")
        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("cookie_samesite must be lax, strict or none")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("cookie_secure is required for SameSite=None")
        return self


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    level: str = "INFO"
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    backup_count: int = Field(default=5, ge=1, le=100)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "CoWo"
    version: str = "0.1.0"
    debug: bool = False
    env: str = "local"

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    max_upload_size_mb: int = 50
    max_batch_files: int = Field(default=10, ge=2, le=10)
    allowed_extensions: list[str] = Field(default=["pdf", "docx", "md", "txt"])


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    falkordb: FalkorDBSettings = Field(default_factory=FalkorDBSettings)
    rabbit: RabbitSettings = Field(default_factory=RabbitSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    normalization: NormalizationSettings = Field(default_factory=NormalizationSettings)
    clustering: ClusteringSettings = Field(default_factory=ClusteringSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
