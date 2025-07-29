from sqlalchemy.orm import Session
import models
import bcrypt
import schemas
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
import secrets

app = FastAPI()

# =======================
# CONFIG
# =======================
SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1
REFRESH_TOKEN_EXPIRE_DAYS = 7

# In-memory stores (for demo only)
fake_users_db = {"alice": {"username": "alice", "password": "secret", "role": "user", "user_id": 1}}
refresh_token_store = {}  # key: refresh_token, value: user_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# =======================
# SCHEMASd
# =======================
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: int
    role: str

# =======================
# UTILS
# =======================
def create_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(user_id: int, role: str):
    return create_token({"user_id": user_id, "role": role}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(user_id: int):
    token = secrets.token_urlsafe(32)
    refresh_token_store[token] = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)}
    return token

def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(user_id=payload["user_id"], role=payload["role"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# =======================
# DEPENDENCY
# =======================
def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    return verify_token(token)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
        return None
    return user


def register_user(
    db: Session,
    username: str,
    password: str,
    # phone_number: int,
    chosed_word_book_id: int,
    average_caiji: float,
    daily_goal: int,
    invitation_code: str,
):
    # ------------------------------------------------
    # 0️⃣  Make sure the username is unique
    # ------------------------------------------------
    if db.query(models.User).filter(models.User.username == username).first():
        raise ValueError("Username already exists")

    # ------------------------------------------------
    # 1️⃣  Validate invitation-code *and* its status
    # ------------------------------------------------
    invite = (
        db.query(models.Invitation_code)
        .filter(models.Invitation_code.code == invitation_code)
        .with_for_update(nowait=True)          # lock the row until commit
        .first()
    )
    if not invite:
        raise ValueError("Invitation code doesn't exist")

    if invite.code_status == 1:                # already consumed?
        raise ValueError("Invitation code used")

    # ------------------------------------------------
    # 2️⃣  Continue with normal user-creation workflow
    # ------------------------------------------------
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user = models.User(
        username=username,
        hashed_password=hashed_pw,
        # phone_number=phone_number,
        membership=0,
        consecutive_learning=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # ------------------------------------------------
    # 3️⃣  Create learning settings linked to the user
    # ------------------------------------------------
    setting = models.Learning_setting(
        user_id=user.id,
        chosed_word_book_id=chosed_word_book_id,
        average_caiji=average_caiji,
        daily_goal=daily_goal,
    )
    db.add(setting)

    # ------------------------------------------------
    # 4️⃣  Mark the invitation code as consumed (status=1)
    #     and commit everything in the same transaction
    # ------------------------------------------------
    invite.code_status = 1
    db.add(invite)          # optional; SQLAlchemy will pick up the dirty row
    db.commit()
    db.refresh(setting)

    return user, setting


def recover_password(
    db: Session,
    username: str,
    password: str,

):
    # ------------------------------------------------
    # 0️⃣  Make sure the username is unique
    # ------------------------------------------------
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise ValueError("user name not valid")


    # ------------------------------------------------
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user.hashed_password = hashed_pw

    db.commit()
    db.refresh(user)


    return user