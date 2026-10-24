import re

from pydantic import BaseModel, EmailStr, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Пароль должен содержать от 8 символов")
        if not re.search(r"[A-ZА-Я]", value):
            raise ValueError(
                "Пароль должен содержать хотя бы одну заглавную букву (A-Z)."
            )
        if not re.search(r"[a-zа-я]", value):
            raise ValueError(
                "Пароль должен содержать хотя бы одну строчную букву (a-z)."
            )
        if not re.search(r"[0-9]", value):
            raise ValueError(
                "Пароль должен содержать хотя бы одну цифру (0-9)."
            )
        return value
