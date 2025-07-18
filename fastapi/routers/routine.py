# routers/learning_log_outline.py
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
from functions.auth import authenticate_user, register_user
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


       # ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")


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


# ─────────────────────────── route ────────────────────────
@router.get(
    "/daily_learning_logs/{user_id}",
    response_model=DailyLogsWithInfoOut,
    summary="Return today's learning-logs plus user-level info",
)
def read_learning_logs(user_id: int, db: Session = Depends(get_db)):
    # 1️⃣ pick the date (today)
    # target_date = dt.date.today()

    # 2️⃣ all logs for that user/date, with word lists eagerly loaded
    # logs = (
    #     db.query(models.Learning_log)
    #       .options(
    #           joinedload(models.Learning_log.daily_new_words),
    #           joinedload(models.Learning_log.daily_review_words),
    #       )
    #       .filter(
    #           models.Learning_log.user_id == user_id,
    #           models.Learning_log.date == target_date)
    #     .order_by(models.Learning_log.id.desc())
    #     .limit(5)
    #     .all()

    # )
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
    if not logs:
        raise HTTPException(404, "No logs found for that user/date")

    # 3️⃣ pull the user’s learning settings
    setting = (
        db.query(models.Learning_setting)
          .filter(models.Learning_setting.user_id == user_id)
          .first()
    )  # Learning_setting: chosed_word_book_id & daily_goal:contentReference[oaicite:0]{index=0}

    if setting is None:
        # no settings yet ⇒ zero progress, None word_book_id
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

    # 4️⃣ gather all word-IDs in that word-book (middle table word_wordbook_links):contentReference[oaicite:1]{index=1}
    word_ids_subq = (
        select(models.Word_wordbook_link.word_id)
        .where(models.Word_wordbook_link.word_book_id == word_book_id)
        .subquery()
    )
    progression1 = 0
    total_words = db.scalar(select(func.count()).select_from(word_ids_subq)) or 0

    # 5️⃣ count this user’s learning / learned words among that set (word_statuss table):contentReference[oaicite:2]{index=2}
    if total_words == 0:
        learning_prop = learned_prop = 0.0
    else:
        learning_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),  # type: ignore[arg-type]
                models.Word_status.status == "learning",
            )
        ) or 0

        learned_count = db.scalar(
            select(func.count())
            .select_from(models.Word_status)
            .where(
                models.Word_status.users_id == user_id,
                models.Word_status.words_id.in_(word_ids_subq),  # type: ignore[arg-type]
                models.Word_status.status == "learned",
            )
        ) or 0
        # progression = (learning_count + learned_count) / 2
        # progression = round(progression)
        progression1 = learning_count + learned_count
        learning_prop = learning_count / total_words
        learned_prop  = learned_count  / total_words


    info = AdditionalInformation(
        word_book_id=word_book_id,
        daily_goal=daily_goal,
        learning_proportion=learning_prop,
        learned_proportion=learned_prop,
        progression=progression1,
        total=total_words,
    )

    return {"logs": logs, "additional_information": info}

