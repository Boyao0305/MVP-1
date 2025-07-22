# routers/learning_log_outline.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models
import datetime
from pydantic import BaseModel, conint
from openai import AsyncOpenAI,OpenAI
from database import SessionLocal# ← your pydantic models
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional, List
from database import SessionLocal
from functions.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas2

from models import Learning_log, User, Daily_new_word_link, Daily_review_word_link
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
from models import Word, Learning_log
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
    log_id : int
    note : Optional[str]=None
class SavedPhraseResponse(BaseModel):
    content: str
    translation: Optional[str]
    explication: Optional[str]
    log_id : Optional[int]=None
    note : Optional[str]=None
class LearningLogResponse(BaseModel):
    log_id: int
    daily_new_words: List[str]
    daily_review_words: List[str]
    english_title: Optional[str]
    chinese_title: Optional[str]
    article: Optional[str]
    date: Optional[datetime.date] = None
class LearningLogSummary(BaseModel):
    log_id: int
    english_title: Optional[str]
    chinese_title: Optional[str]
    date: Optional[date]
    phrases: List[SavedPhraseResponse]
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
        category="phrase",
        log_id=data.log_id,


    )
    db.add(saved_phrase)
    db.commit()
    db.refresh(saved_phrase)

    return {
        "message": "Phrase saved successfully",
        "saved_phrase_id": saved_phrase.id
    }
@router.post("/save_phrase_note")
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
        category="phrase",
        log_id=data.log_id,
        note=data.note,
    )
    db.add(saved_phrase)
    db.commit()
    db.refresh(saved_phrase)

    return {
        "message": "Phrase saved successfully",
        "saved_phrase_id": saved_phrase.id
    }
class SavedPhraseDelete(BaseModel):
    user_id: int
    saved_phrase_id: int

# ── DELETE endpoint ───────────────────────────────────────────────────────────
@router.delete("/unsave_phrase")
def delete_saved_phrase(data: SavedPhraseDelete, db: Session = Depends(get_db)):
    phrase = (
        db.query(Saved_phrase)
        .filter(
            Saved_phrase.id == data.saved_phrase_id,      # primary-key column:contentReference[oaicite:0]{index=0}
            Saved_phrase.user_id == data.user_id          # ownership check:contentReference[oaicite:1]{index=1}
        )
        .first()
    )
    if not phrase:
        raise HTTPException(status_code=404, detail="Saved phrase not found")

    db.delete(phrase)
    db.commit()

    return {"message": "Phrase unsaved (deleted) successfully", "saved_phrase_id": data.saved_phrase_id}

@router.get(
    "/saved_phrases/{user_id}",
    response_model=List[LearningLogSummary],
)
def get_user_phrases(user_id: int, db: Session = Depends(get_db)):
    # ensure the user exists
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")

    # all log-ids that have *phrase* entries for this user
    log_ids_subq = (
        db.query(Saved_phrase.log_id)
        .filter(
            Saved_phrase.user_id == user_id,
            Saved_phrase.category == "phrase",
            Saved_phrase.log_id.isnot(None)
        )
        .distinct()
        .subquery()
    )

    # fetch only those learning logs
    logs = db.query(Learning_log).filter(Learning_log.id.in_(log_ids_subq)).all()

    result: List[LearningLogSummary] = []
    for log in logs:
        phrases = (
            db.query(Saved_phrase)
            .filter(
                Saved_phrase.user_id == user_id,
                Saved_phrase.log_id == log.id,
                Saved_phrase.category == "phrase",
            )
            .all()
        )

        result.append(
            LearningLogSummary(
                log_id=log.id,
                english_title=log.english_title,
                chinese_title=log.chinese_title,
                date=log.date,
                phrases=[
                    SavedPhraseResponse(
                        content=p.content,
                        translation=p.translation,
                        explication=p.explication,
                        log_id=p.log_id,
                        note=None,
                    )
                    for p in phrases
                ],
            )
        )

    return result

class LearningLogWithPhrases(LearningLogResponse):
    phrases: List[SavedPhraseResponse]
