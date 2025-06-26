from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from database import SessionLocal
from functions.auth import authenticate_user, register_user
from pydantic import BaseModel
import schemas
import datetime as dt
import models
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from functions.new_session import (
    assign_word_book,
    set_daily_goal,
    create_five_learning_logs,
    assign_daily_new_words,
    assign_daily_review_words,
    generate_outlines_for_date_async,
)

router = APIRouter(prefix="/api")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.post("/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"message": "Login successful", "username": user.username, "id": user.id}

@router.post("/register", response_model=schemas.UserResponse)
def register(data: schemas.FullRegisterRequest, db: Session = Depends(get_db)):
    try:
        user, setting = register_user(
            db,
            data.username,
            data.password,
            # data.phone_number,
            data.chosed_word_book_id,
            data.average_caiji,
            data.daily_goal,
            data.invitation_code
        )
        return schemas.UserResponse(
            id=user.id,
            username=user.username,
            # phone_number=user.phone_number,
            membership=user.membership,
            consecutive_learning=user.consecutive_learning,
            chosed_word_book_id=setting.chosed_word_book_id,
            average_caiji=setting.average_caiji,
            daily_goal=setting.daily_goal
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/account_initiation/{user_id}/{word_book_id}/{daily_goal}",
    summary="Run the whole daily sequence for one user",
)
async def run_daily_pipeline(
    user_id: int,
    word_book_id: int,
    daily_goal: int,
    db: Session = Depends(get_db),
):
    """
    1️⃣  Link the chosen *word-book* to the user
    2️⃣  Store today’s *daily_goal* in Learning_setting
    3️⃣  Create 5 fresh Learning_log rows for **today**
    4️⃣  Attach today's *daily-new* words to each log
    5️⃣  Attach today's *daily-review* words to each log
    6️⃣  Ask the LLM for outlines + titles and persist them
    7️⃣  Return a compact JSON summary for the caller
    """
    today = dt.date.today()

    # --- 1.  word-book & 2. goal ---------------------------------
    assign_word_book(user_id, word_book_id, db)
    set_daily_goal(user_id, daily_goal, db)

    # --- 3. five logs --------------------------------------------
    logs = create_five_learning_logs(user_id, today, db)
    log_ids = [log.id for log in logs]

    # --- 4. daily-new words --------------------------------------
    new_words = assign_daily_new_words(user_id, today, db)        # {log_id: [word_id,…]}

    # --- 5. daily-review words -----------------------------------
    review_raw = assign_daily_review_words(user_id, today, db)    # {log_id: [Word_status,…]}
    review_words = {
        lid: [ws.l_words.id for ws in ws_list] for lid, ws_list in review_raw.items()
    }

    # --- 6. outlines (async, ~5 parallel LLM calls) --------------
    outlines = await generate_outlines_for_date_async(user_id, today, db)
    # outlines → [{"log": <Learning_log>, "prompt": "...", "answer": {...}}, …]

    # --- 7. summary payload --------------------------------------
    return {
        "date": today.isoformat(),
        "log_ids": log_ids,
        "daily_new_word_ids": new_words,
        "daily_review_word_ids": review_words,
        "outlines_saved": [
            {"log_id": item["log"].id,
             "english_title": item["answer"].get("english_title", ""),
             "chinese_title": item["answer"].get("chinese_title", "")}
            for item in outlines
        ],
    }



# @router.post("/assign_word_book/{user_id}/{word_book_id}", response_model=schemas.Learning_settings)
# def assign_word_book(user_id: int, word_book_id: int, db: Session = Depends(get_db)):
#     setting = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id).first()
#     if not setting:
#         raise HTTPException(status_code=404, detail="Learning setting not found for this user")
#     setting.chosed_word_book_id = word_book_id
#     db.commit()
#     db.refresh(setting)
#     return setting
#
# @router.post(
#     "/assign_word_book/{user_id}/{word_book_id}",
#     response_model=schemas.Learning_settings,  # keep the same schema
# )
# def assign_word_book(
#     user_id: int,
#     word_book_id: int,
#     db: Session = Depends(get_db),
# ):
#     # 1️⃣  Get the learning-setting row (one-to-one with user)
#     setting = (
#         db.query(models.Learning_setting)
#         .filter(models.Learning_setting.user_id == user_id)
#         .first()
#     )
#     if not setting:
#         raise HTTPException(
#             status_code=404, detail="Learning setting not found for this user"
#         )
#
#     # 2️⃣  Make sure the chosen word-book exists
#     word_book = (
#         db.query(models.Word_book)
#         .filter(models.Word_book.id == word_book_id)
#         .first()
#     )
#     if not word_book:
#         raise HTTPException(status_code=404, detail="Word book not found")
#
#     # 3️⃣  Update the setting
#     setting.chosed_word_book_id = word_book_id
#
#     # 4️⃣  Build the set of word-ids already linked to this user
#     existing_word_ids = {
#         wid for (wid,) in db.query(models.Word_status.words_id)
#         .filter(models.Word_status.users_id == user_id)
#         .all()
#     }
#
#     # 5️⃣  Create Word_status rows **only** for words in this word-book
#     new_status_objects = [
#         models.Word_status(
#             words_id=word.id,
#             users_id=user_id,
#             status="unlearned",           # learning_factor defaults to 0.0
#         )
#         for word in word_book.l_words
#         if word.id not in existing_word_ids
#     ]
#
#     if new_status_objects:            # bulk insert if there’s anything new
#         db.bulk_save_objects(new_status_objects)
#
#     db.commit()
#     db.refresh(setting)
#     return setting
#
#
# @router.post("/set_daily_goal/{user_id}/{goal}", response_model=schemas.Learning_settings)
# def set_daily_goal(user_id: int, goal: int, db: Session = Depends(get_db)):
#     setting = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id).first()
#     if not setting:
#         raise HTTPException(status_code=404, detail="Learning setting not found for this user")
#     setting.daily_goal = goal
#     db.commit()
#     db.refresh(setting)
#     return setting