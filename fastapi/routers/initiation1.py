from fastapi import APIRouter, Depends, HTTPException, Form,Body
from sqlalchemy.orm import Session
from database import SessionLocal
from functions.auth import authenticate_user, register_user, recover_password, create_access_token, create_refresh_token
from pydantic import BaseModel
import schemas
import datetime as dt
import models
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from functions.auth import refresh_token_store
from functions.new_session import (
    assign_word_book,
    set_daily_goal,
    create_five_learning_logs,
    assign_daily_new_words,
    assign_daily_review_words,
    generate_outlines_for_date_async,
)
from tools.logger import logger
from datetime import datetime, timedelta
router = APIRouter(prefix="/api")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"




# @router.post("/login", response_model=Token)
# def login(form_data: OAuth2PasswordRequestForm = Depends()):
#     user = fake_users_db.get(form_data.username)
#     if not user or user["password"] != form_data.password:
#         raise HTTPException(status_code=400, detail="Incorrect username or password")
#
#     access_token = create_access_token(user_id=user["user_id"], role=user["role"])
#     refresh_token = create_refresh_token(user["user_id"])
#     return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/logintest", response_model=Token)
def login_test(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"收到 logintest 登录请求，username={data.username}")
    user = authenticate_user(db, data.username, data.password)
    if not user:
        logger.warning(f"logintest 登录失败，username={data.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token(user_id=user.id, role="user")
    refresh_token = create_refresh_token(user_id=user.id)
    logger.success(f"logintest 登录成功，user_id={user.id}, username={user.username}")
    return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/login")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"收到 login 登录请求，username={data.username}")
    user = authenticate_user(db, data.username, data.password)
    if not user:
        logger.warning(f"login 登录失败，username={data.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    logger.success(f"login 登录成功，user_id={user.id}, username={user.username}")
    return {"message": "Login successful", "username": user.username, "id": user.id}

@router.post("/register", response_model=schemas.UserResponse)
def register(data: schemas.FullRegisterRequest, db: Session = Depends(get_db)):
    logger.info(f"收到注册请求，username={data.username}, word_book_id={data.chosed_word_book_id}")
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
        logger.success(f"注册成功，user_id={user.id}, username={user.username}")

        access_token = create_access_token(user_id=user["user_id"], role=user["role"])
        refresh_token = create_refresh_token(user["user_id"])
        logger.debug(f"Token 生成成功，user_id={user.id}")

        return schemas.UserResponse(
            id=user.id,
            username=user.username,
            # phone_number=user.phone_number,
            membership=user.membership,
            consecutive_learning=user.consecutive_learning,
            chosed_word_book_id=setting.chosed_word_book_id,
            average_caiji=setting.average_caiji,
            daily_goal=setting.daily_goal,
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except ValueError as e:
        logger.warning(f"注册失败，username={data.username}，原因：{str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"注册服务异常，username={data.username}，原因：{e}")
        raise HTTPException(status_code=500, detail="Internal server error")

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=Token)
def refresh_token(req: RefreshRequest):
    logger.info(f"收到 refresh token 请求")
    tokenstring = req.refresh_token
    token_data = refresh_token_store.get(tokenstring)
    
    if not token_data:
        logger.warning(f"无效的 refresh token: {tokenstring}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if token_data["exp"] < datetime.utcnow():
        logger.warning(f"refresh token 已过期: {tokenstring}")
        del refresh_token_store[tokenstring]
        raise HTTPException(status_code=401, detail="Refresh token expired")

    try:
        new_access = create_access_token(user_id=token_data["user_id"], role="user")
        new_refresh = create_refresh_token(token_data["user_id"])
        del refresh_token_store[tokenstring]
        logger.success(f"user_id={token_data['user_id']} refresh token 刷新成功")
        return Token(access_token=new_access, refresh_token=new_refresh)
    except Exception as e:
        logger.exception(f"refresh token 刷新失败: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")

@router.post("/password_recovery")
def password_recover(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"收到密码找回请求，username={data.username}")
    try:
        user = recover_password(
            db,
            data.username,
            data.password,
        )
        logger.success(f"密码找回成功，user_id={user.id}, username={user.username}")
        return {"message": "recovery successful", "username": user.username, "id": user.id}
    except ValueError as e:
        logger.warning(f"密码找回失败，username={data.username}，原因：{str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"密码找回服务异常，username={data.username}，原因：{e}")
        raise HTTPException(status_code=500, detail="Internal server error")
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
    logger.info(
        f"收到 account_initiation 初始化请求 user_id={user_id}, word_book_id={word_book_id}, daily_goal={daily_goal}"
    )
    today = dt.date.today()
    try:
        # --- 1. word-book & 2. goal ---------------------------------
        assign_word_book(user_id, word_book_id, db)
        logger.info(f"user_id={user_id} 已分配词书 word_book_id={word_book_id}")
        set_daily_goal(user_id, daily_goal, db)
        logger.info(f"user_id={user_id} 今日目标设为 {daily_goal}")

        # --- 3. five logs --------------------------------------------
        logs = create_five_learning_logs(user_id, today, db)
        log_ids = [log.id for log in logs]
        logger.info(f"user_id={user_id} 今日已创建 5 条学习日志: {log_ids}")

        # --- 4. daily-new words --------------------------------------
        new_words = assign_daily_new_words(user_id, today, db)
        logger.info(f"user_id={user_id} 今日新单词分配结果: {new_words}")

        # --- 5. daily-review words -----------------------------------
        review_raw = assign_daily_review_words(user_id, today, db)
        review_words = {
            lid: [ws.l_words.id for ws in ws_list] for lid, ws_list in review_raw.items()
        }
        logger.info(f"user_id={user_id} 今日复习单词分配: {review_words}")

        # --- 6. outlines (async, ~5 parallel LLM calls) --------------
        outlines = await generate_outlines_for_date_async(user_id, today, db)
        logger.info(f"user_id={user_id} 今日大纲生成完毕 outlines_count={len(outlines)}")

        # --- 7. summary payload --------------------------------------
        result = {
            "date": today.isoformat(),
            "log_ids": log_ids,
            "daily_new_word_ids": new_words,
            "daily_review_word_ids": review_words,
            "outlines_saved": [
                {
                    "log_id": item["log"].id,
                    "english_title": item["answer"].get("english_title", ""),
                    "chinese_title": item["answer"].get("chinese_title", ""),
                }
                for item in outlines
            ],
        }
        logger.success(f"user_id={user_id} account_initiation 全流程成功: {result}")
        return result

    except Exception as e:
        logger.exception(f"user_id={user_id} account_initiation 初始化流程异常: {e}")
        raise HTTPException(status_code=500, detail="Account initiation pipeline failed")

DATABASE_VERSION = "v1.0.0"
@router.get("/version")
def get_version():
    logger.info("收到 version 查询请求")
    try:
        version = DATABASE_VERSION
        logger.success(f"查询 version 成功，version={version}")
        return {"version": version}
    except Exception as e:
        logger.exception(f"查询 version 异常: {e}")
        return {"error": "Could not get version"}
# @router.post("/assign_word_book/{user_id}/{word_book_id}", respons    e_model=schemas.Learning_settings)
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
@router.post("/set_daily_goal/{user_id}/{goal}", response_model=schemas.Learning_settings)
def set_daily_goal(user_id: int, goal: int, db: Session = Depends(get_db)):
    logger.info(f"收到 set_daily_goal 请求, user_id={user_id}, goal={goal}")
    try:
        setting = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id).first()
        if not setting:
            logger.warning(f"未找到用户的学习设置, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Learning setting not found for this user")
        setting.daily_goal = goal
        db.commit()
        db.refresh(setting)
        logger.success(f"user_id={user_id} 日目标设置为 {goal} 成功")
        return setting
    except Exception as e:
        logger.exception(f"user_id={user_id} 日目标设置失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")