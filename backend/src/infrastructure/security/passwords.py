import asyncio

from pwdlib import PasswordHash


class PasswordManager:
    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()
        self._dummy_hash = self._password_hash.hash("cowo-invalid-password")

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._password_hash.hash, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        return await asyncio.to_thread(
            self._password_hash.verify,
            password,
            password_hash,
        )

    async def verify_unknown(self, password: str) -> None:
        await self.verify(password, self._dummy_hash)
