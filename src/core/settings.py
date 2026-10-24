from pathlib import Path

from pydantic import (
    AmqpDsn,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    computed_field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "postgres"
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
                host="localhost",
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

    root_user: str
    root_password: str
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
    password: SecretStr
    ssl: bool = False

    max_connections: int = 10
    socket_timeout: int = 5

    @computed_field
    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        password = self.password.get_secret_value() if self.password else None
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
    password: SecretStr
    username: str
    graph_name: str = "knowledge_graph"

    max_connections: int = 10
    socket_timeout: int = 5

    embedding_dim: int = 768
    vector_index_name: str = "concept_embedding_idx"

    @computed_field
    @property
    def url(self) -> str:
        password = self.password.get_secret_value() if self.password else None
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
        extra="ignore",
    )

    # provider: str = "openrouter"
    # api_key: SecretStr | None = None
    # base_url: str | None = None

    # model_analyst: str = "google/gemma-3-12b-it"
    # model_responder: str = "google/gemma-3-12b-it"
    # model_embedding: str = "intfloat/multilingual-e5-small"

    # temperature: float = 0.1
    # max_tokens: int = 2048
    # timeout: int = 60
    # max_retries: int = 3


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # secret_key: SecretStr
    # algorithm: str
    # access_token_expire_minutes: int = 60 * 24
    # refresh_token_expire_days: int = 30


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
    allowed_extensions: list[str] = Field(default=["pdf", "md", "txt"])


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
    llm: LLMSettings = Field(default_factory=LLMSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
