from pygments.lexers import data

import sys
import os
import pandas as pd
from fastapi import HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal, engine, Base
import models
import bcrypt
import re


# Create tables
Base.metadata.create_all(bind=engine)

# Create a test user
db = SessionLocal()


try:
    df = pd.read_csv('/app/tools/initiation/completion.csv')

    df = df.where(pd.notnull(df), None)

    for _, row in df.iterrows():
        tag1 = row['tag']
        word_book1 = row['word_book']
        words = models.Word(word=row['word'], definition=row['definition'], CEFR=row['CEFR'], phonetic=row['phonetic'])
        db.add(words)
        # word_book1 = row['word_book']
        # word_book2 = db.query(models.Word_book).filter(models.Word_book.name == word_book1).first()
        # # print(word_book2.name)
        # if not word_book2:
        #     db.rollback()
        #     raise HTTPException(status_code=404, detail=f"Word_book '{word_book1}' not found")
        #
        # word_book2.l_words.append(words)

        if tag1 == None:
            tagstable = db.query(models.Tag).filter(models.Tag.name == 'None').first()
            tagstable.l_words.append(words)
        else:
            # print(tag1)
            match = re.search(r"\[(.*?)\]", tag1)
            tag1 = match.group(1)
            tag1 = tag1.strip()
            tag1 = [x.strip().strip('"') for x in tag1.split(",")]
            for component in tag1:
                tagstable = db.query(models.Tag).filter(models.Tag.name == component).first()
                if not tagstable:
                    continue
                else:
                    tagstable.l_words.append(words)
        match = re.search(r"\[(.*?)\]", word_book1)
        word_book1 = match.group(1)
        word_book1 = word_book1.strip()
        word_book1 = [x.strip().strip('"') for x in word_book1.split(",")]
        for component in word_book1:
            wordbookstable = db.query(models.Word_book).filter(models.Word_book.name == component).first()
            if not wordbookstable:
                continue
            else:wordbookstable.l_words.append(words)

    db.commit()

except Exception as e:
    db.rollback()
    print(f"❌ Error occurred: {e}")

finally:
    db.close()