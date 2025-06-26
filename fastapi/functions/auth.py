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