

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
    count = 0
    words = db.query(Word).all()
    pattern = re.compile(r'\b([a-z]{1,5})\.\.')

    for word in words:
        original = word.definition
        if original:
            cleaned = pattern.sub(r'\1.', original)
            if cleaned != original:
                # print (cleaned)
                # print (original)
                count +=1
                word.definition = cleaned
    print (count)
    db.commit()
    count2 = 0
    for word in words:
        print(word.definition)
        count2 += 1
    print(count2)
with SessionLocal() as db:
    clean_definitions(db)

