# routers/learning_log_outline.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models

from openai import AsyncOpenAI,OpenAI
from database import SessionLocal# ← your pydantic models

from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional, List
from database import SessionLocal
from functions.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas2

from models import Learning_log, User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, select
import datetime as dt
from models import Dictionary
import models                                # ← your ORM models
from functions.new_session import (                    # ← orchestration helpers
    create_five_learning_logs,
    assign_daily_new_words,
    assign_daily_review_words,
    generate_outlines_for_date_async,
)
from functions.cefr import compare_lists_to_text
from functions.cefr2 import update_average_caiji_for_user
import json, os, asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import Saved_phrase, User

       # ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")

class SavedPhraseCreate(BaseModel):
    user_id: int
    content: str
    translation: str
    explication: str

@router.post("/save_phrase")
def save_phrase(data: SavedPhraseCreate, db: Session = Depends(get_db)):
    # Optional: Validate that the user exists
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    saved_phrase = Saved_phrase(
        user_id=data.user_id,
        content=data.content,
        translation=data.translation,
        explication=data.explication,
        category="phrase"
    )
    db.add(saved_phrase)
    db.commit()
    db.refresh(saved_phrase)

    return {
        "message": "Phrase saved successfully",
        "saved_phrase_id": saved_phrase.id
    }


class SavedPhraseResponse(BaseModel):
    content: str
    translation: Optional[str]
    explication: Optional[str]

@router.get("/user_phrases/{user_id}", response_model=List[SavedPhraseResponse])
def get_user_phrases(user_id: int, db: Session = Depends(get_db)):
    # Optional: check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    phrases = (
        db.query(Saved_phrase)
        .filter(Saved_phrase.user_id == user_id, Saved_phrase.category == "phrase")
        .all()
    )

    return phrases
class LearningLogResponse(BaseModel):
    log_id: int
    daily_new_words: List[str]
    daily_review_words: List[str]
    english_title: Optional[str]
    chinese_title: Optional[str]
    article: Optional[str]

# ── Endpoint ────────────────────────────────────────────────────────────────────
@router.get("/all_learning_logs/{user_id}", response_model=List[LearningLogResponse])
def get_learning_logs(user_id: int, db: Session = Depends(get_db)):
    # (optional) Ensure the user exists
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")

    logs = (
        db.query(Learning_log)
        .filter(Learning_log.user_id == user_id,
                Learning_log.artical.isnot(None)
                )
        .all()
    )

    # Construct the response
    result: List[LearningLogResponse] = []
    for log in logs:
        result.append(
            LearningLogResponse(
                log_id=log.id,
                daily_new_words=[w.word for w in log.daily_new_words],
                daily_review_words=[w.word for w in log.daily_review_words],
                english_title=log.english_title,
                chinese_title=log.chinese_title,
                article=log.artical,  # DB column is `artical`
            )
        )

    return result
