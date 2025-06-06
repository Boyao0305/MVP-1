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

df = pd.read_csv('/app/tools/tag_result2.csv')

df = df.where(pd.notnull(df), None)


for _, row in df.iterrows():
    word1=row['word']
    phonetic1=row['phonetic']
    word2 = db.query(models.Word).filter(models.Word.word == word1).first()
    if word2:
        # 2. Modify the fields you want
        word2.phonetic = phonetic1

        # 3. Commit the changes
        db.commit() # Optional: to get the updated object
