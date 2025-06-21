# models.py  – schema **plus** optional seed helper
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, Session
from database import SessionLocal
Base = declarative_base()

class Word_book(Base):
    __tablename__ = "word_books"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False)

# ───────────────────────────────────────────────────────────────
#  OPTIONAL: seed convenience – only runs if you call it.
# ───────────────────────────────────────────────────────────────
def seed_initial_word_books(db: Session) -> list["Tag"]:
    """
    Insert the fixed tag vocabulary.  Safe to call multiple times:
    duplicates are skipped.  Returns the Tag objects added this call.
    """
    word_book_names = ["midschool", "highschool", "cet4", "cet6", "tem4", "tem8", "postgrad", "ielts", "toefl"]

    existing = {t[0] for t in db.query(Word_book.name).all()}
    new_rows = [Word_book(name=n) for n in word_book_names if n not in existing]

    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()

    return new_rows
with SessionLocal() as db:
    seed_initial_word_books(db)