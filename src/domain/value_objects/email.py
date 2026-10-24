import re
from dataclasses import dataclass

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not normalized:
            raise ValueError("Введите Email")
        if len(normalized) > 64:
            raise ValueError("Email слишком длинный (макимум 64 символов)")
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError(f"Неверный формат")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value

    @property
    def local_part(self) -> str:
        return self.value.split("@")[0]

    @property
    def domain(self) -> str:
        return self.value.split("@")[1]
