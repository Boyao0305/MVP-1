from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from functions.auth import authenticate_user, register_user
import schemas
import datetime as dt
import schemas2
import models
from sqlalchemy.orm import joinedload
from functions.new_session import create_five_learning_logs, assign_daily_new_words,assign_daily_review_words, generate_outlines_for_date_async

from typing import List, Optional
from sqlalchemy.sql.expression import func

router = APIRouter(prefix="/api")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ADD
@router.post("/word/", response_model=schemas.Wordget)
def create_word(word: schemas.Wordcreate, db: Session = Depends(get_db)):
    new_word = models.Word(**word.dict())
    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word

@router.post("/add_tag/", response_model=schemas.Tagget)
def add_tag(tag: schemas.Tagcreate, db: Session = Depends(get_db)):
    db_tag = models.Tag(name=tag.name)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

@router.post("/add_word_book/", response_model=schemas.Word_bookget)
def add_word_book(word_book: schemas.Word_bookcreate, db: Session = Depends(get_db)):
    db_word_book = models.Word_book(name=word_book.name)
    db.add(db_word_book)
    db.commit()
    db.refresh(db_word_book)
    return db_word_book

# @router.post("/learning_log", response_model=schemas2.LearningLog)
# def create_learning_log(log: schemas2.LearningLog, db: Session = Depends(get_db)):
#     new_log = models.Learning_log(**log.dict())
#     db.add(new_log)
#     db.commit()
#     db.refresh(new_log)
#     return new_log



