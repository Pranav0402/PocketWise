from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from pwdlib import PasswordHash
from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.secret_key, algorithm=ALGORITHM)


def token_user_id(token: str) -> int:
    try:
        claims=jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM], options={"require_exp": True, "require_sub": True})
        user_id=int(claims["sub"])
        if user_id < 1: raise ValueError("Invalid user id")
        return user_id
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid or expired token") from exc