@router.get("/save_article/{log_id}")
def save_article(log_id: int, db: Session = Depends(get_db)):
    log = (
        db.query(Learning_log)
        .filter(Learning_log.id == log_id)
        .first()
    )
    log.save = 1
    db.commit()

    return {
        "log_id": log.id,
        "save_status": log.save
    }
@router.get("/unsave_article/{log_id}")
def save_article(log_id: int, db: Session = Depends(get_db)):
    log = (
        db.query(Learning_log)
        .filter(Learning_log.id == log_id)
        .first()
    )
    log.save = 0
    db.commit()

    return {
        "log_id": log.id,
        "save_status": log.save
    }

# ── RE-WRITTEN ENDPOINT ───────────────────────────────────────────────────────
@router.get(
    "/saved_article/{user_id}",
    response_model=List[LearningLogWithPhrases],
)
def get_user_article(user_id: int, db: Session = Depends(get_db)):
    # 1. ensure the user exists (optional but helpful)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. pull every learning-log that belongs to the user
    logs = (
        db.query(Learning_log)
        .filter(Learning_log.user_id == user_id,
                Learning_log.artical.isnot(None),
                Learning_log.save == 1
                )
        .all()
    )

    # 3. for each log, attach its own saved-phrases
    result: List[LearningLogWithPhrases] = []
    for log in logs:
        phrases = (
            db.query(Saved_phrase)
            .filter(
                Saved_phrase.user_id == user_id,
                Saved_phrase.log_id == log.id,
                Saved_phrase.category == "phrase",
            )
            .all()
        )

        result.append(
            LearningLogWithPhrases(
                log_id=log.id,
                daily_new_words=[w.word for w in log.daily_new_words],
                daily_review_words=[w.word for w in log.daily_review_words],
                english_title=log.english_title,
                chinese_title=log.chinese_title,
                article=log.artical,       # article text column:contentReference[oaicite:0]{index=0}
                date=log.date,
                phrases=[
                    SavedPhraseResponse(
                        content=p.content,
                        translation=p.translation,
                        explication=p.explication,
                        log_id=p.log_id,
                        note=None,
                    )
                    for p in phrases
                ],
            )
        )

    return result



@router.get("/all_article/{user_id}", response_model=List[LearningLogResponse])
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
                date=log.date,
            )
        )

    return result

class DifficultyUpdate(BaseModel):
    article_difficulty: conint(ge=0)  # adjust range/validators as you wish
    word_difficulty:    conint(ge=0)

# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.put("/learning_logs_feedback/{log_id}")
def update_difficulty(
    log_id: int,
    diff: DifficultyUpdate,
    db: Session = Depends(get_db)
):
    learning_log = db.query(Learning_log).filter(Learning_log.id == log_id).first()
    if not learning_log:
        raise HTTPException(status_code=404, detail="Learning log not found")

    learning_log.article_difficulty = diff.article_difficulty
    learning_log.words_difficulty   = diff.word_difficulty  # column name is plural
    db.commit()
    db.refresh(learning_log)

    return {"message": "Difficulties updated", "log_id": log_id}

@router.get("/word_learning_history/{word_id}", response_model=List[dict])
def get_learning_logs_by_word(word_id: int, db: Session = Depends(get_db)):
    # Fetch the word from the database to ensure it exists
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    # Query for the learning logs where the word is part of daily new or reviewed words
    learning_logs = db.query(Learning_log).join(
        Daily_new_word_link, Learning_log.id == Daily_new_word_link.learning_log_id
    ).filter(Daily_new_word_link.word_id == word_id, Learning_log.artical.isnot(None)).all()

    # Adding the learning logs from the daily review word link table
    learning_logs += db.query(Learning_log).join(
        Daily_review_word_link, Learning_log.id == Daily_review_word_link.learning_log_id
    ).filter(Daily_review_word_link.word_id == word_id, Learning_log.artical.isnot(None)).all()

    # Prepare the result with only the needed fields
    result = [
        {
            "date": log.date,
            "english_title": log.english_title,
            "chinese_title": log.chinese_title
        }
        for log in learning_logs
    ]

    return result