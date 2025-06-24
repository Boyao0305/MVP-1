"""
Count how many words carry 1, 2, …, 16 tags.

Place this file next to your *models.py* and *database.py*
and run:  python count_word_tag_distribution.py
"""

from sqlalchemy import func
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models


def count_word_tag_distribution(max_tags: int = 16) -> None:
    """Prints “#tags  ->  #words” for 1..max_tags (inclusive)."""
    db: Session = SessionLocal()
    try:
        # —— 1️⃣  for every word, how many tags does it have? ——————————————
        word_counts_subq = (
            db.query(
                models.Word_tag_link.word_id.label("word_id"),
                func.count(models.Word_tag_link.tag_id).label("n_tags"),
            )
            .group_by(models.Word_tag_link.word_id)
            .subquery()
        )

        # —— 2️⃣  how many words fall into each n_tags bucket? ———————
        rows = (
            db.query(
                word_counts_subq.c.n_tags,
                func.count().label("n_words"),
            )
            .group_by(word_counts_subq.c.n_tags)
            .all()
        )

        # —— 3️⃣  put results in a dict for easy lookup ————————————————
        distribution = {n_tags: n_words for n_tags, n_words in rows}

        # —— 4️⃣  pretty-print 1‥max_tags, defaulting to 0 when missing ———
        for k in range(1, max_tags + 1):
            print(f"{k:2d} tag{'s' if k > 1 else ''} : {distribution.get(k, 0)}")

    finally:
        db.close()


if __name__ == "__main__":
    count_word_tag_distribution(16)
