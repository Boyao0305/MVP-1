# routers/learning_log_outline.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
import json, os, asyncio
from fastapi.responses import StreamingResponse
import models

from openai import AsyncOpenAI
from database import SessionLocal# ← your pydantic models
       # ← usual DB-session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/api")

# ---------- DashScope-compatible client ------------------------------------
async_client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY", "sk-5ccb1709bc5b4ecbbd3aedaf69ca969b"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# ---------- prompt templates ----------------------------------------------
PROMPT_TMPL_OUTLINE = (
    "词汇：{words}\n\n"
    "请用以上词汇生成一个一百词左右的英语文章大纲（此大纲应能概括一篇五百词英语文章的内容），"
    "再生成与此文章对应的中英文标题；回答应以json的格式输出（"
    '{{"outline":"", "english_title":"", "chinese_title":""}}'
    "）标题语言应生动且吸引人，请模仿微信公众号类似文章的标题"
)

PROMPT_TMPL_ARTICLE = (
    "You are required to write an English article of around 500 words with the following "
    "title and outline, while integrate the following list of vocabulary into your article. "
    "Do not add subtitles.\n"
    "Title = {english_title}\n"
    "Outline = {outline}\n"
    "Vocabulary = {vocab}\n"
    "You are also required to make the article easy to read for the user with the level "
    "of {CEFR}. Please only return the title and the article itself"
)

# ---------- endpoint -------------------------------------------------------
@router.post(
    "/generate_artical/{log_id}",
    response_class=StreamingResponse,         # ← only the article is returned
    summary="Generate outline, titles, then full article for a learning log",
)
async def generate_article_for_log(
    log_id: int,
    db: Session = Depends(get_db),
):
    # 1️⃣ fetch log ---------------------------------------------------------
    log: models.Learning_log | None = (
        db.query(models.Learning_log).filter(models.Learning_log.id == log_id).first()
    )
    if not log:
        raise HTTPException(404, "Learning log not found")
    if not log.daily_new_words:
        raise HTTPException(400, "This log has no daily-new words attached")

    # 2️⃣ first LLM call (outline & titles) ---------------------------------
    words_list = [w.word for w in log.daily_new_words]
    prompt1 = PROMPT_TMPL_OUTLINE.format(words="，".join(words_list))

    outline_resp = await async_client.chat.completions.create(
        model="deepseek-v3",
        messages=[{"role": "user", "content": prompt1}],
    )

    raw = outline_resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.strip("` \n")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    ans = json.loads(raw)

    # 3️⃣ save outline & titles --------------------------------------------
    log.outline        = ans.get("outline", "")
    log.english_title  = ans.get("english_title", "")
    log.chinese_title  = ans.get("chinese_title", "")
    db.commit()
    db.refresh(log)

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

    async def article_stream():
        collected = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                collected.append(text)
                # ⬇ yield bytes so FastAPI sends Transfer-Encoding: chunked
                yield text.encode()
        # update DB once the article is complete
        final_article = "".join(collected).strip()
        log.artical = final_article
        db.commit()

    return StreamingResponse(article_stream(), media_type="text/plain")
