# routers/learning_log_outline.py — async conversion (minimal behavior changes)
from __future__ import annotations

import datetime
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, conint

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import SessionLocal
from tools.logger import logger
from functions.auth import (
    authenticate_user,
    register_user,
    change_number,
    recover_password,
    create_access_token,
    create_refresh_token,
    get_current_user
)
from models import (
    User,
    Word,
    Learning_log,
    Saved_phrase,
    Daily_new_word_link,
    Daily_review_word_link,
)

# ──────────────────────────────────────────────────────────────────────────────
# Async DB dependency
# ──────────────────────────────────────────────────────────────────────────────
async def get_db():
    async with SessionLocal() as db:
        yield db

router = APIRouter(prefix="/test")

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
class SavedPhraseCreate(BaseModel):

    content: str
    translation: str
    explication: str
    log_id: int
    note: Optional[str] = None

class SavedPhraseResponse(BaseModel):
    content: str
    translation: Optional[str]
    explication: Optional[str]
    log_id: Optional[int] = None
    note: Optional[str] = None

class LearningLogResponse(BaseModel):
    log_id: int
    daily_new_words: List[str]
    daily_review_words: List[str]
    english_title: Optional[str]
    chinese_title: Optional[str]
    article: Optional[str]
    date: Optional[datetime.date] = None

class LearningLogSummary(BaseModel):
    log_id: int
    english_title: Optional[str]
    chinese_title: Optional[str]
    date: Optional[date]
    phrases: List[SavedPhraseResponse]

class SavedPhraseDelete(BaseModel):
    saved_phrase_id: int

class LearningLogWithPhrases(LearningLogResponse):
    phrases: List[SavedPhraseResponse]

class DifficultyUpdate(BaseModel):
    article_difficulty: conint(ge=0)
    word_difficulty: conint(ge=0)

# ──────────────────────────────────────────────────────────────────────────────
# Routes — async implementations
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/save_phrase")
async def save_phrase(data: SavedPhraseCreate, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 save_phrase 请求, user_id={user_id}, log_id={data.log_id}")
    try:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        if not user:
            logger.warning(f"用户不存在, user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        saved_phrase = Saved_phrase(
            user_id=user_id,
            content=data.content,
            translation=data.translation,
            explication=data.explication,
            category="phrase",
            log_id=data.log_id,
        )
        db.add(saved_phrase)
        await db.commit()
        await db.refresh(saved_phrase)

        logger.success(
            f"短语保存成功, saved_phrase_id={saved_phrase.id}, user_id={user_id}"
        )
        return {"message": "Phrase saved successfully", "saved_phrase_id": saved_phrase.id}
    except Exception as e:
        await db.rollback()
        logger.exception(f"短语保存失败, user_id={user_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Phrase save failed")


@router.post("/save_phrase_note")
async def save_phrase_note(
    data: SavedPhraseCreate, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)
):
    user_id = current_user.user_id
    logger.info(
        f"收到 save_phrase_note 请求, user_id={user_id}, log_id={data.log_id}"
    )
    try:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        if not user:
            logger.warning(f"用户不存在, user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        saved_phrase = Saved_phrase(
            user_id=user_id,
            content=data.content,
            translation=data.translation,
            explication=data.explication,
            category="phrase",
            log_id=data.log_id,
            note=data.note,
        )
        db.add(saved_phrase)
        await db.commit()
        await db.refresh(saved_phrase)

        logger.success(
            f"短语+笔记保存成功, saved_phrase_id={saved_phrase.id}, user_id={user_id}"
        )
        return {"message": "Phrase saved successfully", "saved_phrase_id": saved_phrase.id}
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"短语+笔记保存失败, user_id={user_id}, error: {e}"
        )
        raise HTTPException(status_code=500, detail="Phrase with note save failed")


