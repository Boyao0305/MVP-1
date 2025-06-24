from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional
from database import SessionLocal
from crud.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas2
import models
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, select
import datetime as dt




router = APIRouter(prefix="/api")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




# routers/learning_logs.py  –  NEW VERSION





# ─────────────────────── new response models ──────────────
class AdditionalInformation(schemas2.BaseModel):
    word_book_id: Optional[int]
    daily_goal: int
    learning_proportion: float
    learned_proportion: float
    progression: int
    total: int

class DailyLogsWithInfoOut(schemas2.BaseModel):
    logs: list[schemas2.LearningLogDetailOut]
    additional_information: AdditionalInformation


# ─────────────────────────── route ────────────────────────
@router.get(
    "/daily_learning_logs/{user_id}",
    response_model=DailyLogsWithInfoOut,
    summary="Return today's learning-logs plus user-level info",
)
def read_learning_logs(user_id: int, db: Session = Depends(get_db)):
    # 1️⃣ pick the date (today)
    target_date = dt.date.today()

    # 2️⃣ all logs for that user/date, with word lists eagerly loaded
    logs = (
        db.query(models.Learning_log)
          .options(
              joinedload(models.Learning_log.daily_new_words),
              joinedload(models.Learning_log.daily_review_words),
          )
          .filter(
              models.Learning_log.user_id == user_id,
              models.Learning_log.date == target_date)
        .order_by(models.Learning_log.id.desc())
        .limit(5)
        .all()

    )
    if not logs:
        raise HTTPException(404, "No logs found for that user/date")

    # 3️⃣ pull the user’s learning settings
    setting = (
        db.query(models.Learning_setting)
          .filter(models.Learning_setting.user_id == user_id)
          .first()
    )  # Learning_setting: chosed_word_book_id & daily_goal:contentReference[oaicite:0]{index=0}

    if setting is None:
        # no settings yet ⇒ zero progress, None word_book_id
        info = AdditionalInformation(
            word_book_id=None,
            daily_goal=0,
            learning_proportion=0.0,
            learned_proportion=0.0,
            progression=0,
            total=0,
        )
        return {"logs": logs, "additional_information": info}

    word_book_id = setting.chosed_word_book_id
    daily_goal = setting.daily_goal

    # 4️⃣ gather all word-IDs in that word-book (middle table word_wordbook_links):contentReference[oaicite:1]{index=1}
    word_ids_subq = (
        select(models.Word_wordbook_link.word_id)
        .where(models.Word_wordbook_link.word_book_id == word_book_id)
        .subquery()
    )

    total_words = db.scalar(select(func.count()).select_from(word_ids_subq)) or 0

    # 5️⃣ count this user’s learning / learned words among that set (word_statuss table):contentReference[oaicite:2]{index=2}
    if total_words == 0:
        learning_prop = learned_prop = 0.0
    else:
        learning_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),  # type: ignore[arg-type]
                models.Word_status.status == "learning",
            )
        ) or 0

        learned_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),  # type: ignore[arg-type]
                models.Word_status.status == "learned",
            )
        ) or 0
        progression = (learning_count + learned_count) / 2
        progression = round(progression)
        learning_prop = learning_count / total_words
        learned_prop  = learned_count  / total_words

    info = AdditionalInformation(
        word_book_id=word_book_id,
        daily_goal=daily_goal,
        learning_proportion=learning_prop,
        learned_proportion=learned_prop,
        progression=progression,
        total=total_words,
    )

    return {"logs": logs, "additional_information": info}
