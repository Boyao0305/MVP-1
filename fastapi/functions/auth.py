# functions/auth.py — async version (DB I/O via AsyncSession)
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from routers2.phone_number2 import verify_code
import models
import schemas

# Optional: this file originally instantiated a FastAPI app; omitted here since
# routes live elsewhere. If you need it for compatibility, you can re-add it.
# from fastapi import FastAPI
# app = FastAPI()

# =======================
# CONFIG (unchanged)
# =======================
SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2
REFRESH_TOKEN_EXPIRE_DAYS = 7

# In-memory stores (for demo only)
fake_users_db = {
    "alice": {"username": "alice", "password": "secret", "role": "user", "user_id": 1}
}
refresh_token_store: dict[str, dict] = {}

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
# TOKEN UTILS (sync OK)
# =======================

def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    return create_token(
        {"user_id": user_id, "role": role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    refresh_token_store[token] = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return token


def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(user_id=payload["user_id"], role=payload["role"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# =======================
# DEPENDENCY (sync OK)
# =======================

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return verify_token(token)


# =======================
# AUTH HELPERS (async DB)
# =======================
async def authenticate_user(
    db: AsyncSession, username: str, password: str
):
    """Return the user if credentials are valid; otherwise None.
    Uses async SQLAlchemy for DB and runs bcrypt in a thread to avoid blocking.
    """
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    user = result.scalars().first()
    if not user:
        return None

    # bcrypt.checkpw is CPU-bound; run it in a worker thread
    ok = await asyncio.to_thread(
        bcrypt.checkpw, password.encode(), user.hashed_password.encode()
    )
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
    # 0) Ensure the username is unique
    exists = (
        await db.execute(
            select(models.User.id).where(models.User.username == username)
        )
    ).scalar()
    if exists:
        raise ValueError("Username already exists")

    # 1) Validate invitation-code (row-level lock until commit)
    await verify_code(phone_number, code)



    # 2) Create user
    hashed_pw = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    hashed_pw_str = hashed_pw.decode()

    user = models.User(
        username=username,
        hashed_password=hashed_pw_str,
        phone_number=phone_number,
        membership=0,
        consecutive_learning=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 3) Create learning settings
    setting = models.Learning_setting(
        user_id=user.id,
        chosed_word_book_id=chosed_word_book_id,
        average_caiji=average_caiji,
        daily_goal=daily_goal,
    )
    db.add(setting)

    # 4) Mark invitation code as consumed and commit atomically
    # invite.code_status = 1
    # db.add(invite)
    await db.commit()
    await db.refresh(setting)

    return user, setting


async def recover_password(
    db: AsyncSession,
    username: str,
    password: str,
    phone_number: str,
    code: str
):
    # 0) Locate user
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    user = result.scalars().first()
    if not user:
        raise ValueError("user name not valid")
    await verify_code(phone_number, code)

    # Update password
    hashed_pw = await asyncio.to_thread(bcrypt.hashpw, password.encode(), bcrypt.gensalt())
    user.hashed_password = hashed_pw.decode()

    await db.commit()
    await db.refresh(user)
    return user

async def change_number(
    db: AsyncSession,
    user_id: str,
    phone_number: str,
    code: str
):
    # 0) Locate user
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise ValueError("user name not valid")

    await verify_code(phone_number, code)

    # Update password

    user.phone_number = phone_number

    await db.commit()
    await db.refresh(user)
    return user
