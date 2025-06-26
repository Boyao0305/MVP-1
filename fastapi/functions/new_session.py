import random
from sqlalchemy.orm import Session
from fastapi import HTTPException
   # adjust import paths as needed
import asyncio
import os, datetime as dt
from typing import Dict, List
from sqlalchemy.orm import Session, joinedload
from database import SessionLocal
from functions.auth import authenticate_user, register_user
import json,re
from openai import AsyncOpenAI
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
import datetime as dt
from sqlalchemy import and_
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ──────────────────────────────────────────────────────────────────────────────
#  Helper
# ──────────────────────────────────────────────────────────────────────────────


def assign_word_book(
    user_id: int,
    word_book_id: int,
    db: Session = Depends(get_db),
):
    # 1️⃣  Get the learning-setting row (one-to-one with user)
    setting = (
        db.query(models.Learning_setting)
        .filter(models.Learning_setting.user_id == user_id)
        .first()
    )
    if not setting:
        raise HTTPException(
            status_code=404, detail="Learning setting not found for this user"
        )

    # 2️⃣  Make sure the chosen word-book exists
    word_book = (
        db.query(models.Word_book)
        .filter(models.Word_book.id == word_book_id)
        .first()
    )
    if not word_book:
        raise HTTPException(status_code=404, detail="Word book not found")

    # 3️⃣  Update the setting
    setting.chosed_word_book_id = word_book_id

    # 4️⃣  Build the set of word-ids already linked to this user
    existing_word_ids = {
        wid for (wid,) in db.query(models.Word_status.words_id)
        .filter(models.Word_status.users_id == user_id)
        .all()
    }

    # 5️⃣  Create Word_status rows **only** for words in this word-book
    new_status_objects = [
        models.Word_status(
            words_id=word.id,
            users_id=user_id,
            status="unlearned",           # learning_factor defaults to 0.0
        )
        for word in word_book.l_words
        if word.id not in existing_word_ids
    ]

    if new_status_objects:            # bulk insert if there’s anything new
        db.bulk_save_objects(new_status_objects)

    db.commit()
    db.refresh(setting)
    return setting

def set_daily_goal(user_id: int, goal: int, db: Session = Depends(get_db)):
    setting = db.query(models.Learning_setting).filter(models.Learning_setting.user_id == user_id).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Learning setting not found for this user")
    setting.daily_goal = goal
    db.commit()
    db.refresh(setting)
    return setting

def _caiji_to_cefr(x: float) -> str:
    """Map average_caiji (1 → 6) to CEFR band."""
    if   1 <= x < 2: return "A1"
    elif 2 <= x < 3: return "A2"
    elif 3 <= x < 4: return "B1"
    elif 4 <= x < 5: return "B2"
    elif 5 <= x < 6: return "C1"
    else:            return "C2"        # x ≥ 6 or anything unexpected


# ──────────────────────────────────────────────────────────────────────────────
#  Main service function
# ──────────────────────────────────────────────────────────────────────────────