# link
@router.post("/link-user-word/", response_model=schemas.Word_statusget)
def link_user_word(payload: schemas.Word_statuscreate, db: Session = Depends(get_db)):
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == payload.users_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if word exists
    word = db.query(models.Word).filter(models.Word.id == payload.words_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    # Create relation
    link = models.Word_status(
        users_id=payload.users_id,
        words_id=payload.words_id,
        status=payload.status,
        learning_factor=payload.learning_factor
    )

    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.post("/link_tag_to_word/", response_model=schemas.Tagget)
def link_tag_to_word(link_data: schemas.TagLinkRequest, db: Session = Depends(get_db)):
    word = db.query(models.Word).filter(models.Word.id == link_data.word_id).first()
    tag = db.query(models.Tag).filter(models.Tag.id == link_data.tag_id).first()

    if not word or not tag:
        raise HTTPException(status_code=404, detail="Word or Tag not found")

    word.l_tags.append(tag)
    db.commit()
    return tag


@router.post("/link_word_to_wordbook/")
def link_word_to_wordbook(link_data: schemas.WordBookLinkRequest, db: Session = Depends(get_db)):
    word = db.query(models.Word).filter(models.Word.id == link_data.word_id).first()
    word_book = db.query(models.Word_book).filter(models.Word_book.id == link_data.word_book_id).first()

    if not word or not word_book:
        raise HTTPException(status_code=404, detail="Word or Word_book not found")

    word.l_word_books.append(word_book)
    db.commit()
    return {"message": "Word linked to Word_book"}


@router.post("/link_new_word")
def link_new_word(data: schemas.NewWordLinkRequest, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter(models.Learning_log.id == data.learning_log_id).first()
    word = db.query(models.Word).filter(models.Word.id == data.word_id).first()

    if not log or not word:
        raise HTTPException(status_code=404, detail="Learning log or word not found")

    log.daily_new_words.append(word)
    db.commit()

    return {"message": f"Word {word.word} linked as new to log {log.id}"}

@router.post("/link_review_word")
def link_review_word(data: schemas.ReviewWordLinkRequest, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter(models.Learning_log.id == data.learning_log_id).first()
    word = db.query(models.Word).filter(models.Word.id == data.word_id).first()

    if not log or not word:
        raise HTTPException(status_code=404, detail="Learning log or word not found")

    log.daily_review_words.append(word)
    db.commit()

    return {"message": f"Word {word.word} linked as review to log {log.id}"}


# check link
@router.post("/user_word/")
def user_word(search: schemas.Userid, db: Session = Depends(get_db)):
    words=db.query(models.User).filter(models.User.id == search.id).first()
    if not words:
        raise HTTPException(status_code=404, detail="User not found")
    result = []

    for link in words.l_word_statuss:
        result.append(link.l_words.word)

    return {"word":result}
@router.get("/tag/{tag_id}", response_model=schemas.Tagget)
def get_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag

# @router.get("/learning_log/{learning_log_id}", response_model=schemas.Learning_logget)
# def get_new_word(learning_log_id: int, db: Session = Depends(get_db)):
#     log = db.query(models.Learning_log).filter(models.Learning_log.id == learning_log_id).first()
#     if not log:
#         raise HTTPException(status_code=404, detail="Tag not found")
#     return log

@router.get("/learning_log/{learning_log_id}")
def get_new_word(learning_log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter(models.Learning_log.id == learning_log_id).first()
    result = []
    for words in log.daily_new_words:
        result.append(words.word)
    return {log}

@router.get("/word/{word_id}", response_model=schemas2.WordOut)
def get_new_word(word_id: int, db: Session = Depends(get_db)):
    log = db.query(models.Word).filter(models.Word.id == word_id).first()
    return log

@router.get("/word_book/{word_book_name}", response_model=schemas.Word_bookget)
def get_new_word(word_book_name: str, db: Session = Depends(get_db)):
    log = db.query(models.Word_book).filter(models.Word_book.name == word_book_name).first()
    return log

# @router.get("/tag/{word_book_name}", response_model=schemas.Word_bookget)
# def get_new_word(word_book_name: str, db: Session = Depends(get_db)):
#     log = db.query(models.Word_book).filter(models.Word_book.name == word_book_name).first()
#     return log

# @router.post("/assigne_word_book/{user_id1}/{word_book}", response_model=schemas.Learning_settings)
# def assign_word_book(user_id1: int, word_book: int, db: Session = Depends(get_db)):
#     Learning_setting1 = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id1).first()
#     if not Learning_setting1:
#         raise HTTPException(status_code=404, detail="User not found")
#     Learning_setting1.chosed_word_book_id = word_book
#     db.commit()
#     db.refresh(Learning_setting1)
#     return Learning_setting1

@router.post("/user/{user_id1}",response_model=schemas.Userget)
def getuser(user_id1: int, db: Session = Depends(get_db)):
    user = db.query(models.User).options(joinedload(models.User.l_learning_setting)).filter(models.User.id == user_id1).first()
    return user

# @router.get("/user/{user_id1}", response_model=schemas.Userget)
# def getuser(user_id1: int, db: Session = Depends(get_db)):
#     user = db.query(models.User)\
#         .options(joinedload(models.User.l_learning_setting))\
#         .filter(models.User.id == user_id1).first()
#
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     if user.l_learning_setting is None:
#         raise HTTPException(status_code=500, detail="User has no learning setting")
#
#     return

@router.put("/update_average_caiji/{user_id}/{new_value}", response_model=schemas.Learning_settings)
def update_average_caiji(user_id: int, new_value: int, db: Session = Depends(get_db)):
    setting = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Learning setting not found for this user")

    setting.average_caiji = new_value
    db.commit()
    db.refresh(setting)
    return setting

@router.post("/learning_logs/seed/{user_id}", response_model=list[schemas2.LearningLog])
def seed_learning_logs(user_id: int, db: Session = Depends(get_db)):
    return create_five_learning_logs(user_id, db)

@router.post(
    "/daily_new_words/{user_id}",
    response_model=list[schemas2.LogWithWords],
    summary="Generate today’s new-word lists and return them",
)
def generate_and_read_daily_words(user_id: int, db: Session = Depends(get_db)):
    """
    1.  Runs **assign_daily_new_words()** → fills *daily_new_word_links* for today.
    2.  Fetches today’s five learning-log rows eagerly-loaded with their `daily_new_words`.
    3.  Serialises them with *LogWithWords*.
    """
    # 1️⃣  populate links (raises HTTPException if anything is wrong)
    assign_daily_new_words(user_id, db)

    # 2️⃣  read fresh data back
    today = dt.date.today()
    logs = (
        db.query(models.Learning_log)
        .options(joinedload(models.Learning_log.daily_new_words))
        .filter(models.Learning_log.user_id == user_id,
                models.Learning_log.date == today)
        .order_by(models.Learning_log.id.desc())  # newest first
        .limit(5)
        .all()
    )

    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")
    # 3️⃣  FastAPI + orm_mode → automatic conversion to LogWithWords
    return logs
@router.post(
    "/daily_review_words/{user_id}",
    response_model=list[schemas2.LogWithWordsreview],
    summary="Pick lowest-factor review words per tag and link them"
)

def generate_and_read_daily_review_words(user_id: int, db: Session = Depends(get_db)):
    assign_daily_review_words(user_id, db)

    # 2️⃣  read fresh data back
    today = dt.date.today()
    logs = (
        db.query(models.Learning_log)
        .options(joinedload(models.Learning_log.daily_review_words))
        .filter(models.Learning_log.user_id == user_id,
                models.Learning_log.date == today)
        .order_by(models.Learning_log.id.desc())  # newest first
        .limit(5)
        .all()
    )

    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")
    # 3️⃣  FastAPI + orm_mode → automatic conversion to LogWithWords
    return logs
# def daily_review_words(user_id: int, db: Session = Depends(get_db)):
#     promoted = assign_daily_review_words(user_id, db)   # id → [Word_status]
#
#     # build response
#     out: list[schemas2.ReviewTagOut] = []
#     for log_id, ws_rows in promoted.items():
#         if not ws_rows:
#             continue
#         tag = ws_rows[0].l_words.l_tags[0].name  # each row shares the same tag
#         out.append(
#             schemas2.ReviewTagOut(
#                 learning_log_id=log_id,
#                 tag=tag,
#                 words=[
#                     schemas2.ReviewWordOut(
#                         id=ws.l_words.id,
#                         word=ws.l_words.word,
#                         CEFR=ws.l_words.CEFR,
#                         learning_factor=ws.learning_factor,
#                     )
#                     for ws in ws_rows
#                 ],
#             )
#         )
#     return out


@router.post(
    "/generate_outlines/{user_id}",
    response_model=list[schemas2.OutlineOut],
    summary="Generate 5 outlines + titles concurrently via LLM",
)
async def generate_outlines(
    user_id: int,
    date: Optional[str] = None,      # /generate_outlines/{id}?date=YYYY-MM-DD
    db: Session = Depends(get_db),
):
    try:
        for_date = dt.date.fromisoformat(date) if date else dt.date.today()
    except ValueError:
        raise HTTPException(422, "date must be YYYY-MM-DD")

    data = await generate_outlines_for_date_async(user_id, for_date, db)

    return [
        schemas2.OutlineOut(
            learning_log_id=item["log"].id,
            tag=item["log"].tag,
            prompt=item["prompt"],
            outline=item["answer"]["outline"],
            english_title=item["answer"]["english_title"],
            chinese_title=item["answer"]["chinese_title"],
        )
        for item in data
    ]
@router.get("/random-words", response_model=List[schemas.Wordget])
def get_random_words(db: Session = Depends(get_db)):
    words = db.query(models.Word).order_by(func.random()).limit(20).all()
    if not words:
        raise HTTPException(status_code=404, detail="No words found in database.")
    return words

@router.get(
    "/daily_learning_logs_by_id/{log_id}",
    response_model=list[schemas2.LearningLogDetailOut],
    summary="Return today's (or specified) learning-log rows for a user",
)
def read_learning_logs(
    log_id: int,              # ← query-param, optional
    db: Session = Depends(get_db),
):
    # 1️⃣  pick the date


    # 2️⃣  fetch rows with word lists pre-loaded
    logs = (
        db.query(models.Learning_log)

          .filter(
              models.Learning_log.id == log_id,
          )
          .all()
    )
    if not logs:
        raise HTTPException(404, "No logs found for that user/date")

    return logs
from sqlalchemy import select, outerjoin
@router.get(
    "/tags/{tag_name}/words/{user_id}",
    response_model=schemas.TagWordsStatusOut,
    summary="Return every word linked to a tag with that user’s status",
)
def words_by_tag_with_status(
    tag_name: str,
    user_id: int,
    db: Session = Depends(get_db),
):
    # 1) locate the tag
    tag = db.execute(
        select(models.Tag).where(models.Tag.name == tag_name)
    ).scalar_one_or_none()
    if tag is None:
        raise HTTPException(404, "Tag not found")

    # 2) join words ←→ tag  +  OUTER join to word_statuss for *this* user
    stmt = (
        select(
            models.Word,                      # full Word ORM object
            models.Word_status.status,
            models.Word_status.learning_factor,
        )
        .join(models.Word_tag_link,
              models.Word_tag_link.word_id == models.Word.id)
        .where(models.Word_tag_link.tag_id == tag.id)
        .outerjoin(                          # may be NULL if user never touched it
            models.Word_status,
            (models.Word_status.words_id == models.Word.id)
            & (models.Word_status.users_id == user_id),
        )
    )

    rows = db.execute(stmt).all()

    # 3) build DTO list (use defaults when no status row exists)
    words_out = [
        schemas.WordStatusOut(
            id=w.id,
            word=w.word,
            CEFR=w.CEFR,
            status=s if s is not None else "unlearned",
            learning_factor=lf if lf is not None else 0.0,
        )
        for w, s, lf in rows
    ]

    return {"tag": tag.name, "words": words_out}


@router.get(
    "/users/{user_id}/learning-words",
       # change to your own schema type
    summary="Return all words currently in 'learning' status for the user",
)
def read_learning_words(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    1️⃣  Join **Word** ←→ **Word_status**.
    2️⃣  Keep rows where `Word_status.users_id == user_id` *and*
        `Word_status.status == "learning"`.
    3️⃣  Return the matching `Word` ORM objects (FastAPI → Pydantic).
    """
    words = (
        db.query(models.Word)
        .join(
            models.Word_status,
            (models.Word.id == models.Word_status.words_id)
            & (models.Word_status.users_id == user_id)
            & (models.Word_status.status == "learning")
        )
        .order_by(models.Word.word)          # optional: alphabetical
        .all()
    )

    if not words:
        raise HTTPException(
            status_code=404,
            detail="No words with status 'learning' found for this user",
        )

    return words

@router.get(
    "/users/{user_id}/learned-words",
       # change to your own schema type
    summary="Return all words currently in 'learning' status for the user",
)
def read_learning_words(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    1️⃣  Join **Word** ←→ **Word_status**.
    2️⃣  Keep rows where `Word_status.users_id == user_id` *and*
        `Word_status.status == "learning"`.
    3️⃣  Return the matching `Word` ORM objects (FastAPI → Pydantic).
    """
    words = (
        db.query(models.Word)
        .join(
            models.Word_status,
            (models.Word.id == models.Word_status.words_id)
            & (models.Word_status.users_id == user_id)
            & (models.Word_status.status == "learned")
        )
        .order_by(models.Word.word)          # optional: alphabetical
        .all()
    )

    if not words:
        raise HTTPException(
            status_code=404,
            detail="No words with status 'learned' found for this user",
        )

    return words