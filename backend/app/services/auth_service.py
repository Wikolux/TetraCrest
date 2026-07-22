import hashlib
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.user_repository import UserRepository
from database import SessionLocal
from security import create_access_token, create_refresh_token


class AuthService:
    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()
        self.user_repo = UserRepository(self.db)

    def register(self, username: str, password: str, email: str, full_name: str | None, organization_id: int) -> dict[str, Any]:
        if self.user_repo.get_by_username(username):
            raise HTTPException(status_code=400, detail="Username already registered")
        user = User(
            organization_id=organization_id,
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=self.hash_password(password),
            roles="admin",
            is_superuser=True,
        )
        self.user_repo.create(user)
        return self._token_payload(username)

    def login(self, username: str, password: str) -> dict[str, Any]:
        user = self.user_repo.get_by_username(username)
        if not user or not self.verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return self._token_payload(user.username)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._token_payload("admin")

    def _token_payload(self, username: str) -> dict[str, Any]:
        return {
            "access_token": create_access_token(username),
            "refresh_token": create_refresh_token(username),
            "token_type": "bearer",
        }

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return salt.hex() + ":" + derived.hex()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            salt_hex, derived_hex = hashed_password.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
            return derived.hex() == derived_hex
        except ValueError:
            return False
