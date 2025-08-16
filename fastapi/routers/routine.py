# routers/learning_log_outline.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, case, func
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models

from openai import AsyncOpenAI,OpenAI
from database import SessionLocal# ← your pydantic models

from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional
from database import SessionLocal
from functions.auth import authenticate_user, register_user, get_current_user
from pydantic import BaseModel
import schemas2
import models
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, select
import datetime as dt
from models import Dictionary
import models                                # ← your ORM models
from functions.new_session import (                    # ← orchestration helpers
    create_five_learning_logs,
    assign_daily_new_words,
    assign_daily_review_words,
    generate_outlines_for_date_async,
)
from functions.cefr import compare_lists_to_text
from functions.cefr2 import update_average_caiji_for_user
import json, os, asyncio

from tools.logger import logger 

       # ← usual DB-session dependency
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

async def get_db():
    async with SessionLocal() as session:
        yield session

router = APIRouter(prefix="/api")

# @app.get("/protected")
# def protected_route(current_user: TokenData = Depends(get_current_user)):
#     # return {"msg": f"Hello User {current_user.user_id}, Role: {current_user.role}"}
#     return current_user
class AdditionalInformation(schemas2.BaseModel):
    word_book_id: Optional[int]
    daily_goal: int
    learning_proportion: float
    learned_proportion: float
    progression: int
    total: int

class DailyLogsWithInfoOut(schemas2.BaseModel):
    logs: list[schemas2.LearningLogDetailOut]
    additional_information: AdditionalInformation

class TokenData(BaseModel):
    user_id: int
    role: str
# ─────────────────────────── route ────────────────────────
@router.get(
    "/daily_learning_logs",
    response_model=DailyLogsWithInfoOut,
    summary="Return today's learning-logs plus user-level info",
)
def read_learning_logs(current_user: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.user_id
    logger.info(f"用户请求 daily_learning_logs, user_id={user_id}")

    # 1️⃣ pick the date (today)
    # target_date = dt.date.today()

    # 2️⃣ all logs for that user/date, with word lists eagerly loaded
    logs = (
        db.query(models.Learning_log)
        .options(
            joinedload(models.Learning_log.daily_new_words),
            joinedload(models.Learning_log.daily_review_words),
        )
        .filter(
            models.Learning_log.user_id == user_id)
        .order_by(models.Learning_log.id.desc())
        .limit(5)
        .all()
    )
    logger.debug(f"查到的 logs 数量: {len(logs)}")

    if not logs:
        logger.warning(f"user {user_id} 未查到 logs")
        raise HTTPException(404, "No logs found for that user/date")

    # 3️⃣ pull the user’s learning settings
    setting = (
        db.query(models.Learning_setting)
          .filter(models.Learning_setting.user_id == user_id)
          .first()
    )
    if setting is None:
        logger.info(f"user {user_id} 未设置学习设置")
        info = AdditionalInformation(
            word_book_id=None,
            daily_goal=0,
            learning_proportion=0.0,
            learned_proportion=0.0,
            progression=0,
            total=0,
        )
        return {"logs": logs, "additional_information": info}

    word_book_id = setting.chosed_word_book_id
    daily_goal = setting.daily_goal
    logger.debug(f"user {user_id} 的 word_book_id={word_book_id}, daily_goal={daily_goal}")

    # 4️⃣ gather all word-IDs in that word-book
    word_ids_subq = (
        select(models.Word_wordbook_link.word_id)
        .where(models.Word_wordbook_link.word_book_id == word_book_id)
        .subquery()
    )
    progression1 = 0
    total_words = db.scalar(select(func.count()).select_from(word_ids_subq)) or 0
    logger.debug(f"user {user_id} 的 word_book_id={word_book_id}，单词总数: {total_words}")

    # 5️⃣ count this user’s learning / learned words among that set
    if total_words == 0:
        learning_prop = learned_prop = 0.0
        logger.info(f"user {user_id} word_book_id={word_book_id} 没有单词")
    else:
        learning_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),
                models.Word_status.status == "learning",
            )
        ) or 0

        learned_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),
                models.Word_status.status == "learned",
            )
        ) or 0
        progression1 = learning_count + learned_count
        learning_prop = learning_count / total_words
        learned_prop  = learned_count  / total_words
        logger.debug(f"user {user_id} 学习中: {learning_count}, 已学会: {learned_count}")

    info = AdditionalInformation(
        word_book_id=word_book_id,
        daily_goal=daily_goal,
        learning_proportion=learning_prop,
        learned_proportion=learned_prop,
        progression=progression1,
        total=total_words,
    )
    logger.success(f"user {user_id} 查询返回成功")
    return {"logs": logs, "additional_information": info}
