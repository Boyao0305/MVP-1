import random
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models      # adjust import paths as needed

import random
import os, datetime as dt
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models
from typing import Dict, List
from sqlalchemy.orm import Session, joinedload
from openai import OpenAI
import json,re

# adjust path if your models file lives elsewhere

# ──────────────────────────────────────────────────────────────────────────────
#  Helper to convert a numeric “average_caiji” into a CEFR level
# ──────────────────────────────────────────────────────────────────────────────
def _caiji_to_cefr(x: float) -> str:
    """Map average_caiji (1 → 6) to CEFR band."""
    if   1 <= x < 2: return "A1"
    elif 2 <= x < 3: return "A2"
    elif 3 <= x < 4: return "B1"
    elif 4 <= x < 5: return "B2"
    elif 5 <= x < 6: return "C1"
    else:            return "C2"          # covers x ≥ 6 and any unexpected value


# ──────────────────────────────────────────────────────────────────────────────
#  Main service function
# ──────────────────────────────────────────────────────────────────────────────
def create_five_learning_logs(user_id: int, db: Session) -> list[models.Learning_log]:
    """
    1. Confirm user exists.
    2. Fetch user's average_caiji → convert to CEFR.
    3. Random-sample five *distinct* tags.
    4. Insert five Learning_log rows with user_id, tag, CEFR (+ today’s date).
    5. Return the freshly created ORM objects.
    """
    # 1️⃣  Verify user
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2️⃣  Get avg_caiji → CEFR
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(status_code=404, detail="Learning_setting not found")
    cefr_level = _caiji_to_cefr(setting.average_caiji)

    # 3️⃣  Pull tags and pick five unique ones
    tags = db.query(models.Tag).all()
    if len(tags) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 tags in the DB")
    chosen_tags = random.sample(tags, 5)

    # 4️⃣  Build & insert logs (only the required columns)
    today = dt.date.today()
    new_logs = [
        models.Learning_log(
            user_id=user_id,
            tag=tag.name,      # or tag_id=tag.id if you store FK instead of text
            CEFR=cefr_level,   # ← the newly-derived CEFR label
            date=today         # lets you later filter by “today’s” logs if needed
        )
        for tag in chosen_tags
    ]

    db.add_all(new_logs)
    db.commit()                 # generates primary keys
    for log in new_logs:
        db.refresh(log)

    return new_logs

# services.py  (excerpt)

import random, datetime as dt
# from sqlalchemy.orm import Session, joinedload
# from fastapi import HTTPException
# import models         # adjust import path if needed
#
# _CEFR_RANK = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
# def _higher_cefr(w_lvl: str, base: str) -> bool:
#     return _CEFR_RANK.get(w_lvl, -1) >= _CEFR_RANK.get(base, -1)

# services.py  (excerpt)

import random, datetime as dt
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
import models         # adjust import path if needed

_CEFR_RANK = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
def _higher_cefr(w_lvl: str, base: str) -> bool:
    return _CEFR_RANK.get(w_lvl, -1) >= _CEFR_RANK.get(base, -1)

