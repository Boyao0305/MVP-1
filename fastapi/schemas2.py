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
    english_title: Optional[str] = None
    chinese_title:Optional[str] = None
    outline: Optional[str] = None
    artical: Optional[str] = None     # spelling matches models.py

    class Config:
        orm_mode = True



# select new words
class Statusbase(BaseModel):
    status:str
    learning_factor: float
class Tagbase(BaseModel):
    name: str

class WordOut(BaseModel):
    id: int
    word: str
    definition: Optional[str] = None
    CEFR: Optional[str] = None
    phonetic: Optional[str] = None
    # tags: List[Tagbase] = Field(..., alias="l_tags")
    # status: List[Statusbase] = Field(..., alias="l_word_statuss")

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
class LogWithWordsreview(BaseModel):
    id: int                                # ← maps directly to Learning_log.id
    tag: str
    CEFR: Optional[str] = None
    date: Optional[datetime.date] = None

    # “words” is just a nicer name for the relationship `daily_new_words`
    words: List[WordOut] = Field(..., alias="daily_review_words")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True   # lets FastAPI return `words`

# daily review words

class ReviewWordOut(BaseModel):
    id: int
    word: str
    CEFR: Optional[str] = None
    learning_factor: float

    class Config:
        orm_mode = True


class ReviewTagOut(BaseModel):
    learning_log_id: int
    tag: str
    words: List[ReviewWordOut]

    class Config:
        orm_mode = True

# llm
class OutlineOut(BaseModel):
    learning_log_id: int
    tag: str
    prompt: str
    outline: str
    english_title: str
    chinese_title: str

# learning_log
class LearningLogDetailOut(BaseModel):
    id: int
    user_id: int
    date: Optional[datetime.date] = None
    tag: str
    CEFR: Optional[str] = None
    english_title: Optional[str]
    chinese_title: Optional[str]
    outline: Optional[str]
    daily_new_words: List[WordOut]
    daily_review_words: List[WordOut]

    class Config:
        orm_mode = True



# service_functions
class WordBatchOut(BaseModel):
    id: int
    word: str
    CEFR: Optional[str] = None
    learning_factor: float = Field(..., alias="learning_factor")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True


class TagWordsOut(BaseModel):
    tag: str
    words: List[WordBatchOut]

    class Config:
        orm_mode = True
# dicrtionary
class Word_definition(BaseModel):
    definition: str