from fastapi import FastAPI, HTTPException
from typing import List
from collections import defaultdict
from nltk.stem import WordNetLemmatizer
import nltk
# routers/learning_log_outline.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models

from openai import AsyncOpenAI
from database import SessionLocal# ← your pydantic models
       # ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")

# Initialize

lemmatizer = WordNetLemmatizer()

# (Optional: during startup)
nltk.download('wordnet')
nltk.download('omw-1.4')

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

@router.get("/word_search/{word}", response_model=List[str])
def word_search(word: str):
    word = word.lower()
    forms_to_try = [word]

    # Try lemmatized forms
    forms_to_try.append(lemmatizer.lemmatize(word, pos="v"))  # verb
    forms_to_try.append(lemmatizer.lemmatize(word, pos="n"))  # noun

    # Try manual stem variants
    if word.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")  # studies → study
    if word.endswith("ing"):
        forms_to_try.append(word[:-3])        # eating → eat
    if word.endswith("ed"):
        forms_to_try.append(word[:-2])        # worked → work
    if word.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])        # cars → car

    # Remove duplicates
    forms_to_try = list(dict.fromkeys(forms_to_try))

    # Try each form
    for form in forms_to_try:
        result = reverse_dict.get(form)
        if result:
            return result

    raise HTTPException(status_code=404, detail="Word not found in dictionary")
