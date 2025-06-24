# ─── routers/words.py ─────────────────────────────────────────────────────────
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
import models                       # your existing models.py
from database import SessionLocal
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# your SessionLocal dependency

router = APIRouter(prefix="/api")


@router.get(
    "/tags/{tag_name}/random-words",
    response_model=List[str],
    summary="Return 30 random English words from the given tag",
)
def random_words_from_tag(
    tag_name: str,
    limit: int = 30,                 # let clients pass ?limit=50 if they like
    db: Session = Depends(get_db),
):
    # 1) Look up the tag
    tag_id = db.execute(
        select(models.Tag.id).where(models.Tag.name == tag_name)
    ).scalar_one_or_none()
    if tag_id is None:
        raise HTTPException(404, detail=f"Tag '{tag_name}' not found")

    # 2) Fetch up-to `limit` random words for that tag
    #    func.random() works on SQLite & PostgreSQL; use func.rand() on MySQL.
    random_func = func.random()
    if db.bind.dialect.name == "mysql":
        random_func = func.rand()

    rows = (
        db.query(models.Word.word)                           # only the column we need
          .join(models.Word_tag_link,
                models.Word_tag_link.word_id == models.Word.id)
          .filter(models.Word_tag_link.tag_id == tag_id)
          .order_by(random_func)
          .limit(limit)
          .all()
    )

    # 3) rows come back as list[tuple]; flatten to list[str]
    return [w[0] for w in rows]
def _random(session: Session):
    return func.rand() if session.bind.dialect.name == "mysql" else func.random()


@router.get(
    "/tags/{tag_name}/mixed-30",
    response_model=List[str],
    summary="15 random words from the tag + 15 from tag 'None' (combined list)",
)
def mixed_words_from_tag_and_none(
    tag_name: str,
    db: Session = Depends(get_db),
):
    # ── 1. Fetch ids for both target tag and 'None' ──────────────────────────
    tags = db.execute(
        select(models.Tag.name, models.Tag.id).where(
            models.Tag.name.in_([tag_name, "None"])
        )
    ).all()
    tag_ids = {name: _id for name, _id in tags}

    if tag_name not in tag_ids:
        raise HTTPException(404, detail=f"Tag '{tag_name}' not found")
    if "None" not in tag_ids:
        raise HTTPException(500, detail="Tag 'None' missing in the database")

    rnd = _random(db)

    # helper → ≤15 random word strings for given tag-id
    def _pick_15(tag_id: int):
        rows = (
            db.query(models.Word.word)
              .join(models.Word_tag_link,
                    models.Word_tag_link.word_id == models.Word.id)
              .filter(models.Word_tag_link.tag_id == tag_id)
              .order_by(rnd)
              .limit(15)
              .all()
        )
        return [row[0] for row in rows]

    words = _pick_15(tag_ids[tag_name]) + _pick_15(tag_ids["None"])

    # ── 2. Remove duplicates (if a word carries both tags) and shuffle ───────
    import random
    words = list(set(words))
    random.shuffle(words)

    # If fewer than 30 remain (because of overlap or small tag size),
    # return whatever we have.
    return words