@router.get("/daily_learning_logs/{user_id}", response_model=DailyLogsWithInfoOut)
async def read_learning_logs(user_id: int, db: AsyncSession = Depends(get_db)):
    # logs
    q_logs = (
        select(models.Learning_log)
        .options(
            selectinload(models.Learning_log.daily_new_words),
            selectinload(models.Learning_log.daily_review_words),
        )
        .where(models.Learning_log.user_id == user_id)
        .order_by(models.Learning_log.id.desc())
        .limit(5)
    )
    logs = (await db.execute(q_logs)).scalars().all()
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found for that user.")

    # settings
    q_set = select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
    setting = (await db.execute(q_set)).scalars().first()

    if setting is None or setting.chosed_word_book_id is None:
        info = AdditionalInformation(
            word_book_id=None,
            daily_goal=setting.daily_goal if setting else 0,
            learning_proportion=0.0,
            learned_proportion=0.0,
            progression=0,
            total=0,
        )
        return {"logs": logs, "additional_information": info}

    word_book_id = setting.chosed_word_book_id
    daily_goal = setting.daily_goal

    word_ids_subq = (
        select(models.Word_wordbook_link.word_id)
        .where(models.Word_wordbook_link.word_book_id == word_book_id)
        .subquery()
    )

    total_words = (
        await db.scalar(select(func.count()).select_from(word_ids_subq))
    ) or 0

    if total_words == 0:
        learning_prop = learned_prop = 0.0
        progression1 = 0
    else:
        result = await db.execute(
            select(
                func.sum(case((models.Word_status.status == "learning", 1), else_=0)),
                func.sum(case((models.Word_status.status == "learned", 1), else_=0)),
            ).where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(select(word_ids_subq.c.word_id)),
            )
        )
        learning_count, learned_count = result.one()

        learning_count = learning_count or 0
        learned_count = learned_count or 0

        progression1 = learning_count + learned_count
        learning_prop = learning_count / total_words
        learned_prop = learned_count / total_words

    info = AdditionalInformation(
        word_book_id=word_book_id,
        daily_goal=daily_goal or 0,
        learning_proportion=round(learning_prop, 4),
        learned_proportion=round(learned_prop, 4),
        progression=progression1,
        total=total_words,
    )
    return {"logs": logs, "additional_information": info}