def create_five_learning_logs(user_id: int, today: dt.date, db: Session) -> list[models.Learning_log]:
    """
    1. Verify user exists.
    2. Convert user's average_caiji → CEFR.
    3. Build the list of tags that still have *something* left to learn/review
       for this user (Word_status ∈ {"unlearned", "learning"}).
    4. Pick up to five tags; duplicates are allowed only if <5 eligible tags.
    5. Insert five Learning_log rows (distinct dates+tags) and return them.
    """
    # 1️⃣  Confirm the user
    user = db.query(models.User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # 2️⃣  CEFR from average_caiji
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    cefr_level = _caiji_to_cefr(setting.average_caiji)

    # 3️⃣  Tags with at least one “unlearned” or “learning” word for this user
    eligible_tags = (
        db.query(models.Tag)
          .join(models.Tag.l_words)                                   # Tag → Word
          .join(models.Word_status,
                and_(models.Word_status.words_id == models.Word.id,
                     models.Word_status.users_id == user_id))
          .filter(models.Word_status.status.in_(("unlearned", "learning")))
          .distinct()
          .all()
    )

    if not eligible_tags:       # nothing left to study/review
        raise HTTPException(400, "No tag has words left in 'unlearned' or 'learning' status")

    # 4️⃣  Choose five tags (repeat only if <5 distinct ones)
    chosen_tags = random.sample(eligible_tags, min(5, len(eligible_tags)))
    while len(chosen_tags) < 5:
        chosen_tags.append(random.choice(eligible_tags))  # deliberately allow repeats

    # 5️⃣  Build & insert the logs

    new_logs = [
        models.Learning_log(
            user_id=user_id,
            tag=tag.name,
            CEFR=cefr_level,
            date=today
        )
        for tag in chosen_tags
    ]

    db.add_all(new_logs)
    db.commit()
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


from collections import defaultdict
from sqlalchemy.orm import joinedload, Session
from fastapi import HTTPException
import models

# ──────────────────────────────────────────────────────────────────────────────
def assign_daily_new_words(user_id: int, today: dt.date, db: Session) -> dict[int, list[int]]:
    """
    For each of today’s five newest Learning_log rows:
      • pick ⌊daily_goal/2⌋ words tagged like the log,
      • pick the remaining words from tag == 'None',
      • priority: unlearned → learning,
      • obey same-book & higher-CEFR rules,
      • allow shortage (log may end up with < daily_goal words).
    """
    words_variable = 10
    # 1️⃣  Read daily_goal and chosen word-book
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    daily_goal, word_book_id = 10, setting.chosed_word_book_id
    if word_book_id is None:
        raise HTTPException(400, "No word-book chosen for user")

    # 2️⃣  Get *today’s* five most-recent logs (by id DESC)
    logs = (
        db.query(models.Learning_log)
          .options(joinedload(models.Learning_log.daily_new_words))
          .filter(models.Learning_log.user_id == user_id,
                  models.Learning_log.date == today)
          .order_by(models.Learning_log.id.desc())
          .limit(5)
          .all()
    )
    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")

    # 3️⃣  Load Word_status rows (both UNLEARNED & LEARNING)
    ws_rows = (
        db.query(models.Word_status)
          .join(models.Word)
          .options(
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags),
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_word_books),
          )
          .filter(models.Word_status.users_id == user_id,
                  models.Word_status.status.in_(("unlearned", "learning")))
          .all()
    )

    # 4️⃣  Build multi-level pools: pool[status][tag] = [Word,…]
    pool = defaultdict(lambda: defaultdict(list))          # status → tag → list
    for ws in ws_rows:
        status = ws.status            # 'unlearned' / 'learning'
        word   = ws.l_words
        for tag in word.l_tags:
            pool[status][tag.name].append(word)

    # 5️⃣  Helper to filter pools by book / CEFR / duplicates
    def _candidates(words, log):
        return [
            w for w in words
            if any(wb.id == word_book_id for wb in w.l_word_books)
               and _higher_cefr(w.CEFR, log.CEFR)
               and w not in log.daily_new_words
        ]

    # 6️⃣  Select for each log
    assigned: dict[int, list[int]] = {}

    for log in logs:
        tag_half  = daily_goal // 2                   # from the log’s own tag
        none_half = daily_goal - tag_half            # from tag 'None'
        selected: list[models.Word] = []
        already   = set()                            # ids picked for this log

        # ------- inner helper -------------------------------------------------
        def _pick(tag_name, quota):
            """Return <= quota words from the given tag, respecting priority."""
            out: list[models.Word] = []

            if quota <= 0:
                return out

            # first UNLEARNED
            pool_unl  = _candidates(pool["unlearned" ].get(tag_name, []), log)
            need      = min(quota, len(pool_unl))
            if need:
                out.extend(random.sample(pool_unl, need))
                quota -= need

            # then LEARNING
            if quota > 0:
                pool_lear = _candidates(pool["learning"].get(tag_name, []), log)
                # remove duplicates already selected
                pool_lear = [w for w in pool_lear if w.id not in already]
                need      = min(quota, len(pool_lear))
                if need:
                    out.extend(random.sample(pool_lear, need))

            return out
        # ----------------------------------------------------------------------

        # (A) words from the log’s tag
        tag_words = _pick(log.tag, tag_half)
        selected += tag_words
        already  |= {w.id for w in tag_words}

        # (B) words from the 'None' tag
        none_words = _pick("None", none_half)
        # avoid duplicates in the unlikely event the same word has both tags
        none_words = [w for w in none_words if w.id not in already]
        selected  += none_words

        # (C) link whatever we managed to collect
        if selected:
            log.daily_new_words.extend(selected)
        assigned[log.id] = [w.id for w in selected]   # may be < daily_goal

    db.commit()
    return assigned
