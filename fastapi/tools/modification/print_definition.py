

import sys
import os
import pandas as pd
from fastapi import HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal, engine, Base
import models
import bcrypt
import re
import re
from sqlalchemy.orm import Session
from models import Word


# Create tables
Base.metadata.create_all(bind=engine)

# Create a test user
db = SessionLocal()


def clean_definitions(db: Session):
    """
    Replace double dots (e.g., 'n..', 'v..') in all definitions in the `words` table with a single dot (e.g., 'n.').
    """
    count2 = 0
    words = db.query(Word).all()

    for word in words:
        print(word.definition)
        count2 += 1
    print(count2)
with SessionLocal() as db:
    clean_definitions(db)