# ---------- DashScope-compatible client ------------------------------------
async_client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY", "sk-5ccb1709bc5b4ecbbd3aedaf69ca969b"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
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
    response_class=StreamingResponse,         # ← only the article is returned
    summary="Generate outline, titles, then full article for a learning log",
)
async def generate_article_for_log(
    log_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    target_date = dt.date.today()
    # 2️⃣ all logs for that user/date, with word lists eagerly loaded
    log = (
        db.query(models.Learning_log)
        .options(
            joinedload(models.Learning_log.daily_new_words),
            joinedload(models.Learning_log.daily_review_words),
        )
        .filter(

            models.Learning_log.id == log_id)
        .order_by(models.Learning_log.id.desc())
        .first()

    )
    # models.Learning_log.date == target_date,
    if not log:
        raise HTTPException(404, "Learning log not found")
    if not log.daily_new_words:
        raise HTTPException(400, "This log has no daily-new words attached")

    # 2️⃣ first LLM call (outline & titles) ---------------------------------
    words_list = [w.word for w in log.daily_new_words]
    for w2 in log.daily_review_words:
        words_list.append(w2.word)

    # 4️⃣ second LLM call (stream out to client) ---------------------------
    prompt2 = PROMPT_TMPL_ARTICLE.format(
        english_title=log.english_title,
        outline=log.outline,
        vocab=", ".join(words_list),
        CEFR=log.CEFR or "A2",
    )

    stream = await async_client.chat.completions.create(
        model="deepseek-v3",
        messages=[{"role": "user", "content": prompt2}],
        stream=True,
    )

    collected = []

    def save_article_to_db(log_id: int, article_text: str):
        from database import SessionLocal  # adjust if your session maker is named differently
        db_bg = SessionLocal()
        try:
            log_to_update = db_bg.query(models.Learning_log).filter(models.Learning_log.id == log_id).first()
            if log_to_update:
                log_to_update.artical = article_text
                db_bg.commit()
                print("✅ Article saved in background")
            else:
                print("❌ Could not find log to update")
        except Exception as e:
            print("❌ Background DB commit failed:", e)
        finally:
            db_bg.close()

    async def article_stream():
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                collected.append(text)
                yield text.encode()

        final_article = "".join(collected).strip()
        background_tasks.add_task(save_article_to_db, log.id, final_article)

    # 🚨 Fix: Create a new session in background thread




    return StreamingResponse(article_stream(), media_type="text/plain")


@router.get("/word_search/{log_id}/{word}")

def word_search(word: str, log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        raise HTTPException(404, detail="Learning log not found")

    # 2️⃣ insert the searched word
    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # With the composite PK (log_id, id) this fires if the *same* word is
        # already linked to the log (or any other PK violation)
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )
    word0 = word.lower()
    forms_to_try = [word]
    output = None
    if word0.endswith("ing") or word0.endswith("ed"):
        # word4 = (
        #     db.query(models.Word)
        #
        #     .filter(
        #         models.Word.word == form
        #     )
        #     .first()
        # )
        # if word4:
        #     print("word1")
        #     output = word1.definition + ", " + word1.phonetic
        #     target_date = dt.date.today()
        #     review_search = (
        #         db.query(models.Learning_log)
        #         .options(
        #             joinedload(models.Learning_log.daily_review_words),
        #         )
        #         .filter(
        #             models.Learning_log.id == log_id, )
        #         .first()
        #
        #     )
        #
        #     if word1 in review_search.daily_review_words:
        #         review_search2 = (
        #             db.query(models.Daily_review_word_link)
        #             .filter(
        #                 models.Daily_review_word_link.learning_log_id == log_id,
        #                 models.Daily_review_word_link.word_id == word1.id,
        #             )
        #             .first()
        #         )
        #         review_search2.review_indicator = 1
        #         db.commit()
        word5 = (
            db.query(models.Dictionary)

            .filter(
                models.Dictionary.word == word0)
            .first()
        )
        if word5:
            output = word5.definition
        else:
            client = OpenAI(
                # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
                api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
                # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

            completion = client.chat.completions.create(
                model="deepseek-v3",  # 此处以 deepseek-r1 为例，可按需更换模型名称。
                messages=[
                    {'role': 'user',
                     'content': f"""请返回{word0}单词的中文定义和音标，请只返回一个或几个词性缩写和对应的中文定义以及单词音标(/的形式），并用逗号隔开 ; 请考虑所有的词性可能性（ed或ing结尾的词可做形容词和动词（过去式和进行式））"""
                     }
                ]
            )

            definition5 = completion.choices[0].message.content
            word6 = Dictionary(word=word0, definition=definition5)
            db.add(word6)
            db.commit()
            output = definition5
    else:

        # Try manual stem variants
        if word0.endswith("ies"):
            forms_to_try.append(word[:-3] + "y")  # studies → study
        # if word0.endswith("ing"):
        #     forms_to_try.append(word[:-3])        # eating → eat
        # if word0.endswith("ed"):
        #     forms_to_try.append(word[:-2])        # worked → work
        if word0.endswith("s") and len(word) > 3:
            forms_to_try.append(word[:-1])        # cars → car
        # return forms_to_try   # Remove duplicates
        forms_to_try = list(dict.fromkeys(forms_to_try))
        #
        # # Try each form

        for form in forms_to_try:
                # result = reverse_dict.get(form)
                word1 = (
                    db.query(models.Word)

                    .filter(
                        models.Word.word == form
                    )
                    .first()
                )
                word2 = (
                    db.query(models.Dictionary)

                             .filter(
                        models.Dictionary.word == form
                    )
                             .first()
                             )
                if word1:
                    print("word1")
                    output = word1.definition+", "+word1.phonetic
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
                    else:
                        pass

                else:
                    pass

                if word2:
                    print("word2")
                    output = word2.definition
                else:
                    pass

        if not output:

            client = OpenAI(
                # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
                api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
                # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

            completion = client.chat.completions.create(
                model="deepseek-v3",  # 此处以 deepseek-r1 为例，可按需更换模型名称。
                messages=[
                    {'role': 'user',
                     'content': f"""请返回{word0}单词的中文定义和音标，请只返回一个或几个词性缩写和对应的中文定义以及单词音标(/的形式），并用逗号隔开"""
                     }
                ]
            )

            definition2 = completion.choices[0].message.content
            word3 = Dictionary(word = word0, definition = definition2 )
            db.add(word3)
            db.commit()
            output = definition2


    return output

@router.get("/english_word_search/{log_id}/{word}")

def word_search(word: str, log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        raise HTTPException(404, detail="Learning log not found")

    # 2️⃣ insert the searched word
    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # With the composite PK (log_id, id) this fires if the *same* word is
        # already linked to the log (or any other PK violation)
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )
    word0 = word.lower()
    forms_to_try = [word]

    # Try manual stem variants
    if word0.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")  # studies → study
    # if word0.endswith("ing"):
    #     forms_to_try.append(word[:-3])        # eating → eat
    # if word0.endswith("ed"):
    #     forms_to_try.append(word[:-2])        # worked → work
    if word0.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])        # cars → car
    # return forms_to_try   # Remove duplicates
    forms_to_try = list(dict.fromkeys(forms_to_try))
    #
    # # Try each form

    for form in forms_to_try:
            # result = reverse_dict.get(form)
            word1 = (
                db.query(models.Word)

                .filter(
                    models.Word.word == form
                )
                .first()
            )
            if word1:
                print("word1")
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






    client = OpenAI(
        # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
        api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
        # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    completion = client.chat.completions.create(
        model="deepseek-v3",  # 此处以 deepseek-r1 为例，可按需更换模型名称。
        messages=[
            {'role': 'user',
             'content': f"""请返回{word0}单词的英文解释和音标，请只返回一个或几个词性缩写和对应的英文解释以及单词音标(/的形式），并用逗号隔开"""
             }
        ]
    )

    definition2 = completion.choices[0].message.content
    output = definition2

    return output

@router.get("/word_unsearch/{log_id}/{word}")

def word_unsearch(word: str, log_id: int, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter_by(id=log_id).first()
    if log is None:
        raise HTTPException(404, detail="Learning log not found")

    # 2️⃣ insert the searched word
    searched = models.Daily_searched_word(word=word, log_id=log_id)
    db.add(searched)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # With the composite PK (log_id, id) this fires if the *same* word is
        # already linked to the log (or any other PK violation)
        raise HTTPException(
            400, detail="This word is already recorded for that log."
        )
    word0 = word.lower()
    forms_to_try = [word]


    # Try manual stem variants
    if word0.endswith("ies"):
        forms_to_try.append(word[:-3] + "y")  # studies → study
    if word0.endswith("ing"):
        forms_to_try.append(word[:-3])        # eating → eat
    if word0.endswith("ed"):
        forms_to_try.append(word[:-2])        # worked → work
    if word0.endswith("s") and len(word) > 3:
        forms_to_try.append(word[:-1])        # cars → car
    # return forms_to_try   # Remove duplicates
    forms_to_try = list(dict.fromkeys(forms_to_try))
    #
    # # Try each form
    output = None
    for form in forms_to_try:
            # result = reverse_dict.get(form)
            word1 = (
                db.query(models.Word)

                .filter(
                    models.Word.word == form
                )
                .first()
            )
            if word1:
                # output = word1.definition+", "+word1.phonetic
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
                    review_search2.review_indicator = 0
                    db.commit()
                    output = "oui"
                else:
                    output = "none"
            else:
                output = "none"
    return output

class LLMRequest(BaseModel):
    content: str
@router.post(
    "/content_search/{category}",
    response_class=StreamingResponse,
    summary="Stream an LLM answer for the given content",
)
async def llm_stream(category: str,req: LLMRequest):
    """Forward `content` to the LLM and stream the raw answer back."""

    # 1️⃣  initialise client (reuse a single instance in real apps)
    client = OpenAI(
        # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
        api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
        # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    prompt_word = f"请给出这个英文词组的中文翻译，请只返回答案本身；如果英文内容不是词组，请返回“内容不是词组”：{req.content}"
    prompt_phrase = f"请猜测语境并给出这个英文句子的中文翻译，请只返回答案本身：{req.content}"
    if category == "word_group":
        prompt = prompt_word
    else:
        prompt = prompt_phrase
    # 2️⃣  start streaming call
    stream = await async_client.chat.completions.create(
        model="deepseek-v3",                # pick the model you like
        messages=[{"role": "user", 'content': prompt}],
        stream=True,
    )

    # 3️⃣  forward tokens to the caller as they arrive
    async def token_gen():
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content.encode()

    return StreamingResponse(token_gen(), media_type="text/plain")
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

    # 1️⃣  initialise client (reuse a single instance in real apps)
    client = OpenAI(
        # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
        api_key="sk-5ccb1709bc5b4ecbbd3aedaf69ca969b",
        # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    prompt_explication = f"请用中文相对简短得解释这个英语句子（长难句）的意思（分模块解释，而非直接给出翻译），再列出中的重要语法点（固定搭配，表达，词组等，请最多挑出3-4点做简短的解释. ）{req.content}"

    # 2️⃣  start streaming call
    stream = await async_client.chat.completions.create(
        model="deepseek-v3",                # pick the model you like
        messages=[{"role": "user", 'content': prompt_explication}],
        stream=True,
    )

    # 3️⃣  forward tokens to the caller as they arrive
    async def token_gen():
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content.encode()

    return StreamingResponse(token_gen(), media_type="text/plain")
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
    log = (
        db.query(models.Learning_log)                     # learning_logs table
          .filter(models.Learning_log.id == log_id)
          .options(joinedload(models.Learning_log.l_user))
          .first()
    )
    if not log:
        raise HTTPException(404, "Learning-log not found")
    log.status = 1
    user_id = log.user_id

    review_links = (
        db.query(models.Daily_review_word_link)           # daily_review_word_links :contentReference[oaicite:0]{index=0}
          .filter(models.Daily_review_word_link.learning_log_id == log_id)
          .all()
    )

    touched, promoted, started= 0, 0, 0
    for link in review_links:
        # if link.review_indicator != 0:
        #     continue                                      # already reviewed

        ws = (
            db.query(models.Word_status)                  # word_statuss :contentReference[oaicite:1]{index=1}
              .filter(
                  models.Word_status.users_id == user_id,
                  models.Word_status.words_id == link.word_id,
              )
              .first()
        )
        if not ws or ws.status == "learned" :
            continue
        if ws.status == "learning":

            if link.review_indicator == 0:

                ws.learning_factor = min(ws.learning_factor + 0.5, 1.0)
                touched += 1
                if ws.learning_factor >= 0.9:
                    ws.status = "learned"
                    promoted += 1
            else:
                continue
        if ws.status == "unlearned":
            ws.status = "learning"
            started += 1

    new_links = (
        db.query(models.Daily_new_word_link)  # daily_review_word_links :contentReference[oaicite:0]{index=0}
        .filter(models.Daily_new_word_link.learning_log_id == log_id)
        .all()
    )

    for link in new_links:
        # if link.review_indicator != 0:
        #     continue                                      # already reviewed

        ws = (
            db.query(models.Word_status)  # word_statuss :contentReference[oaicite:1]{index=1}
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
    db.commit()
    compare_lists_to_text(log_id, db)
    return {
        "log_id": log_id,
        "updated_words": touched,
        "promoted_to_learned": promoted,
        "started_words": started,
    }

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
    setting = (
        db.query(models.Learning_setting)                 # learning_settings :contentReference[oaicite:2]{index=2}
          .filter(models.Learning_setting.user_id == user_id)
          .first()
    )
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    update_average_caiji_for_user(user_id, db)

    # tomorrow = dt.date.today() + dt.timedelta(days=1)
    tomorrow = dt.date.today()

    # ―― pipeline helpers ――――――――――――――――――――――――――――――――――――――――――――――
    create_five_learning_logs(user_id, tomorrow, db)
    assign_daily_new_words(user_id, tomorrow, db)
    assign_daily_review_words(user_id, tomorrow, db)
    outlines = await generate_outlines_for_date_async(user_id, tomorrow, db)

    return {
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

@router.post("/appreciation/{log_id}/{level}")
def article_appreciation(log_id:int, level:int, db: Session = Depends(get_db)):
    log = db.query(models.Learning_log).filter(models.Learning_log.id == log_id).first()
    log.appreciation = level

    if not log:
        raise HTTPException(status_code=404, detail="Learning log or word not found")

    db.commit()

    return {"log":log.id, "level":level}
