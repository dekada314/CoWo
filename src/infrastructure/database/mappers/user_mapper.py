from src.domain.entities.user import User
from src.domain.value_objects.email import Email
from src.infrastructure.database.models.user import UserORM


class UserMapper:
    @staticmethod
    def to_domain(orm: UserORM) -> User:
        return User(
            id=orm.id,
            email=Email(orm.email),
            is_active=orm.is_active,
        )

    @staticmethod
    def to_orm(user: User, password_hash: str) -> UserORM:
        return UserORM(
            id=user.id,
            email=str(user.email),
            password_hash=password_hash,
            is_active=user.is_active,
        )

    @staticmethod
    def update_orm(orm: UserORM, user: User) -> None:
        orm.email = str(user.email)
        orm.is_active = user.is_active