from sqlalchemy import func

def assign_daily_review_words(user_id: int, today: dt.date,db: Session) -> Dict[int, List[models.Word_status]]:
    """
    For each of today’s 5 newest Learning_log rows:

      • quota = ⌊daily_goal/2⌋ words with tag == log.tag
      • remainder from tag == 'None'

      • If TOTAL Learning_log rows  >= 20
            – 'learning' words first, then 'unlearned'
            – within each status bucket choose smallest learning_factor,
              but break ties **randomly**
      • If TOTAL Learning_log rows  < 20
            – tag == log.tag  follows the same rule as above
            – tag == 'None'  → IGNORE status 'learning'; pick only
              unlearned words **randomly** (no learning-factor ordering)

      • Always honour:
          – same word-book
          – no duplicates already linked to the log
          – graceful shortage (log may end up with < daily_goal words)

      • Returns {log_id: [Word_status, …]}
    """


    # 1️⃣  settings
    setting = db.query(models.Learning_setting).get(user_id)
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    daily_goal = 10
    wb_id      = setting.chosed_word_book_id
    if wb_id is None:
        raise HTTPException(400, "User has no chosen word-book")

    # ── total Learning_log rows decides None-tag policy ───────────────────────
    total_logs = (
        db.query(func.count(models.Learning_log.id))
          .filter(models.Learning_log.user_id == user_id)
          .scalar()
    )
    allow_learning_in_none = total_logs >= 20     # <20 ⇒ only UNLEARNED for tag 'None'

    # 2️⃣  today’s five newest logs
    logs = (
        db.query(models.Learning_log)
          .options(joinedload(models.Learning_log.daily_review_words))
          .filter(models.Learning_log.user_id == user_id,
                  models.Learning_log.date == today)
          .order_by(models.Learning_log.id.desc())
          .limit(5)
          .all()
    )
    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")

    # 3️⃣  Word_status rows (learning + unlearned) in the chosen word-book
    ws_rows = (
        db.query(models.Word_status)
          .join(models.Word)
          .join(models.Word.l_word_books)
          .options(joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags))
          .filter(models.Word_status.users_id == user_id,
                  models.Word_book.id == wb_id,
                  models.Word_status.status.in_(("learning", "unlearned")))
          .all()
    )

    # 4️⃣  pool[status][tag]  (unsorted – we’ll order / shuffle at pick-time)
    pool = defaultdict(lambda: defaultdict(list))       # status → tag → list[Word_status]
    for ws in ws_rows:
        for tag in ws.l_words.l_tags:
            pool[ws.status][tag.name].append(ws)

    # 5️⃣  helper ----------------------------------------------------------------
    def _ordered_then_random(cands: List[models.Word_status]) -> List[models.Word_status]:
        """
        Return candidates ordered by (learning_factor, random) so ties are randomised.
        """
        return sorted(
            cands,
            key=lambda ws: (ws.learning_factor or 0.0, random.random())
        )

    def _pick(
        tag_name: str,
        quota: int,
        already_word_ids: set[int],
        allow_learning: bool,
        random_unlearned: bool
    ) -> List[models.Word_status]:
        picked: List[models.Word_status] = []

        # (a) status = learning
        if allow_learning and quota > 0:
            candidates = [
                ws for ws in pool["learning"].get(tag_name, [])
                if ws.l_words.id not in already_word_ids
            ]
            candidates = _ordered_then_random(candidates)
            need = min(quota, len(candidates))
            picked.extend(candidates[:need])
            quota -= need

        # (b) status = unlearned
        if quota > 0:
            candidates = [
                ws for ws in pool["unlearned"].get(tag_name, [])
                if ws.l_words.id not in already_word_ids
            ]
            if random_unlearned:
                random.shuffle(candidates)                 # pure random
            else:
                candidates = _ordered_then_random(candidates)
            need = min(quota, len(candidates))
            picked.extend(candidates[:need])

        return picked
    # ---------------------------------------------------------------------------

    # 6️⃣  select & link
    result: Dict[int, List[models.Word_status]] = {}

    for log in logs:
        tag_quota  = daily_goal
        none_quota = daily_goal
        already_ids = {w.id for w in log.daily_review_words}
        selected_ws: List[models.Word_status] = []

        # (A) same-tag words – always allow learning, use ordered-random ties
        ws_tag = _pick(
            tag_name=log.tag,
            quota=tag_quota,
            already_word_ids=already_ids,
            allow_learning=True,
            random_unlearned=False
        )
        selected_ws.extend(ws_tag)
        already_ids.update(ws.l_words.id for ws in ws_tag)

        # (B) 'None'-tag words – behaviour depends on total_logs
        ws_none = _pick(
            tag_name="None",
            quota=none_quota,
            already_word_ids=already_ids,
            allow_learning=allow_learning_in_none,        # False if <20 logs
            random_unlearned=not allow_learning_in_none   # True  if <20 logs
        )
        selected_ws.extend(ws_none)

        # (C) link to the log (avoid dupes on re-run)
        for ws in selected_ws:
            if ws.l_words not in log.daily_review_words:
                log.daily_review_words.append(ws.l_words)

        result[log.id] = selected_ws        # may be shorter than daily_goal

    db.commit()
    return result
