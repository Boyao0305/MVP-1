from __future__ import annotations

"""
Auth helpers with Redis-backed access/refresh tokens so all FastAPI workers
share the same short‑term storage.

- Access token: JWT (HS256). We also write a whitelist entry to Redis with TTL
  equal to the JWT expiry (optional but enables server-side revoke).
- Refresh token: random opaque string saved in Redis with TTL (days).

ENV VARS (optional)
-------------------
REDIS_URL           default: redis://redis:6379/0
REDIS_PREFIX        default: auth
STRICT_TOKEN_CHECK  default: 0  (if "1", verify_token also checks Redis whitelist)
SECRET_KEY          default: super-secret-key
ACCESS_TOKEN_MIN    default: 2 (minutes)
REFRESH_TOKEN_DAYS  default: 5 (days)
"""

import os
import asyncio
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import redis  # sync client to keep compatibility with existing sync helpers
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# If you wired this in your project, keep it.
# (Used by register/change_number/recover_password to validate SMS codes.)
from routers2.phone_number2 import verify_code
import models
import schemas

# =======================
# CONFIG
# =======================
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_MIN", "1"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "5"))

# Redis setup (shared across workers)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "auth")
STRICT_TOKEN_CHECK = os.getenv("STRICT_TOKEN_CHECK", "0") == "1"

_redis = redis.from_url(REDIS_URL, decode_responses=True)


def _key(kind: str, token: str) -> str:
    return f"{REDIS_PREFIX}:{kind}:{token}"


# Demo user DB left as-is
fake_users_db = {
    "alice": {"username": "alice", "password": "secret", "role": "user", "user_id": 1}
}

# OAuth2 dependency (unchanged)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# =======================
# SCHEMAS (unchanged)
# =======================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    role: str


# =======================
# TOKEN UTILS (sync-friendly)
# =======================

