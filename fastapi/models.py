from xmlrpc.client import Boolean
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Date, Text
from database import Base
from sqlalchemy.orm import sessionmaker, relationship


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    phone_number = Column(String(255), nullable=True)
    membership = Column(Integer, default=False)
    consecutive_learning = Column(Integer, nullable=False, default=0)
    openid = Column(String(255), nullable=True)

    l_word_statuss = relationship("Word_status", back_populates="l_users")

    l_learning_setting = relationship("Learning_setting", back_populates="l_user", uselist=False)

    l_learning_logs = relationship("Learning_log", back_populates="l_user")
    l_saved_phrases = relationship("Saved_phrase", back_populates="l_user")

class Invitation_code(Base):
    __tablename__ = "invitation_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(255), unique=True, index=True, nullable=False)
    code_status = Column(Integer, nullable=False, default=0)

class Word(Base):
    __tablename__ = "words"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), nullable=False, index=True)
    definition = Column(String(255))
    CEFR = Column(String(255), index=True)
    phonetic = Column(String(255), index=True)
    legality = Column(String(255), index=True)

    l_word_statuss = relationship("Word_status", back_populates="l_words")
    l_tags = relationship("Tag", secondary="word_tag_links", back_populates="l_words")
    l_word_books = relationship("Word_book", secondary="word_wordbook_links", back_populates="l_words")

    new_in_logs = relationship("Learning_log", secondary="daily_new_word_links")
    reviewed_in_logs = relationship("Learning_log", secondary="daily_review_word_links")

class Dictionary(Base):
    __tablename__ = "dictionaries"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), nullable=False, index=True)
    definition = Column(String(255))

class Word_status(Base):
    __tablename__ = "word_statuss"
    words_id = Column(Integer, ForeignKey("words.id"), primary_key=True, index=True)
    users_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    status = Column(String(255), nullable=False, index=True)
    learning_factor = Column(Float, nullable=False,default=0.0, index=True )

    l_words = relationship("Word", back_populates="l_word_statuss")
    l_users = relationship("User", back_populates="l_word_statuss")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)

    l_words = relationship("Word", secondary="word_tag_links", back_populates="l_tags")

# Word_book table
class Word_book(Base):
    __tablename__ = "word_books"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)

    l_words = relationship("Word", secondary="word_wordbook_links", back_populates="l_word_books")

# Middle table: word <-> tag
class Word_tag_link(Base):
    __tablename__ = "word_tag_links"

    word_id = Column(Integer, ForeignKey("words.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

# Middle table: word <-> word_book
class Word_wordbook_link(Base):
    __tablename__ = "word_wordbook_links"

    word_id = Column(Integer, ForeignKey("words.id"), primary_key=True)
    word_book_id = Column(Integer, ForeignKey("word_books.id"), primary_key=True)

class Learning_setting(Base):
    __tablename__ = "learning_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    chosed_word_book_id = Column(Integer)
    average_caiji = Column(Float, default=1)
    daily_goal = Column(Integer, default=15)

    l_user = relationship("User", back_populates="l_learning_setting")

class Saved_phrase(Base):
    __tablename__ = "saved_phrases"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String(1000), nullable=False)
    translation = Column(String(1000))
    explication = Column(String(1000))
    category = Column(String(30), index=True)
    log_id = Column(Integer, nullable=True)
    appreciation = Column(Integer, nullable=True)
    note = Column(String(4096), nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    l_user = relationship("User", back_populates="l_saved_phrases")


class Learning_log(Base):
    __tablename__ = "learning_logs"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String(255), nullable=False, index=True)
    CEFR = Column(String(255), index=True)
    daily_caiji = Column(Float)
    status = Column(String(255), nullable=True, index=True)
    date = Column(Date, nullable=True)
    english_title = Column(String(255), nullable=True)
    chinese_title = Column(String(255), nullable=True)
    outline = Column(String(4096), nullable=True)
    artical = Column(Text, nullable=True)
    appreciation = Column(Integer, nullable=True)
    article_difficulty = Column(Integer, nullable=True)
    words_difficulty = Column(Integer, nullable=True)
    save = Column(Integer, nullable=True)
    note = Column(String(4096), nullable=True)
    status = Column(Integer, nullable=True, default=0)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    l_user = relationship("User", back_populates="l_learning_logs")

    daily_new_words = relationship("Word", secondary="daily_new_word_links", overlaps="new_in_logs")
    daily_review_words = relationship("Word", secondary="daily_review_word_links", overlaps="reviewed_in_logs")
    l_daily_searched_words = relationship("Daily_searched_word", back_populates="l_learning_logs")

class Daily_new_word_link(Base):
    __tablename__ = "daily_new_word_links"

    learning_log_id = Column(Integer, ForeignKey("learning_logs.id"), primary_key=True)
    word_id = Column(Integer, ForeignKey("words.id"), primary_key=True)

# Middle table: learning_log <-> word (for review words)
class Daily_review_word_link(Base):
    __tablename__ = "daily_review_word_links"

    learning_log_id = Column(Integer, ForeignKey("learning_logs.id"), primary_key=True)
    word_id = Column(Integer, ForeignKey("words.id"), primary_key=True)
    review_indicator = Column(Integer, default=0)

class Daily_searched_word(Base):
    __tablename__ = "daily_searched_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(255), nullable=False, index=True)
    log_id = Column(Integer, ForeignKey("learning_logs.id"), index=True)
    l_learning_logs = relationship("Learning_log", back_populates="l_daily_searched_words")

