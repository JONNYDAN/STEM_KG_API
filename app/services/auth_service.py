from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import jwt
import bcrypt
from uuid import UUID

from sqlalchemy.orm import Session
from app.database.postgres_conn import get_session
from app.models.postgres_models import User
from app.config import config

MAX_BCRYPT_PASSWORD_BYTES = 72


class AuthService:
    def __init__(self):
        self.session: Session = get_session()

    def _ensure_password_length(self, password: str) -> None:
        byte_len = len(password.encode("utf-8"))
        if byte_len > MAX_BCRYPT_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be 72 bytes or fewer (got {byte_len} bytes, {len(password)} chars)"
            )

    def _hash_password(self, password: str) -> str:
        self._ensure_password_length(password)
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            self._ensure_password_length(plain_password)
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False

    def get_user_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter(User.username == username).first()

    def create_user(self, payload: Dict[str, Any]) -> User:
        user = User(
            username=payload["username"],
            password_hash=self._hash_password(payload["password"]),
            name=payload.get("name") or payload["username"],
            role=payload.get("role", "user"),
            group_tags=payload.get("group", []),
            photo_url=payload.get("photoURL", ""),
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self._verify_password(password, user.password_hash):
            return None
        return user

    def create_access_token(self, user: User) -> str:
        expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
        payload = {
            "sub": user.username,
            "role": user.role,
            "exp": expire,
        }
        return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)

    def to_user_response(self, user: User) -> Dict[str, Any]:
        return {
            "id": str(user.id),
            "staffCode": str(user.id),
            "name": user.name,
            "username": user.username,
            "role": user.role,
            "group": user.group_tags or [],
            "photoURL": user.photo_url,
        }
