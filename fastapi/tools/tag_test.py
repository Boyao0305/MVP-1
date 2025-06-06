from tracemalloc import take_snapshot

from pygments.lexers import data

import sys
import os
import pandas as pd
from fastapi import HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal, engine, Base
import models
import bcrypt
import re
import json


# Create tables
Base.metadata.create_all(bind=engine)

# Create a test user
db = SessionLocal()



df = pd.read_csv('/app/tools/tag_result2.csv')

df = df.where(pd.notnull(df), None)

for _, row in df.iterrows():

    tag1 = row['tag']
    word1 = row['word']

    if tag1 == None:
        continue
    else:
        # print(tag1)
        match = re.search(r"\[(.*?)\]", tag1)
        tag1 = match.group(1)
        tag1 = tag1.strip()
        tag1 = [x.strip().strip('"') for x in tag1.split(",")]
        for component in tag1:
            tagstable = db.query(models.Tag).filter(models.Tag.name == component).first()
            if not tagstable:
                print(component)
            # print(tagstable.id)




# tag = "dfdfd[12dsff1]dfsdfs"
# print(tag)
# match = re.search(r"\[(.*?)\]", tag)
# if match:
#     inside = match.group(1)
#     print(inside)  # Output: 12dsff1
#
# else:
#     print('error')


