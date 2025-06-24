"""
Count the number of Word rows associated with each Tag.

Assumes:
• `models.py` defines Word, Tag and Word_tag_link as in the file you shared.
• `database.py` exposes a configured SQLAlchemy SessionLocal object.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database  import SessionLocal          # created next to your models
import models


def count_words_by_tag() -> None:
    """Prints:  Tag-name  ->  #words  (one line per tag)."""
    db: Session = SessionLocal()
    try:
        # OUTER join so that tags with zero words still appear (count = 0)
        rows = (
            db.query(models.Tag.name, func.count(models.Word.id).label("n_words"))
              .outerjoin(models.Tag.l_words)          # uses the relationship
              .group_by(models.Tag.id)
              .order_by(models.Tag.name)
              .all()
        )

        for tag_name, n in rows:
            print(f"{tag_name:<20} {n}")

    finally:
        db.close()


if __name__ == "__main__":
    count_words_by_tag()