# @router.get(
#     "/daily_learning_logs/{user_id}",
#     response_model=DailyLogsWithInfoOut,
#     summary="Return today's learning-logs plus user-level info",
# )
# def read_learning_logs(user_id: int, db: Session = Depends(get_db)):
#     logger.info(f"用户请求 daily_learning_logs, user_id={user_id}")
#
#     logs = (
#         db.query(models.Learning_log)
#         .options(
#             joinedload(models.Learning_log.daily_new_words),
#             joinedload(models.Learning_log.daily_review_words),
#         )
#         .filter(
#             models.Learning_log.user_id == user_id)
#         .order_by(models.Learning_log.id.desc())
#         .limit(5)
#         .all()
#     )
#     logger.debug(f"user_id={user_id} 查到的 logs 数量: {len(logs)}")
#
#     if not logs:
#         logger.warning(f"user_id={user_id} 未查到 logs")
#         raise HTTPException(404, "No logs found for that user/date")
#
#     setting = (
#         db.query(models.Learning_setting)
#           .filter(models.Learning_setting.user_id == user_id)
#           .first()
#     )
#     if setting is None:
#         logger.info(f"user_id={user_id} 未设置学习设置")
#         info = AdditionalInformation(
#             word_book_id=None,
#             daily_goal=0,
#             learning_proportion=0.0,
#             learned_proportion=0.0,
#             progression=0,
#             total=0,
#         )
#         return {"logs": logs, "additional_information": info}
#
#     word_book_id = setting.chosed_word_book_id
#     daily_goal = setting.daily_goal
#     logger.debug(f"user_id={user_id} 的 word_book_id={word_book_id}, daily_goal={daily_goal}")
#
#     word_ids_subq = (
#         select(models.Word_wordbook_link.word_id)
#         .where(models.Word_wordbook_link.word_book_id == word_book_id)
#         .subquery()
#     )
#     progression1 = 0
#     total_words = db.scalar(select(func.count()).select_from(word_ids_subq)) or 0
#     logger.debug(f"user_id={user_id} 的 word_book_id={word_book_id}，单词总数: {total_words}")
#
#     if total_words == 0:
#         learning_prop = learned_prop = 0.0
#         logger.info(f"user_id={user_id} word_book_id={word_book_id} 没有单词")
#     else:
#         learning_count = db.scalar(
#             select(func.count())
#             .select_from(models.Word_status)
#             .where(
#                 models.Word_status.users_id == user_id,
#                 models.Word_status.words_id.in_(word_ids_subq),
#                 models.Word_status.status == "learning",
#             )
#         ) or 0
#
#         learned_count = db.scalar(
#             select(func.count())
#             .select_from(models.Word_status)
#             .where(
#                 models.Word_status.users_id == user_id,
#                 models.Word_status.words_id.in_(word_ids_subq),
#                 models.Word_status.status == "learned",
#             )
#         ) or 0
#         progression1 = learning_count + learned_count
#         learning_prop = learning_count / total_words
#         learned_prop  = learned_count  / total_words
#         logger.debug(f"user_id={user_id} 学习中: {learning_count}, 已学会: {learned_count}")
#
#     info = AdditionalInformation(
#         word_book_id=word_book_id,
#         daily_goal=daily_goal,
#         learning_proportion=learning_prop,
#         learned_proportion=learned_prop,
#         progression=progression1,
#         total=total_words,
#     )
#     logger.success(f"user_id={user_id} 查询返回成功")
#     return {"logs": logs, "additional_information": info}

from key.apikey_vault import APIKeyVault

APIKeyVault = APIKeyVault()

