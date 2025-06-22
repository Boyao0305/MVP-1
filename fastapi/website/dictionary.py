from fastapi import FastAPI, HTTPException
from typing import List
from collections import defaultdict
import nltk
from nltk.stem import WordNetLemmatizer

# routers/learning_log_outline.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models
import schemas2
from openai import OpenAI

from openai import AsyncOpenAI
from database import SessionLocal# ← your pydantic models

from models import Dictionary


# ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")

# Initialize

# lemmatizer = WordNetLemmatizer()

# (Optional: during startup)
# nltk.download('wordnet')
# nltk.download('omw-1.4')

# Load dictionary
def load_cedict_reverse(filepath="/app/website/dictionary/cedict_ts.u8"):
    dictionary = defaultdict(list)
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split(" /")
            if len(parts) < 2:
                continue
            chinese_part = parts[0]
            definitions = parts[1].split("/")[:-1]
            try:
                _, simp, _ = chinese_part.split(" ", 2)
            except ValueError:
                continue
            for definition in definitions:
                meaning = definition.strip().lower()
                if simp not in dictionary[meaning]:
                    dictionary[meaning].append(simp)
    return dictionary

reverse_dict = load_cedict_reverse("/app/website/dictionary/cedict_ts.u8")

@router.get("/word_search/{word}")
def word_search(word: str,  db: Session = Depends(get_db)):
    word0 = word.lower()
    forms_to_try = [word]
    # ,
    # response_model = List[str]
    # Try lemmatized forms
    # forms_to_try.append(lemmatizer.lemmatize(word0, pos="v"))  # verb
    # forms_to_try.append(lemmatizer.lemmatize(word0, pos="n"))  # noun

    # Try manual stem variants
    if word0.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")  # studies → study
    if word0.endswith("ing"):
        forms_to_try.append(word[:-3])        # eating → eat
    if word0.endswith("ed"):
        forms_to_try.append(word[:-2])        # worked → work
    if word0.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])        # cars → car
    # return forms_to_try   # Remove duplicates
    forms_to_try = list(dict.fromkeys(forms_to_try))
    #
    # # Try each form
    for form in forms_to_try:
            # result = reverse_dict.get(form)
            word1 = (
                db.query(models.Word)

                .filter(
                    models.Word.word == form
                )
                .first()
            )
            word2 = (
                db.query(models.Dictionary)

                         .filter(
                    models.Dictionary.word == word0
                )
                         .first()
                         )
            if word1:
                return word1.definition

            if word2:
                return word2.definition

            else:
                client = OpenAI(
                    # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
                    api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
                    # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                )

                completion = client.chat.completions.create(
                    model="deepseek-v3",  # 此处以 deepseek-r1 为例，可按需更换模型名称。
                    messages=[
                        {'role': 'user',
                         'content': f"""请返回{word0}单词的中文定义，请只返回一个或几个词性缩写和对应的中文定义，并用逗号隔开"""
                         }
                    ]
                )

                definition2 = completion.choices[0].message.content
                word3 = Dictionary(word = word0, definition = definition2 )
                db.add(word3)
                db.commit()
                return definition2
                # return word



    raise HTTPException(status_code=404, detail="Word not found in dictionary")
