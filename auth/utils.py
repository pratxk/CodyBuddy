"""
Auth utilities — bcrypt + JWT. Mirrored from NourishBot/auth/utils.py, adapted for CodyBuddy.
"""
import os
import warnings
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, status

_JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
if _JWT_SECRET == "dev-secret-change-me":
    warnings.warn("JWT_SECRET not set — using insecure dev default", stacklevel=1)

_ALGORITHM = "HS256"
_EXPIRE_DAYS = 7


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, email: str) -> str:
    # ponytail: re-read from env each call so tests can monkeypatch os.environ
    secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    expire = datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS)
    payload = {"sub": user_id, "email": email, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    try:
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
