# routers/auth_routes.py — fully async endpoints (minimal behavior changes)
from __future__ import annotations

import inspect
import datetime as dt
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from tools.logger import logger
from pydantic import BaseModel

# Project imports (kept exactly as in the original)
from functions.auth import (
    authenticate_user,
    register_user,
    change_number,
    recover_password,
    create_access_token,
    create_refresh_token,
    get_current_user
)
from functions.auth import refresh_token_store
from functions.new_session import (
    assign_word_book,
    set_daily_goal as set_daily_goal_helper,
    create_five_learning_logs,
    assign_daily_new_words,
    assign_daily_review_words,
    generate_outlines_for_date_async,
)
import models, schemas

router = APIRouter(prefix="/test")

# ──────────────────────────────────────────────────────────────────────────────
# Async DB dependency
# ──────────────────────────────────────────────────────────────────────────────
async def get_db():
    async with SessionLocal() as db:
        yield db

# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str
class TokenData(BaseModel):
    user_id: int
    role: str

# ──────────────────────────────────────────────────────────────────────────────
# Auth flows
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/logintest", response_model=Token)
async def login_test(data: schemas.Userbase, db: AsyncSession = Depends(get_db)):
    logger.info(f"收到 logintest 登录请求，username={data.username}")

    # Support sync/async implementations of authenticate_user
    if inspect.iscoroutinefunction(authenticate_user):
        user = await authenticate_user(db, data.username, data.password)
    else:
        def _call(sess):
            return authenticate_user(sess, data.username, data.password)
        user = await db.run_sync(_call)

    if not user:
        logger.warning(f"logintest 登录失败，username={data.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(user_id=user.id, role="user")
    refresh_token = create_refresh_token(user_id=user.id)
    logger.success(f"logintest 登录成功，user_id={user.id}, username={getattr(user, 'username', '<unknown>')}")
    return Token(access_token=access_token, refresh_token=refresh_token)


# @router.post("/login")
# async def login(data: schemas.Userbase, db: AsyncSession = Depends(get_db)):
#     logger.info(f"收到 login 登录请求，username={data.username}")
#
#     if inspect.iscoroutinefunction(authenticate_user):
#         user = await authenticate_user(db, data.username, data.password)
#     else:
#         def _call(sess):
#             return authenticate_user(sess, data.username, data.password)
#         user = await db.run_sync(_call)
#
#     if not user:
#         logger.warning(f"login 登录失败，username={data.username}")
#         raise HTTPException(status_code=401, detail="Invalid username or password")
#
#     logger.success(f"login 登录成功，user_id={user.id}, username={getattr(user, 'username', '<unknown>')}")
#     return {"message": "Login successful", "username": user.username, "id": user.id}


@router.post("/register", response_model=schemas.UserResponse)
async def register(data: schemas.FullRegisterRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"收到注册请求，username={data.username}, word_book_id={data.chosed_word_book_id}")
    try:
        # Support sync/async register_user helper
        if inspect.iscoroutinefunction(register_user):
            user, setting = await register_user(
                db,
                data.username,
                data.password,
                data.phone_number,
                data.code,
                data.chosed_word_book_id,
                data.average_caiji,
                data.daily_goal,

            )
        else:
            def _call(sess):
                return register_user(
                    sess,
                    data.username,
                    data.password,
                    data.phone_number,
                    data.code,
                    data.chosed_word_book_id,
                    data.average_caiji,
                    data.daily_goal,

                )
            user, setting = await db.run_sync(_call)

        logger.success(f"注册成功，user_id={user.id}, username={user.username}")

        # ⚠️ Keep original token-generation lines semantically the same
        access_token = create_access_token(user_id=user["user_id"] if isinstance(user, dict) else getattr(user, "id", None), role="user" if isinstance(user, dict) else getattr(user, "role", "user"))
        refresh_token = create_refresh_token(user["user_id"] if isinstance(user, dict) else getattr(user, "id", None))
        logger.debug("Token 生成成功")

        return schemas.UserResponse(
            id=user.id if hasattr(user, "id") else user.get("id"),
            username=user.username if hasattr(user, "username") else user.get("username"),
            membership=user.membership if hasattr(user, "membership") else user.get("membership"),
            consecutive_learning=user.consecutive_learning if hasattr(user, "consecutive_learning") else user.get("consecutive_learning"),
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


@router.post("/refresh", response_model=Token)
async def refresh_token(req: RefreshRequest):
    logger.info("收到 refresh token 请求")
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
async def password_recover(data: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"收到密码找回请求，username={data.username}")

    try:
        if inspect.iscoroutinefunction(recover_password):
            user = await recover_password(db, data.username, data.password, data.phone_number, data.code)
        else:
            def _call(sess):
                return recover_password(sess, data.username, data.password)
            user = await db.run_sync(_call)

        logger.success(f"密码找回成功，user_id={user.id}, username={user.username}")
        return {"message": "recovery successful", "username": user.username, "id": user.id}
    except ValueError as e:
        logger.warning(f"密码找回失败，username={data.username}，原因：{str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"密码找回服务异常，username={data.username}，原因：{e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/change_phone_number")
async def change_phone_number(data: schemas.ChangePhoneNumber, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id

    logger.info(f"收到手机号更换请求，phoner_number={data.phone_number}")

    try:
        if inspect.iscoroutinefunction(change_number):
            user = await change_number(db, user_id, data.phone_number, data.code)
        else:
            def _call(sess):
                return change_number(db, user_id, data.phone_number, data.code)
            user = await db.run_sync(_call)

        logger.success(f"手机号更换成功，user_id={user.id}, phone_number={user.phone_number}")
        return {"message": "recovery successful", "username": user.username, "id": user.id}
    except ValueError as e:
        logger.warning(f"手机号更换失败，username={data.user_id}，原因：{str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"手机号更换服务器异常，username={data.user_id}，原因：{e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/account_initiation/{word_book_id}/{daily_goal}",
    summary="Run the whole daily sequence for one user",
)
async def run_daily_pipeline(
    word_book_id: int,
    daily_goal: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    user_id = current_user.user_id
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
        # 1 & 2: use sync helpers through run_sync if needed
        if inspect.iscoroutinefunction(assign_word_book):
            await assign_word_book(user_id, word_book_id, db)
        else:
            await db.run_sync(lambda s: assign_word_book(user_id, word_book_id, s))
        logger.info(f"user_id={user_id} 已分配词书 word_book_id={word_book_id}")

        if inspect.iscoroutinefunction(set_daily_goal_helper):
            await set_daily_goal_helper(user_id, daily_goal, db)
        else:
            await db.run_sync(lambda s: set_daily_goal_helper(user_id, daily_goal, s))
        logger.info(f"user_id={user_id} 今日目标设为 {daily_goal}")

        # 3: create five logs
        if inspect.iscoroutinefunction(create_five_learning_logs):
            logs = await create_five_learning_logs(user_id, today, db)
        else:
            logs = await db.run_sync(lambda s: create_five_learning_logs(user_id, today, s))
        log_ids = [log.id for log in logs]
        logger.info(f"user_id={user_id} 今日已创建 5 条学习日志: {log_ids}")

        # 4: daily-new words
        if inspect.iscoroutinefunction(assign_daily_new_words):
            new_words = await assign_daily_new_words(user_id, today, db)
        else:
            new_words = await db.run_sync(lambda s: assign_daily_new_words(user_id, today, s))
        logger.info(f"user_id={user_id} 今日新单词分配结果: {new_words}")

        # 5: daily-review words
        if inspect.iscoroutinefunction(assign_daily_review_words):
            review_raw = await assign_daily_review_words(user_id, today, db)
        else:
            review_raw = await db.run_sync(lambda s: assign_daily_review_words(user_id, today, s))
        review_words = {lid: [ws.l_words.id for ws in ws_list] for lid, ws_list in review_raw.items()}
        logger.info(f"user_id={user_id} 今日复习单词分配: {review_words}")

        # 6: outlines (already async)
        outlines = await generate_outlines_for_date_async(user_id, today, db)
        logger.info(f"user_id={user_id} 今日大纲生成完毕 outlines_count={len(outlines)}")

        # 7: summary
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
async def get_version(current_user: TokenData = Depends(get_current_user)):
    logger.info("收到 version 查询请求")
    try:
        version = DATABASE_VERSION
        logger.success(f"查询 version 成功，version={version}")
        return {"version": version}
    except Exception as e:
        logger.exception(f"查询 version 异常: {e}")
        return {"error": "Could not get version"}


@router.post("/set_daily_goal/{goal}", response_model=schemas.Learning_settings)
async def set_daily_goal(goal: int, db: AsyncSession = Depends(get_db),current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 set_daily_goal 请求, user_id={user_id}, goal={goal}")
    try:
        setting = (
            await db.execute(
                select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
            )
        ).scalars().first()
        if not setting:
            logger.warning(f"未找到用户的学习设置, user_id={user_id}")
            raise HTTPException(status_code=404, detail="Learning setting not found for this user")

        setting.daily_goal = goal
        await db.commit()
        await db.refresh(setting)
        logger.success(f"user_id={user_id} 日目标设置为 {goal} 成功")
        return setting
    except Exception as e:
        logger.exception(f"user_id={user_id} 日目标设置失败: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
