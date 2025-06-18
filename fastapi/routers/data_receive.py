from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional
from database import SessionLocal
from crud.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas2
import models
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
import datetime as dt




router = APIRouter(prefix="/api")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/receive_data")
def receive_data(data: schemas2.Receive_data, db: Session = Depends(get_db)):
    return data



@router.get(
    "/daily_learning_logs/{user_id}",
    response_model=list[schemas2.LearningLogDetailOut],
    summary="Return today's (or specified) learning-log rows for a user",
)
def read_learning_logs(
    user_id: int,
    date: Optional[str] = "2025-06-18",                # ← query-param, optional
    db: Session = Depends(get_db),
):
    # 1️⃣  pick the date
    if date is None:
        # target_date = dt.date.today()
        target_date = dt.date.today()
    else:
        try:
            target_date = dt.date.fromisoformat(date)
        except ValueError:
            raise HTTPException(422, "date must be YYYY-MM-DD")

    # 2️⃣  fetch rows with word lists pre-loaded
    logs = (
        db.query(models.Learning_log)
          .options(
              joinedload(models.Learning_log.daily_new_words),
              joinedload(models.Learning_log.daily_review_words),
          )
          .filter(
              models.Learning_log.user_id == user_id,
              models.Learning_log.date == target_date,
          )
          .all()
    )
    if not logs:
        raise HTTPException(404, "No logs found for that user/date")

    return logs