# ---------- DashScope-compatible client ------------------------------------
# async_client = AsyncOpenAI(
#     api_key = APIKeyVault.get_key("DASHSCOPE_API_KEY"),
#     base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
# )
async_client = AsyncOpenAI(
    api_key = "sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# ---------- prompt templates ----------------------------------------------
from fastapi.background import BackgroundTasks
from sqlalchemy.orm import joinedload

PROMPT_TMPL_ARTICLE = (
    "You are required to write an English article of around 500 words with the following "
    "title and outline, while integrate the following list of vocabulary into your article. "
    "Do not add subtitles.\n"
    "Title = {english_title}\n"
    "Outline = {outline}\n"
    "Vocabulary = {vocab}\n"
    "You are also required to make the article easy to read for the user with the level "
    "of {CEFR}. Please only return the article itself without marking any word in any form nor returning the title"
)

# ---------- endpoint -------------------------------------------------------
@router.post(
    "/generation/{log_id}",
    response_class=StreamingResponse,
    summary="Generate outline, titles, then full article for a learning log",
)
async def generate_article_for_log(
    log_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    logger.info(f"收到生成学习日志文章请求 log_id={log_id}")
    target_date = dt.date.today()
    try:
        # 查询学习日志
        log = (
            db.query(models.Learning_log)
            .options(
                joinedload(models.Learning_log.daily_new_words),
                joinedload(models.Learning_log.daily_review_words),
            )
            .filter(models.Learning_log.id == log_id)
            .order_by(models.Learning_log.id.desc())
            .first()
        )
        if not log:
            logger.warning(f"log_id={log_id} 未找到学习日志")
            raise HTTPException(404, "Learning log not found")
        if not log.daily_new_words:
            logger.warning(f"log_id={log_id} 没有 daily_new_words")
            raise HTTPException(400, "This log has no daily-new words attached")

        # 组装词汇列表
        words_list = [w.word for w in log.daily_new_words]
        for w2 in log.daily_review_words:
            words_list.append(w2.word)
        logger.debug(f"log_id={log_id} 词汇列表: {words_list}")

        # 构造 LLM prompt
        prompt2 = PROMPT_TMPL_ARTICLE.format(
            english_title=log.english_title,
            outline=log.outline,
            vocab=", ".join(words_list),
            CEFR=log.CEFR or "A2",
        )
        logger.debug(f"log_id={log_id} prompt2: {prompt2[:100]}...")  # 日志中只显示前100字

        # LLM 流式生成
        stream = await async_client.chat.completions.create(
            model="deepseek-v3",
            messages=[{"role": "user", "content": prompt2}],
            stream=True,
        )
        logger.info(f"log_id={log_id} 开始流式生成文章")

        collected = []

        def save_article_to_db(log_id: int, article_text: str):
            from database import SessionLocal  # adjust if your session maker is named differently
            db_bg = SessionLocal()
            try:
                log_to_update = db_bg.query(models.Learning_log).filter(models.Learning_log.id == log_id).first()
                if log_to_update:
                    log_to_update.artical = article_text
                    db_bg.commit()
                    logger.info(f"log_id={log_id} 文章已后台保存")
                else:
                    logger.error(f"log_id={log_id} 未找到日志进行保存")
            except Exception as e:
                logger.exception(f"log_id={log_id} 后台保存文章失败: {e}")
            finally:
                db_bg.close()

        async def article_stream():
            try:
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        collected.append(text)
                        yield text.encode()
                final_article = "".join(collected).strip()
                background_tasks.add_task(save_article_to_db, log.id, final_article)
                logger.success(f"log_id={log_id} 文章流式输出完成，已添加后台保存任务")
            except Exception as e:
                logger.exception(f"log_id={log_id} 文章流式输出异常: {e}")
                raise

        return StreamingResponse(article_stream(), media_type="text/plain")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(f"log_id={log_id} 服务异常: {e}")
        raise HTTPException(500, f"服务异常: {e}")


@router.get("/word_search/{log_id}/{word}")
def word_search(word: str, log_id: int, db: Session = Depends(get_db)):
    logger.info(f"收到 word_search 请求，log_id={log_id}, word={word}")

    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        logger.warning(f"log_id={log_id} 未找到学习日志")
        raise HTTPException(404, detail="Learning log not found")

    # 2️⃣ insert the searched word
    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
        logger.debug(f"log_id={log_id}, word={word} 添加到 Daily_searched_word 成功")
    except IntegrityError:
        db.rollback()
        logger.warning(f"log_id={log_id}, word={word} 已经存在于 Daily_searched_word")
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )

    word0 = word.lower()
    forms_to_try = [word]
    output = None
    if word0.endswith("ing") or word0.endswith("ed"):
        logger.debug(f"尝试直接查字典，word={word0} 结尾为 ing/ed")
        word5 = (
            db.query(models.Dictionary)
            .filter(models.Dictionary.word == word0)
            .first()
        )
        if word5:
            logger.info(f"word={word0} 在 Dictionary 中找到")
            output = word5.definition
        else:
            logger.info(f"word={word0} 未在 Dictionary 中找到，调用 LLM 查询")
            client = OpenAI(
                api_key = APIKeyVault.get_key("DASHSCOPE_API_KEY"),
                base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
            )
            completion = client.chat.completions.create(
                model="deepseek-v3",
                messages=[
                    {'role': 'user',
                     'content': f"""请返回{word0}单词的中文定义和音标，请只返回一个或几个词性缩写和对应的中文定义以及单词音标(/的形式），并用逗号隔开 ; 请考虑所有的词性可能性（ed或ing结尾的词可做形容词和动词（过去式和进行式））"""
                     }
                ]
            )
            definition5 = completion.choices[0].message.content
            word6 = models.Dictionary(word=word0, definition=definition5)
            db.add(word6)
            db.commit()
            logger.info(f"word={word0} 的定义经 LLM 查询并已写入 Dictionary")
            output = definition5
    else:
        if word0.endswith("ies"):
            forms_to_try.append(word[:-3] + "y")
        if word0.endswith("s") and len(word) > 3:
            forms_to_try.append(word[:-1])
        forms_to_try = list(dict.fromkeys(forms_to_try))
        logger.debug(f"尝试 forms: {forms_to_try}")

        for form in forms_to_try:
            word1 = (
                db.query(models.Word)
                .filter(models.Word.word == form)
                .first()
            )
            word2 = (
                db.query(models.Dictionary)
                .filter(models.Dictionary.word == form)
                .first()
            )
            if word1:
                logger.info(f"form={form} 在 Word 表中找到")
                output = word1.definition + ", " + word1.phonetic
                target_date = dt.date.today()
                review_search = (
                    db.query(models.Learning_log)
                    .options(
                        joinedload(models.Learning_log.daily_review_words),
                    )
                    .filter(
                        models.Learning_log.id == log_id,)
                    .first()
                )
                if word1 in review_search.daily_review_words:
                    review_search2 = (
                        db.query(models.Daily_review_word_link)
                        .filter(
                            models.Daily_review_word_link.learning_log_id == log_id,
                            models.Daily_review_word_link.word_id == word1.id,
                        )
                        .first()
                    )
                    review_search2.review_indicator = 1
                    db.commit()
                    logger.debug(f"form={form} review_indicator 已置为1")
            if word2:
                logger.info(f"form={form} 在 Dictionary 找到")
                output = word2.definition

        if not output:
            logger.info(f"forms {forms_to_try} 均未找到，调用 LLM 查询定义")
            client = OpenAI(
                api_key = APIKeyVault.get_key("DASHSCOPE_API_KEY"),
                base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
            )
            completion = client.chat.completions.create(
                model="deepseek-v3",
                messages=[
                    {'role': 'user',
                     'content': f"""请返回{word0}单词的中文定义和音标，请只返回一个或几个词性缩写和对应的中文定义以及单词音标(/的形式），并用逗号隔开"""
                     }
                ]
            )
            definition2 = completion.choices[0].message.content
            word3 = models.Dictionary(word=word0, definition=definition2)
            db.add(word3)
            db.commit()
            logger.info(f"word={word0} 的定义经 LLM 查询并已写入 Dictionary")
            output = definition2

    logger.info(f"word_search 返回结果: {output}")
    return output

@router.get("/english_word_search/{log_id}/{word}")
def word_search(word: str, log_id: int, db: Session = Depends(get_db)):
    logger.info(f"收到 english_word_search 请求 log_id={log_id}, word={word}")

    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        logger.warning(f"log_id={log_id} 未找到学习日志")
        raise HTTPException(404, detail="Learning log not found")

    # 2️⃣ insert the searched word
    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
        logger.debug(f"log_id={log_id}, word={word} 添加到 Daily_searched_word 成功")
    except IntegrityError:
        db.rollback()
        logger.warning(f"log_id={log_id}, word={word} 已经存在于 Daily_searched_word")
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )

    word0 = word.lower()
    forms_to_try = [word]

    # Try manual stem variants
    if word0.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")
    if word0.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])
    forms_to_try = list(dict.fromkeys(forms_to_try))
    logger.debug(f"log_id={log_id}, word={word}, 尝试 forms: {forms_to_try}")

    for form in forms_to_try:
        word1 = (
            db.query(models.Word)
            .filter(models.Word.word == form)
            .first()
        )
        if word1:
            logger.info(f"form={form} 在 Word 表中找到")
            target_date = dt.date.today()
            review_search = (
                db.query(models.Learning_log)
                .options(
                    joinedload(models.Learning_log.daily_review_words),
                )
                .filter(models.Learning_log.id == log_id)
                .first()
            )
            if word1 in review_search.daily_review_words:
                review_search2 = (
                    db.query(models.Daily_review_word_link)
                    .filter(
                        models.Daily_review_word_link.learning_log_id == log_id,
                        models.Daily_review_word_link.word_id == word1.id,
                    )
                    .first()
                )
                review_search2.review_indicator = 1
                db.commit()
                logger.debug(f"form={form} review_indicator 已置为1")

    # LLM 查询
    try:
        client = OpenAI(
            api_key=APIKeyVault.get_key("DASHSCOPE_API_KEY"),
            base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
        )

        completion = client.chat.completions.create(
            model="deepseek-v3",
            messages=[
                {'role': 'user',
                 'content': f"""请返回{word0}单词的英文解释和音标，请只返回一个或几个词性缩写和对应的英文解释以及单词音标(/的形式），并用逗号隔开"""
                 }
            ]
        )
        definition2 = completion.choices[0].message.content
        logger.info(f"word={word0} LLM 英文释义查询成功")
        output = definition2
    except Exception as e:
        logger.exception(f"log_id={log_id}, word={word0} LLM 查询异常: {e}")
        raise HTTPException(500, f"LLM 查询异常: {e}")

    logger.info(f"english_word_search 返回结果: {output}")
    return output