# NOTE: The original file had two identical /unsave_phrase handlers.
# To keep behavior unchanged, both are kept here but implemented async.
@router.delete("/unsave_phrase")
async def delete_saved_phrase(data: SavedPhraseDelete, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    phrase = (
        await db.execute(
            select(Saved_phrase).where(
                Saved_phrase.id == data.saved_phrase_id,
                Saved_phrase.user_id == user_id,
            )
        )
    ).scalars().first()
    if not phrase:
        raise HTTPException(status_code=404, detail="Saved phrase not found")

    await db.delete(phrase)
    await db.commit()
    return {
        "message": "Phrase unsaved (deleted) successfully",
        "saved_phrase_id": data.saved_phrase_id,
    }


@router.delete("/unsave_phrase")
async def delete_saved_phrase_dup(
    data: SavedPhraseDelete, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)
):
    user_id = current_user.user_id
    logger.info(
        f"收到 delete_saved_phrase 请求, saved_phrase_id={data.saved_phrase_id}, user_id={user_id}"
    )
    try:
        phrase = (
            await db.execute(
                select(Saved_phrase).where(
                    Saved_phrase.id == data.saved_phrase_id,
                    Saved_phrase.user_id == user_id,
                )
            )
        ).scalars().first()
        if not phrase:
            logger.warning(
                f"未找到要删除的短语, saved_phrase_id={data.saved_phrase_id}, user_id={user_id}"
            )
            raise HTTPException(status_code=404, detail="Saved phrase not found")

        await db.delete(phrase)
        await db.commit()
        logger.success(
            f"短语删除成功, saved_phrase_id={data.saved_phrase_id}, user_id={user_id}"
        )
        return {
            "message": "Phrase unsaved (deleted) successfully",
            "saved_phrase_id": data.saved_phrase_id,
        }
    except Exception as e:
        await db.rollback()
        logger.exception(
            f"短语删除失败, saved_phrase_id={data.saved_phrase_id}, user_id={user_id}, error: {e}"
        )
        raise HTTPException(status_code=500, detail="Delete phrase failed")