from openai import OpenAI

# build once per worker
async_client = AsyncOpenAI(
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
MAX_RETRIES  = 3          # total attempts (1 original + 2 retries)
RETRY_DELAY  = 2.0        # seconds to wait between tries
# ───────────────────  async LLM call  ─────────────────────────
async def _call_llm(prompt: str) -> str:
    r = await async_client.chat.completions.create(
        model="deepseek-v3",
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content.strip()

# ───────────────────  main async helper  ──────────────────────
async def generate_outlines_for_date_async(
    user_id: int,
    today: dt.date,
    db: Session,
) -> List[Dict]:

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # ──────────────────────────────────────────────────────────────
            # 1️⃣ fetch logs (blocking) in a thread
            logs = await run_in_threadpool(
                lambda: (
                    db.query(models.Learning_log)
                      .options(
                          joinedload(models.Learning_log.daily_new_words),
                          joinedload(models.Learning_log.daily_review_words),
                      )
                      .filter(
                          models.Learning_log.user_id == user_id,
                          models.Learning_log.date == today,
                      )
                      .order_by(models.Learning_log.id.desc())
                      .limit(5)
                      .all()
                )
            )

            if len(logs) != 5:
                raise HTTPException(400, f"Expected 5 logs on {today}, found {len(logs)}")

            # 2️⃣ compose prompts
            prompts, metas = [], []
            for log in logs:
                words = {w.word for w in (log.daily_new_words + log.daily_review_words)}
                prompts.append(PROMPT_TMPL.format(words=", ".join(words)))
                metas.append(log)

            # 3️⃣ fire 5 LLM calls in parallel
            raw_answers = await asyncio.gather(*[_call_llm(p) for p in prompts])

            # 4️⃣ parse + save back into ORM objects
            results: List[Dict] = []
            for log, prompt, raw in zip(metas, prompts, raw_answers):
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
                try:
                    ans = json.loads(cleaned)
                except json.JSONDecodeError:
                    ans = {"outline": raw, "english_title": "", "chinese_title": ""}

                log.outline        = ans.get("outline", "")
                log.english_title  = ans.get("english_title", "")
                log.chinese_title  = ans.get("chinese_title", "")

                results.append({"log": log, "prompt": prompt, "answer": ans})

            # 5️⃣ commit once (also in a thread)
            await run_in_threadpool(db.commit)

            return results                     # 🎉 success – exit the retry loop
            # ──────────────────────────────────────────────────────────────

        except Exception as exc:
            # Roll back partial DB work before next try
            await run_in_threadpool(db.rollback)

            if attempt == MAX_RETRIES:
                # No more retries left – re-raise the last error
                raise

            # Optional logging / telemetry
            print(f"[{attempt}/{MAX_RETRIES}] generate_outlines_for_date_async failed: {exc}. Retrying…")

            # Small delay to avoid hammering external services
            await asyncio.sleep(RETRY_DELAY)