@router.get("/word_unsearch/{log_id}/{word}")
def word_unsearch(word: str, log_id: int, db: Session = Depends(get_db)):
    logger.info(f"收到 word_unsearch 请求 log_id={log_id}, word={word}")

    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        logger.warning(f"log_id={log_id} 未找到学习日志")
        raise HTTPException(404, detail="Learning log not found")

    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
        logger.debug(f"log_id={log_id}, word={word} 添加到 Daily_searched_word 成功")
    except IntegrityError:
        db.rollback()
        logger.warning(f"log_id={log_id}, word={word} 已经存在于 Daily_searched_word")
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )

    word0 = word.lower()
    forms_to_try = [word]

    if word0.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")
    if word0.endswith("ing"):
        forms_to_try.append(word[:-3])
    if word0.endswith("ed"):
        forms_to_try.append(word[:-2])
    if word0.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])
    forms_to_try = list(dict.fromkeys(forms_to_try))
    logger.debug(f"word_unsearch forms_to_try: {forms_to_try}")

    output = None
    for form in forms_to_try:
        word1 = (
            db.query(models.Word)
            .filter(models.Word.word == form)
            .first()
        )
        if word1:
            logger.info(f"form={form} 在 Word 表中找到，检查是否为 daily_review_words")
            review_search = (
                db.query(models.Learning_log)
                .options(
                    joinedload(models.Learning_log.daily_review_words),
                )
                .filter(models.Learning_log.id == log_id)
                .first()
            )
            if word1 in review_search.daily_review_words:
                review_search2 = (
                    db.query(models.Daily_review_word_link)
                    .filter(
                        models.Daily_review_word_link.learning_log_id == log_id,
                        models.Daily_review_word_link.word_id == word1.id,
                    )
                    .first()
                )
                if review_search2:
                    review_search2.review_indicator = 0
                    db.commit()
                    logger.info(f"log_id={log_id}, word_id={word1.id} review_indicator 已置为0")
                    output = "oui"
                else:
                    logger.warning(f"log_id={log_id}, word_id={word1.id} 未找到 Daily_review_word_link")
                    output = "none"
            else:
                logger.info(f"form={form} 不在该日志的 daily_review_words")
                output = "none"
        else:
            logger.info(f"form={form} 未在 Word 表找到")
            output = "none"

    logger.info(f"word_unsearch 返回: {output}")
    return output

