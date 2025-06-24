# models.py  – schema **plus** optional seed helper
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, Session
from database import SessionLocal
Base = declarative_base()

class Tag(Base):
    __tablename__ = "tags"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)

# ───────────────────────────────────────────────────────────────
#  OPTIONAL: seed convenience – only runs if you call it.
# ───────────────────────────────────────────────────────────────
def seed_initial_tags(db: Session) -> list["Tag"]:
    """
    Insert the fixed tag vocabulary.  Safe to call multiple times:
    duplicates are skipped.  Returns the Tag objects added this call.
    """
    tag_names = [
        "None", "Tech", "Economy", "Science", "Art",
        "History", "Politics", "Environment", "Health", "Sports",
        "Fashion", "Media", "Literature", "Education", "Society",
        "Laws", "Travel"
    ]

    existing = {t[0] for t in db.query(Tag.name).all()}
    new_rows = [Tag(name=n) for n in tag_names if n not in existing]

    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()

    return new_rows
with SessionLocal() as db:
    seed_initial_tags(db)