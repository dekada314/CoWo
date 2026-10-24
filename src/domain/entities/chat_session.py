from dataclasses import dataclass
from uuid import UUID


@dataclass
class ChatSession:
    id: UUID
    user_id: UUID
    title: str | None = None

    def rename(self, new_title: str) -> None:
        if not new_title.strip():
            raise ValueError("Title cannot be empty")
        self.title = new_title[:512]

    def auto_title_from_question(self, question: str) -> None:
        if self.title is not None:
            return
        self.title = question.strip()[:50]
