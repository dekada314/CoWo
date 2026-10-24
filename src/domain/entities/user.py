from dataclasses import dataclass
from uuid import UUID

from src.domain.value_objects.email import Email


@dataclass
class User:
    id: UUID
    email: Email
    is_active: bool

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True