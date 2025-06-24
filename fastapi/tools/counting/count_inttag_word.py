"""
Count words that belong exclusively to each Tag.

Result:
    Tag name  ->  #words that have *only* this tag (no others).
"""

from sqlalchemy import func
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models


def count_exclusive_words_per_tag() -> None:
    db: Session = SessionLocal()
    try:
        # ── 1. For every word, how many tags does it have? ──────────────────────
        word_tag_cnt = (
            db.query(
                models.Word_tag_link.word_id.label("word_id"),
                func.count(models.Word_tag_link.tag_id).label("n_tags"),
            )
            .group_by(models.Word_tag_link.word_id)
            .subquery()
        )

        # ── 2. Pick only the words whose n_tags == 1 and capture their tag_id ──
        exclusive_words = (
            db.query(
                models.Word_tag_link.word_id.label("word_id"),
                models.Word_tag_link.tag_id.label("tag_id"),
            )
            .join(
                word_tag_cnt,
                models.Word_tag_link.word_id == word_tag_cnt.c.word_id,
            )
            .filter(word_tag_cnt.c.n_tags == 1)
            .subquery()
        )

        # ── 3. Count how many exclusive words each Tag owns ─────────────────────
        rows = (
            db.query(
                models.Tag.name,
                func.count(exclusive_words.c.word_id).label("n_exclusive_words"),
            )
            .outerjoin(exclusive_words, models.Tag.id == exclusive_words.c.tag_id)
            .group_by(models.Tag.id)
            .order_by(models.Tag.name)
            .all()
        )

        # ── 4. Pretty-print (tags with no exclusive words show 0) ───────────────
        for tag_name, n in rows:
            print(f"{tag_name:<20} {n}")

    finally:
        db.close()


if __name__ == "__main__":
    count_exclusive_words_per_tag()
