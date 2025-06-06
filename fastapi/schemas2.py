from pydantic import BaseModel,  Field
from typing import List, Dict, Any, Optional
from pygments.lexer import words

import models
import datetime

class Receive_data(BaseModel):
    user_id: int
    article_id: int
    text: str
    searched_words: List[str]
    test_result: Dict[int, Any]

# class Learning_settings(BaseModel):
#     user_id : int
#     chosed_word_book_id : Optional[int]
#     average_caiji: float
#     daily_goal : int
#     class Config:
#         orm_mode = True

# learning log
class LearningLogBase(BaseModel):
    """Fields common to create/read operations."""
    tag: str


class LearningLogCreate(LearningLogBase):
    """
    Body model for POST requests.

    Only `tag` is supplied in the request body;
    `user_id` comes from the path/route parameter.
    """
    pass


class LearningLog(LearningLogBase):
    """
    Response model for reading logs.
    Most columns are nullable and therefore Optional here.
    """
    id: int
    user_id: int                      # FK column (not nullable)
    CEFR: Optional[str] = None
    daily_caiji: Optional[float] = None
    # all newly-nullable columns ↓
    status: Optional[str] = None
    date: Optional[datetime.date] = None
    title: Optional[str] = None
    outline: Optional[str] = None
    artical: Optional[str] = None     # spelling matches models.py

    class Config:
        orm_mode = True

class LearningLog(LearningLogBase):
    """
    Response model for reading logs.
    Most columns are nullable and therefore Optional here.
    """
    id: int
    user_id: int                      # FK column (not nullable)
    CEFR: Optional[str] = None
    daily_caiji: Optional[float] = None
    # all newly-nullable columns ↓
    status: Optional[str] = None
    date: Optional[datetime.date] = None
    title: Optional[str] = None
    outline: Optional[str] = None
    artical: Optional[str] = None     # spelling matches models.py

    class Config:
        orm_mode = True

# select new words
class WordOut(BaseModel):
    id: int
    word: str
    definition: Optional[str] = None
    CEFR: Optional[str] = None
    phonetic: Optional[str] = None

    class Config:
        orm_mode = True


# --- learning-log + its “new words” bundle ----------------------
class LogWithWords(BaseModel):
    id: int                                # ← maps directly to Learning_log.id
    tag: str
    CEFR: Optional[str] = None
    date: Optional[datetime.date] = None

    # “words” is just a nicer name for the relationship `daily_new_words`
    words: List[WordOut] = Field(..., alias="daily_new_words")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True   # lets FastAPI return `words`