@router.get(
    "/saved_phrases",
    response_model=List[LearningLogSummary],
)
async def get_user_phrases( db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 get_user_phrases 查询, user_id={user_id}")
    try:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        if not user:
            logger.warning(f"用户不存在, user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        log_ids_subq = (
            select(Saved_phrase.log_id)
            .where(
                Saved_phrase.user_id == user_id,
                Saved_phrase.category == "phrase",
                Saved_phrase.log_id.isnot(None),
            )
            .distinct()
            .subquery()
        )

        logs = (
            await db.execute(
                select(Learning_log).where(Learning_log.id.in_(select(log_ids_subq.c.log_id)))
            )
        ).scalars().all()
        logger.debug(f"user_id={user_id} 查询到日志数量: {len(logs)}")

        result: List[LearningLogSummary] = []
        for log in logs:
            phrases = (
                await db.execute(
                    select(Saved_phrase).where(
                        Saved_phrase.user_id == user_id,
                        Saved_phrase.log_id == log.id,
                        Saved_phrase.category == "phrase",
                    )
                )
            ).scalars().all()

            result.append(
                LearningLogSummary(
                    log_id=log.id,
                    english_title=log.english_title,
                    chinese_title=log.chinese_title,
                    date=log.date,
                    phrases=[
                        SavedPhraseResponse(
                            content=p.content,
                            translation=p.translation,
                            explication=p.explication,
                            log_id=p.log_id,
                            note=None,
                        )
                        for p in phrases
                    ],
                )
            )

        logger.success(
            f"user_id={user_id} saved_phrases 查询完成, 返回日志数: {len(result)}"
        )
        return result
    except Exception as e:
        logger.exception(f"用户短语查询失败, user_id={user_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Get saved phrases failed")


@router.get("/save_article/{log_id}")
async def save_article(log_id: int, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 save_article 请求, log_id={log_id}")
    try:
        log = (
            await db.execute(select(Learning_log).where(Learning_log.id == log_id))
        ).scalars().first()
        if not log:
            logger.warning(f"未找到学习日志, log_id={log_id}")
            raise HTTPException(status_code=404, detail="Learning log not found")
        if log.user_id != user_id:
            raise HTTPException(300, "this is not your log")

        log.save = 1
        await db.commit()
        logger.success(f"日志保存成功, log_id={log.id}, save_status={log.save}")
        return {"log_id": log.id, "save_status": log.save}
    except Exception as e:
        await db.rollback()
        logger.exception(f"保存日志失败, log_id={log_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Save article failed")


@router.get("/unsave_article/{log_id}")
async def unsave_article(log_id: int, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 unsave_article 请求, log_id={log_id}")
    try:
        log = (
            await db.execute(select(Learning_log).where(Learning_log.id == log_id))
        ).scalars().first()
        if not log:
            logger.warning(f"未找到学习日志, log_id={log_id}")
            raise HTTPException(status_code=404, detail="Learning log not found")
        if log.user_id != user_id:
            raise HTTPException(300, "this is not your log")
        log.save = 0
        await db.commit()
        logger.success(f"日志取消保存成功, log_id={log.id}, save_status={log.save}")
        return {"log_id": log.id, "save_status": log.save}
    except Exception as e:
        await db.rollback()
        logger.exception(f"取消保存日志失败, log_id={log_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Unsave article failed")


@router.get(
    "/saved_article",
    response_model=List[LearningLogWithPhrases],
)
async def get_user_article(db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 saved_article 查询, user_id={user_id}")
    try:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        if not user:
            logger.warning(f"用户不存在, user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        logs = (
            await db.execute(
                select(Learning_log)
                .options(
                    selectinload(Learning_log.daily_new_words),
                    selectinload(Learning_log.daily_review_words),
                )
                .where(
                    Learning_log.user_id == user_id,
                    Learning_log.artical.isnot(None),
                    Learning_log.save == 1,
                )
            )
        ).scalars().all()
        logger.debug(f"user_id={user_id} 查询到已保存文章日志数量: {len(logs)}")

        result: List[LearningLogWithPhrases] = []
        for log in logs:
            phrases = (
                await db.execute(
                    select(Saved_phrase).where(
                        Saved_phrase.user_id == user_id,
                        Saved_phrase.log_id == log.id,
                        Saved_phrase.category == "phrase",
                    )
                )
            ).scalars().all()

            result.append(
                LearningLogWithPhrases(
                    log_id=log.id,
                    daily_new_words=[w.word for w in log.daily_new_words],
                    daily_review_words=[w.word for w in log.daily_review_words],
                    english_title=log.english_title,
                    chinese_title=log.chinese_title,
                    article=log.artical,
                    date=log.date,
                    phrases=[
                        SavedPhraseResponse(
                            content=p.content,
                            translation=p.translation,
                            explication=p.explication,
                            log_id=p.log_id,
                            note=None,
                        )
                        for p in phrases
                    ],
                )
            )

        logger.success(
            f"user_id={user_id} saved_article 查询完成, 返回日志数: {len(result)}"
        )
        return result
    except Exception as e:
        logger.exception(f"user_id={user_id} 查询 saved_article 接口异常: {e}")
        raise HTTPException(status_code=500, detail="Get saved articles failed")


@router.get("/all_article", response_model=List[LearningLogResponse])
async def get_learning_logs(user_id: int, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.user_id
    logger.info(f"收到 all_article 查询, user_id={user_id}")
    try:
        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        if not user:
            logger.warning(f"用户不存在, user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        logs = (
            await db.execute(
                select(Learning_log)
                .options(
                    selectinload(Learning_log.daily_new_words),
                    selectinload(Learning_log.daily_review_words),
                )
                .where(
                    Learning_log.user_id == user_id,
                    Learning_log.artical.isnot(None),
                )
            )
        ).scalars().all()
        logger.debug(f"user_id={user_id} 查询到已发布文章日志数量: {len(logs)}")

        result: List[LearningLogResponse] = []
        for log in logs:
            result.append(
                LearningLogResponse(
                    log_id=log.id,
                    daily_new_words=[w.word for w in log.daily_new_words],
                    daily_review_words=[w.word for w in log.daily_review_words],
                    english_title=log.english_title,
                    chinese_title=log.chinese_title,
                    article=log.artical,
                    date=log.date,
                )
            )

        logger.success(
            f"user_id={user_id} all_article 查询完成, 返回日志数: {len(result)}"
        )
        return result
    except Exception as e:
        logger.exception(f"user_id={user_id} 查询 all_article 接口异常: {e}")
        raise HTTPException(status_code=500, detail="Get all articles failed")


@router.put("/learning_logs_feedback/{log_id}")
async def update_difficulty(
    log_id: int, diff: DifficultyUpdate, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)
):
    user_id = current_user.user_id
    logger.info(
        f"收到 update_difficulty 请求, log_id={log_id}, article_difficulty={diff.article_difficulty}, word_difficulty={diff.word_difficulty}"
    )
    try:
        learning_log = (
            await db.execute(select(Learning_log).where(Learning_log.id == log_id))
        ).scalars().first()
        if not learning_log:
            logger.warning(f"未找到学习日志, log_id={log_id}")
            raise HTTPException(status_code=404, detail="Learning log not found")
        if learning_log.user_id != user_id:
            raise HTTPException(300, "this is not your log")

        learning_log.article_difficulty = diff.article_difficulty
        learning_log.words_difficulty = diff.word_difficulty
        await db.commit()
        await db.refresh(learning_log)

        logger.success(f"学习日志难度值更新成功, log_id={log_id}")
        return {"message": "Difficulties updated", "log_id": log_id}
    except Exception as e:
        await db.rollback()
        logger.exception(f"学习日志难度值更新异常, log_id={log_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Update difficulty failed")


@router.get(
    "/word_learning_history/{word_id}", response_model=List[dict]
)
async def get_learning_logs_by_word(
    word_id: int, user_id: int, db: AsyncSession = Depends(get_db), current_user: TokenData = Depends(get_current_user)
):
    user_id = current_user.user_id
    logger.info(
        f"收到 word_learning_history 查询, user_id={user_id}, word_id={word_id}"
    )
    try:
        word = (
            await db.execute(select(Word).where(Word.id == word_id))
        ).scalars().first()
        if not word:
            logger.warning(f"未找到单词, word_id={word_id}")
            raise HTTPException(status_code=404, detail="Word not found")

        # Logs where the word is in daily new words
        stmt_new = (
            select(Learning_log)
            .join(
                Daily_new_word_link,
                Learning_log.id == Daily_new_word_link.learning_log_id,
            )
            .where(
                Daily_new_word_link.word_id == word_id,
                Learning_log.artical.isnot(None),
                Learning_log.user_id == user_id,
            )
        )
        logs_new = (await db.execute(stmt_new)).scalars().all()

        # Logs where the word is in daily review words
        stmt_rev = (
            select(Learning_log)
            .join(
                Daily_review_word_link,
                Learning_log.id == Daily_review_word_link.learning_log_id,
            )
            .where(
                Daily_review_word_link.word_id == word_id,
                Learning_log.artical.isnot(None),
                Learning_log.user_id == user_id,
            )
        )
        logs_rev = (await db.execute(stmt_rev)).scalars().all()

        # De-duplicate by log.id while preserving order (new first, then review)
        seen = set()
        learning_logs: List[Learning_log] = []
        for lg in (*logs_new, *logs_rev):
            if lg.id not in seen:
                seen.add(lg.id)
                learning_logs.append(lg)

        logger.debug(
            f"user_id={user_id}, word_id={word_id}，关联学习日志数量: {len(learning_logs)}"
        )

        result = [
            {
                "date": lg.date,
                "english_title": lg.english_title,
                "chinese_title": lg.chinese_title,
            }
            for lg in learning_logs
        ]

        logger.success(
            f"user_id={user_id}, word_id={word_id}，word_learning_history 查询完成"
        )
        return result
    except Exception as e:
        logger.exception(
            f"user_id={user_id}, word_id={word_id}，word_learning_history 查询异常: {e}"
        )
        raise HTTPException(status_code=500, detail="Get word learning history failed")
