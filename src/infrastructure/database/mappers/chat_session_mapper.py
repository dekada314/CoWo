from src.domain.entities.chat_session import ChatSession
from src.infrastructure.database.models.chat_session import ChatSessionORM


class ChatSessionMapper:
    @staticmethod
    def to_domain(orm: ChatSessionORM) -> ChatSession:
        return ChatSession(
            id=orm.id,
            user_id=orm.user_id,
            title=orm.title,
        )

    @staticmethod
    def to_orm(session: ChatSession) -> ChatSessionORM:
        return ChatSessionORM(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
        )

    @staticmethod
    def update_orm(orm: ChatSessionORM, session: ChatSession) -> None:
        orm.title = session.title