def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    """Create a JWT and also whitelist it in Redis with TTL.

    Returns the JWT string. This function remains synchronous to preserve
    existing call sites.
    """
    token = create_token({"user_id": user_id, "role": role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    try:
        ttl = ACCESS_TOKEN_EXPIRE_MINUTES * 15
        # Store minimal data; value can be anything (we use JSON for future-proofing)
        _redis.setex(_key("access", token), ttl, json.dumps({"user_id": user_id, "role": role}))
    except Exception:
        # If Redis is unavailable, we still return the JWT (stateless fallback).
        # Consider logging here in your app's logger.
        pass
    return token


def create_refresh_token(user_id: int) -> str:
    """Create an opaque refresh token and save it in Redis with TTL.

    Value stored is the user_id; TTL is REFRESH_TOKEN_EXPIRE_DAYS.
    """
    token = secrets.token_urlsafe(32)
    try:
        ttl = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        _redis.setex(_key("refresh", token), ttl, str(user_id))
    except Exception:
        # If Redis is down, raise explicitly because refresh requires server state.
        raise HTTPException(status_code=500, detail="Refresh token store unavailable")
    return token


def revoke_access_token(token: str) -> None:
    try:
        _redis.delete(_key("access", token))
    except Exception:
        pass


def revoke_refresh_token(token: str) -> None:
    try:
        _redis.delete(_key("refresh", token))
    except Exception:
        pass


def verify_token(token: str) -> TokenData:
    """Verify JWT signature and (optionally) Redis whitelist if STRICT_TOKEN_CHECK=1."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["user_id"])  # may raise KeyError/ValueError
        role = str(payload["role"])        # may raise KeyError

        if STRICT_TOKEN_CHECK:
            try:
                if not _redis.exists(_key("access", token)):
                    raise HTTPException(status_code=401, detail="Token revoked or expired")
            except HTTPException:
                raise
            except Exception:
                # If Redis is down and strict mode is on, be conservative
                raise HTTPException(status_code=503, detail="Auth store unavailable")
        return TokenData(user_id=user_id, role=role)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed token")


# =======================
# DEPENDENCY (sync OK)
# =======================

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return verify_token(token)


# =======================
# AUTH HELPERS (async DB) — unchanged logic
# =======================
async def authenticate_user(db: AsyncSession, username: str, password: str):
    """Return the user if credentials are valid; otherwise None.
    Uses async SQLAlchemy for DB and runs bcrypt in a thread to avoid blocking.
    """
    result = await db.execute(select(models.User).where(models.User.username == username))
    user = result.scalars().first()
    if not user:
        return None

    ok = await asyncio.to_thread(bcrypt.checkpw, password.encode(), user.hashed_password.encode())
    if not ok:
        return None
    return user


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    phone_number: str,
    code: str,
    chosed_word_book_id: int,
    average_caiji: float,
    daily_goal: int,
):
    """Register a new user and create their learning settings.
    Keeps the same return shape: (user, setting).
    """
    # Ensure the username is unique
    exists = (await db.execute(select(models.User.id).where(models.User.username == username))).scalar()
    if exists:
        raise ValueError("Username already exists")

    # Validate SMS code (via routers2.phone_number2.verify_code)
    await verify_code(phone_number, code)

    # Create user
    hashed_pw = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    user = models.User(
        username=username,
        hashed_password=hashed_pw.decode(),
        phone_number=phone_number,
        membership=0,
        consecutive_learning=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create learning settings
    setting = models.Learning_setting(
        user_id=user.id,
        chosed_word_book_id=chosed_word_book_id,
        average_caiji=average_caiji,
        daily_goal=daily_goal,
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)

    return user, setting


async def recover_password(db: AsyncSession, password: str, phone_number: str, code: str):
    result = await db.execute(select(models.User).where(models.User.phone_number == phone_number).order_by(models.User.id.desc())
    .limit(1))
    user = result.scalars().first()
    if not user:
        raise ValueError("user name not valid")

    await verify_code(phone_number, code)

    hashed_pw = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    user.hashed_password = hashed_pw.decode()
    await db.commit()
    await db.refresh(user)
    return user


async def change_number(db: AsyncSession, user_id: str, phone_number: str, code: str):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise ValueError("user name not valid")

    await verify_code(phone_number, code)

    user.phone_number = phone_number
    await db.commit()
    await db.refresh(user)
    return user


# Router endpoint: Redis-backed refresh
# Replace your existing /refresh handler with the one below (same signature),
# and ensure you import the helpers from this module:
#   from functions.auth import _redis, _key, create_access_token, create_refresh_token, Token

# Example (drop into your routers file):
# @router.post("/refresh", response_model=Token)
# async def refresh_token(req: RefreshRequest):
#     logger.info("收到 refresh token 请求")
#     tokenstring = req.refresh_token
#
#     # 1) Read user id bound to this refresh token from Redis (presence implies not expired)
#     try:
#         user_id_str = _redis.get(_key("refresh", tokenstring))
#     except Exception as e:
#         logger.exception(f"Redis 连接失败: {e}")
#         raise HTTPException(status_code=503, detail="Auth store unavailable")
#
#     if not user_id_str:
#         logger.warning(f"无效的 refresh token: {tokenstring}")
#         raise HTTPException(status_code=401, detail="Invalid refresh token")
#
#     # 2) Rotate tokens: issue a new access + refresh, then invalidate the old refresh (single-use)
#     try:
#         user_id = int(user_id_str)
#         new_access = create_access_token(user_id=user_id, role="user")
#         new_refresh = create_refresh_token(user_id)
#         _redis.delete(_key("refresh", tokenstring))
#         logger.success(f"user_id={user_id} refresh token 刷新成功")
#         return Token(access_token=new_access, refresh_token=new_refresh)
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception(f"refresh token 刷新失败: {e}")
#         raise HTTPException(status_code=500, detail="Token refresh failed")
