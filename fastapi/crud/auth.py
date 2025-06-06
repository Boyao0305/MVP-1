from sqlalchemy.orm import Session
import models
import bcrypt
import schemas
from typing import List, Optional

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not bcrypt.checkpw(password.encode(), user.hashed_password.encode()):
        return None
    return user


def register_user(db: Session, username: str, password: str, phone_number: int,
                  chosed_word_book_id: int, average_caiji: float, daily_goal: int):
    if db.query(models.User).filter(models.User.username == username).first():
        raise ValueError("Username already exists")

    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Create user first
    user = models.User(
        username=username,
        hashed_password=hashed_pw,
        phone_number=phone_number,
        membership=0,
        consecutive_learning=0
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create linked learning setting
    setting = models.Learning_setting(
        user_id=user.id,
        chosed_word_book_id=chosed_word_book_id,
        average_caiji=average_caiji,
        daily_goal=daily_goal
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)

    return user, setting