class LLMRequest(BaseModel):
    content: str
@router.post(
    "/content_search/{category}",
    response_class=StreamingResponse,
    summary="Stream an LLM answer for the given content",
)
async def llm_stream(category: str, req: LLMRequest):
    """Forward `content` to the LLM and stream the raw answer back."""
    logger.info(f"收到 content_search 请求, category={category}, content={req.content}")

    try:
        client = OpenAI(
            api_key = APIKeyVault.get_key("DASHSCOPE_API_KEY"),
            base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
        )
        prompt_word = f"请给出这个英文词组的中文翻译，请只返回答案本身；如果英文内容不是词组，请返回“内容不是词组”：{req.content}"
        prompt_phrase = f"请猜测语境并给出这个英文句子的中文翻译，请只返回答案本身：{req.content}"
        if category == "word_group":
            prompt = prompt_word
        else:
            prompt = prompt_phrase
        logger.debug(f"category={category}, prompt={prompt}")

        # 开始流式 LLM 调用
        stream = await async_client.chat.completions.create(
            model="deepseek-v3",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        logger.info(f"category={category}, LLM 流式生成开始")

        async def token_gen():
            try:
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content.encode()
                logger.info(f"category={category}, content_search 流式输出完成")
            except Exception as e:
                logger.exception(f"category={category}, content_search 流式输出异常: {e}")
                raise

        return StreamingResponse(token_gen(), media_type="text/plain")
    except Exception as e:
        logger.exception(f"category={category}, content_search 服务异常: {e}")
        raise HTTPException(500, f"服务异常: {e}")
class LLMRequest2(BaseModel):
    content: str
    translation: str
@router.post(
    "/phrase_explanation/{user_id}",
    response_class=StreamingResponse,
    summary="Stream an LLM answer for the given content",
)
async def llm_stream(user_id: int, req: LLMRequest2):
    """Forward `content` to the LLM and stream the raw answer back."""
    logger.info(f"收到 phrase_explanation 请求, user_id={user_id}, content={req.content}")

    try:
        client = OpenAI(
            api_key = APIKeyVault.get_key("DASHSCOPE_API_KEY"),
            base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
        )

        prompt_explication = (
            f"请用中文相对简短得解释这个英语句子（长难句）的意思（分模块解释，而非直接给出翻译），"
            f"再列出中的重要语法点（固定搭配，表达，词组等，请最多挑出3-4点做简短的解释. ）{req.content}"
        )
        logger.debug(f"user_id={user_id}, prompt_explication={prompt_explication}")

        stream = await async_client.chat.completions.create(
            model="deepseek-v3",
            messages=[{"role": "user", 'content': prompt_explication}],
            stream=True,
        )
        logger.info(f"user_id={user_id}, LLM 流式生成开始")

        async def token_gen():
            try:
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content.encode()
                logger.success(f"user_id={user_id}, phrase_explanation 流式输出完成")  # 用 success 记录完成
            except Exception as e:
                logger.exception(f"user_id={user_id}, phrase_explanation 流式输出异常: {e}")
                raise

        return StreamingResponse(token_gen(), media_type="text/plain")
    except Exception as e:
        logger.exception(f"user_id={user_id}, phrase_explanation 服务异常: {e}")
        raise HTTPException(500, f"服务异常: {e}")
# --------------------------- main endpoint -------------------------------
@router.post(
    "/finish_reading/{log_id}",
    summary="Update learning_factor after a review session",
)
def review_update(
    log_id: int,
    db: Session = Depends(get_db),
):
    """
    • For every review word in the given learning-log:
        – if `review_indicator == 0` **and** the user’s `Word_status.status`
          is **learning**, add 0.5 to `learning_factor`.
        – When the factor reaches ≥ 0.9, flip status → *learned*.
    • All other cases are skipped.
    """
    logger.info(f"收到 finish_reading 请求, log_id={log_id}")
    try:
        log = (
            db.query(models.Learning_log)
              .filter(models.Learning_log.id == log_id)
              .options(joinedload(models.Learning_log.l_user))
              .first()
        )
        if not log:
            logger.warning(f"log_id={log_id} 未找到学习日志")
            raise HTTPException(404, "Learning-log not found")
        log.status = 1
        user_id = log.user_id

        review_links = (
            db.query(models.Daily_review_word_link)
              .filter(models.Daily_review_word_link.learning_log_id == log_id)
              .all()
        )

        touched, promoted, started = 0, 0, 0
        for link in review_links:
            ws = (
                db.query(models.Word_status)
                  .filter(
                      models.Word_status.users_id == user_id,
                      models.Word_status.words_id == link.word_id,
                  )
                  .first()
            )
            if not ws or ws.status == "learned":
                continue
            if ws.status == "learning":
                if link.review_indicator == 0:
                    old_factor = ws.learning_factor
                    ws.learning_factor = min(ws.learning_factor + 0.5, 1.0)
                    touched += 1
                    logger.debug(f"log_id={log_id}, word_id={link.word_id} learning_factor: {old_factor}→{ws.learning_factor}")
                    if ws.learning_factor >= 0.9:
                        ws.status = "learned"
                        promoted += 1
                        logger.info(f"log_id={log_id}, word_id={link.word_id} 已晋升为 learned")
                else:
                    continue
            if ws.status == "unlearned":
                ws.status = "learning"
                started += 1
                logger.info(f"log_id={log_id}, word_id={link.word_id} 状态从 unlearned→learning")

        new_links = (
            db.query(models.Daily_new_word_link)
            .filter(models.Daily_new_word_link.learning_log_id == log_id)
            .all()
        )

        for link in new_links:
            ws = (
                db.query(models.Word_status)
                .filter(
                    models.Word_status.users_id == user_id,
                    models.Word_status.words_id == link.word_id,
                )
                .first()
            )
            if not ws or ws.status == "learned":
                continue
            if ws.status == "learning":
                continue
            if ws.status == "unlearned":
                ws.status = "learning"
                started += 1
                logger.info(f"log_id={log_id}, word_id={link.word_id} 新单词状态从 unlearned→learning")

        db.commit()
        logger.success(f"log_id={log_id} finish_reading 状态更新完成，touched={touched}, promoted={promoted}, started={started}")

        compare_lists_to_text(log_id, db)

        return {
            "log_id": log_id,
            "updated_words": touched,
            "promoted_to_learned": promoted,
            "started_words": started,
        }
    except Exception as e:
        logger.exception(f"log_id={log_id} finish_reading 服务异常: {e}")
        raise HTTPException(500, f"服务异常: {e}")

# ------------------------------------------------------------------------
# 2️⃣  Next-day preparation endpoint
# ------------------------------------------------------------------------
@router.post(
    "/finish_study/{user_id}",
    summary="Create tomorrow’s logs & outlines for a user",
)
async def prepare_tomorrow(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    • Reads `Learning_setting` for the user
    • Runs the entire *tomorrow* pipeline:
      logs → new words → review words → LLM outlines
    """
    logger.info(f"收到 finish_study 请求 user_id={user_id}")
    try:
        setting = (
            db.query(models.Learning_setting)
              .filter(models.Learning_setting.user_id == user_id)
              .first()
        )
        if not setting:
            logger.warning(f"user_id={user_id} 没有找到 Learning_setting")
            raise HTTPException(404, "Learning_setting not found")

        update_average_caiji_for_user(user_id, db)
        logger.info(f"user_id={user_id} 已更新平均采集值")

        # tomorrow = dt.date.today() + dt.timedelta(days=1)
        tomorrow = dt.date.today()
        logger.info(f"user_id={user_id} 目标日期: {tomorrow}")

        create_five_learning_logs(user_id, tomorrow, db)
        logger.info(f"user_id={user_id} 已创建5条学习日志")

        assign_daily_new_words(user_id, tomorrow, db)
        logger.info(f"user_id={user_id} 已分配每日新单词")

        assign_daily_review_words(user_id, tomorrow, db)
        logger.info(f"user_id={user_id} 已分配每日复习单词")

        outlines = await generate_outlines_for_date_async(user_id, tomorrow, db)
        logger.info(f"user_id={user_id} 已生成并保存所有日志大纲 outlines_count={len(outlines)}")

        result = {
            "date_prepared": tomorrow.isoformat(),
            "daily_goal": setting.daily_goal,
            "chosed_word_book_id": setting.chosed_word_book_id,
            "outlines_saved": [
                {
                    "log_id": item["log"].id,
                    "english_title": item["answer"].get("english_title", ""),
                    "chinese_title": item["answer"].get("chinese_title", ""),
                }
                for item in outlines
            ],
        }
        logger.success(f"user_id={user_id} finish_study 全部流程成功: {result}")
        return result

    except Exception as e:
        logger.exception(f"user_id={user_id} finish_study 服务异常: {e}")
        raise HTTPException(500, f"服务异常: {e}")

@router.post("/appreciation/{log_id}/{level}")
def article_appreciation(log_id: int, level: int, db: Session = Depends(get_db)):
    logger.info(f"收到 appreciation 打分请求, log_id={log_id}, level={level}")

    log = db.query(models.Learning_log).filter(models.Learning_log.id == log_id).first()
    if not log:
        logger.warning(f"学习日志 log_id={log_id} 未找到")
        raise HTTPException(status_code=404, detail="Learning log not found")

    log.appreciation = level
    logger.debug(f"log_id={log_id} appreciation 设为 {level}")

    try:
        db.commit()
        logger.success(f"log_id={log_id} appreciation 提交成功，level={level}")
    except Exception as e:
        db.rollback()
        logger.exception(f"log_id={log_id} appreciation 提交失败: {e}")
        raise HTTPException(status_code=500, detail="Database commit failed")

    return {"log": log.id, "level": level}
