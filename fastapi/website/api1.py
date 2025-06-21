# routers/word_selection.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import models
import schemas2 as schemas
from database import SessionLocal# ← your pydantic models
       # ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")

# --- CEFR groups per level -----------------------------------------------
# 1 ➜ A1 & A2     2 ➜ B1 & B2     3 ➜ C1 & C2
_ALLOWED_FOR_LEVEL = {
    1: {"A1", "A2"},
    2: {"B1", "B2"},
    3: {"C1", "C2"},
}

# --- response model (same as before) --------------------------------------
class _BasicWordOut(schemas.WordOut):
    class Config:
        fields = {"definition": {"exclude": True},
                  "CEFR": {"exclude": True},
                  "phonetic": {"exclude": True}}

class WordsBatchResp(schemas.BaseModel):
    learning_log_id: int
    words: list[_BasicWordOut]

    class Config:
        orm_mode = True


@router.post(
    "/words/generate/{level}/{tag}/{word_book_id}",
    response_model=WordsBatchResp,
    summary="Pick 20 random words by tag & CEFR (grouped) and create a learning log",
)
def generate_words_for_learning(
    level: int,
    tag: str,
    word_book_id: int,
    db: Session = Depends(get_db),
):
    """
    • level 1 → A1 + A2
    • level 2 → B1 + B2
    • level 3 → C1 + C2

    Select 20 random words that match **both** the tag and the CEFR group,
    save them into a new `Learning_log` row for user #1, and return
    the log-id plus each word’s id & English spelling.
    """
    if level not in (1, 2, 3):
        raise HTTPException(400, detail="`level` must be 1, 2 or 3")

    allowed_cefr = _ALLOWED_FOR_LEVEL[level]

    # 1️⃣  words that carry the given tag AND belong to the CEFR subset
    qry = (
        db.query(models.Word)
        .join(models.Word.l_tags)
        .join(models.Word.l_word_books)
        .filter(models.Tag.name == tag)
        .filter(models.Word_book.id == word_book_id)
        .filter(models.Word.CEFR.in_(allowed_cefr))
    )
    qry2 = (
        db.query(models.Word)
        .join(models.Word.l_tags)
        .join(models.Word.l_word_books)
        .filter(models.Tag.name == "None")
        .filter(models.Word_book.id == word_book_id)
        .filter(models.Word.CEFR.in_(allowed_cefr))
    )

    # 2️⃣  random-pick 20
    words = qry.order_by(func.random()).limit(10).all()
    words2 = qry2.order_by(func.random()).limit(10).all()
    if len(words) < 10:
        raise HTTPException(
            404,
            detail=f"Not enough words for tag='{tag}' & level={level}",
        )

    # 3️⃣  create the learning-log row and link the words
    new_log = models.Learning_log(tag=tag, user_id=1,CEFR='A1')
    new_log.daily_new_words.extend(words)
    db.add(new_log)
    for ws in words2:
        new_log.daily_new_words.append(ws)

    db.commit()
    db.refresh(new_log)

    # 4️⃣  response
    return {
        "learning_log_id": new_log.id,
        "words": new_log.daily_new_words,
    }