from pydantic import BaseModel,  Field
from typing import List, Optional

from pygments.lexer import words

import models
import datetime


# users
class Userid(BaseModel):
    id: int

class Userbase(BaseModel):
    username: str
    password: str

class Usercreate(Userbase):
    pass

class Learning_settings(BaseModel):
    user_id : int
    chosed_word_book_id : Optional[int]
    average_caiji: float
    daily_goal : int
    class Config:
        orm_mode = True

class Userget(BaseModel):
    username: str
    l_learning_setting: Learning_settings
    class Config:
        orm_mode = True

class LoginRequest(Userbase):
    pass

# schemas.py

class FullRegisterRequest(BaseModel):
    username: str
    password: str
    phone_number: int
    chosed_word_book_id: Optional[int] = None
    average_caiji: Optional[float] = 1
    daily_goal: Optional[int] = 15

class UserResponse(BaseModel):
    id: int
    username: str
    phone_number: Optional[int]
    membership: int
    consecutive_learning: int
    chosed_word_book_id: Optional[int]
    average_caiji: float
    daily_goal: int

    class Config:
        orm_mode = True

# words
class Wordbase(BaseModel):
    word: str
    definition: Optional[str]
    CEFR: str
    phonetic: str

class Wordcreate(Wordbase):
    pass

class Wordget(Wordbase):
    id:int
    class Config:
        orm_mode = True

# word_status
class Word_statusbase(BaseModel):
    status: str
    learning_factor: float

class Word_statuscreate(Word_statusbase):
    words_id: int
    users_id: int

class Word_statusget(Word_statuscreate):
    class Config:
        orm_mode = True

# tag
class Tagbase(BaseModel):
    name: str

class Tagcreate(Tagbase):
    pass

class Tagget(Tagbase):
    id: int
    l_words : List[Wordget] = []
    class Config:
        orm_mode = True


class TagLinkRequest(BaseModel):
    word_id: int
    tag_id: int


# word_book

class WordBookLinkRequest(BaseModel):
    word_id: int
    word_book_id: int

class Word_bookbase(BaseModel):
    name: str

class Word_bookcreate(Word_bookbase):
    pass

class Word_bookget(Word_bookbase):
    l_words: List[Wordget] = []
    class Config:
        orm_mode = True

# learning_log



class Learning_logbase(BaseModel):
    date: datetime.date = Field(default_factory=datetime.date.today)
    tag:str
    CEFR: str
    daily_caiji: float
    status: str
    title: str
    outline: str
    artical: str

class Learning_logcreate(Learning_logbase):
    user_id: int  # to link to a user

class Learning_logget(Learning_logbase):
    id: int
    user_id: int
    daily_new_words : List[Wordget] = []
    daily_review_words: List[Wordget] = []

    class Config:
        orm_mode = True

# daily words
class NewWordLinkRequest(BaseModel):
    learning_log_id: int
    word_id: int

class ReviewWordLinkRequest(BaseModel):
    learning_log_id: int
    word_id: int