def assign_daily_new_words(user_id: int, db: Session) -> dict[int, list[int]]:
    """Populate today’s five Learning_log rows with <daily_goal> random, *unlearned* words."""
    today = dt.date.today()

    # 1️⃣  Learning-setting → daily_goal + chosen word-book
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(status_code=404, detail="Learning_setting not found")
    daily_goal, word_book_id = setting.daily_goal, setting.chosed_word_book_id
    if word_book_id is None:
        raise HTTPException(status_code=400, detail="No word-book chosen for user")

    # 2️⃣  Fetch the five logs created earlier today
    logs = (
        db.query(models.Learning_log)
          .options(joinedload(models.Learning_log.daily_new_words))
          .filter(models.Learning_log.user_id == user_id,
                  models.Learning_log.date == today)
          .all()
    )
    if len(logs) != 5:
        raise HTTPException(status_code=400,
                            detail=f"Expected 5 logs today, found {len(logs)}")

    # 3️⃣  Pull ALL Word_status rows for this user (eager-join to Word, tags, books)
    word_status_rows = (
        db.query(models.Word_status)
          .join(models.Word)
          .options(
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags),
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_word_books),
          )
          .filter(models.Word_status.users_id == user_id,
                  models.Word_status.status == "unlearned")     # ← **new filter**
          .all()
    )

    # 4️⃣  Build {tag → [Word,…]} pool, but only unlearned words pass through
    pool_by_tag = {}
    for ws in word_status_rows:
        word = ws.l_words
        for tag in word.l_tags:
            pool_by_tag.setdefault(tag.name, []).append(word)

    # 5️⃣  Select and link words for each log
    assigned: dict[int, list[int]] = {}
    for log in logs:
        candidates = [
            w for w in pool_by_tag.get(log.tag, [])
            if any(wb.id == word_book_id for wb in w.l_word_books)
               and _higher_cefr(w.CEFR, log.CEFR)
               and w not in log.daily_new_words
        ]
        if not candidates:
            raise HTTPException(400, f"No suitable words for log {log.id} (tag={log.tag})")

        selected = random.sample(candidates, min(daily_goal//2, len(candidates)))
        log.daily_new_words.extend(selected)      # inserts into daily_new_word_links
        assigned[log.id] = [w.id for w in selected]

    db.commit()
    return assigned

def assign_daily_review_words(user_id: int, db: Session) -> Dict[int, List[models.Word_status]]:
    """
    • For each of today’s 5 Learning_log rows:
        – find 'learning' words with the same tag AND in the chosen word-book
        – sort by learning_factor ↑ and take daily_goal // 2
        – link them via daily_review_word_links
    • Returns {learning_log_id: [Word_status, …]}.
    """
    today = dt.date.today()

    # 1️⃣  pull setting to get daily_goal and chosen word-book
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    daily_goal = setting.daily_goal or 0
    wb_id     = setting.chosed_word_book_id
    if wb_id is None:
        raise HTTPException(400, "User has no chosen word-book")

    # 2️⃣  fetch today’s five logs
    logs = (
        db.query(models.Learning_log)
          .options(joinedload(models.Learning_log.daily_review_words))
          .filter(models.Learning_log.user_id == user_id,
                  models.Learning_log.date == today)
          .all()
    )
    if len(logs) != 5:
        raise HTTPException(400, f"Expected 5 logs today, found {len(logs)}")

    result: Dict[int, List[models.Word_status]] = {}

    for log in logs:
        # 3️⃣  candidate Word_status rows for this tag
        qs = (
            db.query(models.Word_status)
              .join(models.Word)                                    # ws.l_words alias
              .join(models.Word.l_word_books)
              .join(models.Word.l_tags)
              .filter(
                  models.Word_status.users_id == user_id,
                  models.Word_status.status == "learning",
                  models.Word_book.id == wb_id,
                  models.Tag.name == log.tag,
              )
              .order_by(models.Word_status.learning_factor.asc())
              .limit(max(0, daily_goal // 2))
              .all()
        )

        # 4️⃣  link – avoid duplicates on rerun
        for ws in qs:
            if ws.l_words not in log.daily_review_words:
                log.daily_review_words.append(ws.l_words)

        result[log.id] = qs

    db.commit()
    return result

from openai import OpenAI

# build once per worker
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY", "sk-5ccb1709bc5b4ecbbd3aedaf69ca969b"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

PROMPT_TMPL = (
    "词汇：{words}\n\n"
    "请用以上词汇生成一个一百词左右的英语文章大纲（此大纲应能概括一篇五百词英语文章的内容），"
    "再生成与此文章对应的中英文标题；回答应以json的格式输出（"
    '{{"outline":"", "english_title":"", "chinese_title":""}}'
    "）标题语言应生动且吸引人，请模仿微信公众号类似文章的标题"
)

def _call_llm(prompt: str) -> str:
    """One call to DeepSeek-v3; returns the assistant message content."""
    completion = client.chat.completions.create(
        model="deepseek-v3",
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content.strip()

def generate_outlines_for_date(
    user_id: int, for_date: dt.date, db: Session
) -> List[Dict]:
    """
    1. Fetch the five learning-log rows for (user_id, date)
    2. For each row:
       • merge today's new+review words → prompt
       • call LLM
       • parse JSON (handle ```json fences)
       • SAVE outline / english_title / chinese_title into the row
    3. Commit once; return data for the API layer.
    """
    logs = (
        db.query(models.Learning_log)
          .options(
              joinedload(models.Learning_log.daily_new_words),
              joinedload(models.Learning_log.daily_review_words),
          )
          .filter(
              models.Learning_log.user_id == user_id,
              models.Learning_log.date == for_date,
          )
          .all()
    )
    if len(logs) != 5:
        raise HTTPException(
            400, f"Expected 5 logs on {for_date.isoformat()}, found {len(logs)}"
        )

    results: List[Dict] = []

    for log in logs:
        # ① build prompt
        words_set = {w.word for w in (log.daily_new_words + log.daily_review_words)}
        prompt = PROMPT_TMPL.format(words=", ".join(words_set))

        # ② LLM call
        raw = _call_llm(prompt)

        # ③ strip optional ```json fences → parse
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
        try:
            ans = json.loads(cleaned)
        except json.JSONDecodeError:
            ans = {
                "outline": raw,
                "english_title": "",
                "chinese_title": "",
            }

        # ④ SAVE to the Learning_log row
        log.outline        = ans.get("outline", "")
        log.english_title  = ans.get("english_title", "")
        log.chinese_title  = ans.get("chinese_title", "")

        results.append(
            {
                "log": log,
                "prompt": prompt,
                "answer": ans,   # for API response
            }
        )

    # ⑤ one commit for all five rows
    db.commit()

    return results