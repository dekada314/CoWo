class DomainError(Exception):
    """Базовое исключение домена."""


class FileStorageError(DomainError):
    """Ошибка инфраструктурного слоя S3 хранилища."""


class GraphStorageError(DomainError):
    """Ошибка инфраструктурного слоя графа."""

class RepositoryError(DomainError):
    """Ошибка слоя работы с БД."""
