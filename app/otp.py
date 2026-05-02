from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random


@dataclass
class OTPRecord:
    code: str
    expires_at: datetime
    verified: bool = False


class OTPManager:
    def __init__(self, ttl_minutes: int = 10) -> None:
        self.ttl_minutes = ttl_minutes
        self._store: dict[str, OTPRecord] = {}

    def generate(self, key: str) -> str:
        code = f"{random.randint(1000, 9999)}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.ttl_minutes)
        self._store[key] = OTPRecord(code=code, expires_at=expires_at)
        return code

    def verify(self, key: str, code: str) -> bool:
        rec = self._store.get(key)
        if not rec:
            return False
        if datetime.now(timezone.utc) > rec.expires_at:
            return False
        if rec.code != str(code).strip():
            return False
        rec.verified = True
        return True

    def get(self, key: str) -> OTPRecord | None:
        return self._store.get(key)
