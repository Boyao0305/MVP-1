from pygments.lexers import data

import sys
import os
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal, engine, Base
import models
import bcrypt


# Create tables
Base.metadata.create_all(bind=engine)

# Create a test user
db = SessionLocal()

try:

    word1 = db.query(models.Word).filter(models.Word.word == word1).all()
    word_book1 = db.query(models.Word_book).filter(models.Word_book.name == word_book1).first()

    df = pd.read_csv('/app/tools/tag_result2.csv')

    df = df.where(pd.notnull(df), None)


    for _, row in df.iterrows():
        word1=row['word']
        word_book1=row['word_book']
        word2 = db.query(models.Word).filter(models.Word.word == word1).all()
        word_book = db.query(models.Word_book).filter(models.Word_book.name == word_book1).first()

        if not word2 or not word_book:
            raise HTTPException(status_code=404, detail="Word or Word_book not found")

        word_book.l_words.append(word2)
        db.commit()
except Exception as e:
    db.rollback()
    print(f"An error occurred: {e}")
finally:
    db.close()