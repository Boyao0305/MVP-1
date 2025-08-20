# functions/new_session.py — fully async conversions (DB I/O via AsyncSession)
from __future__ import annotations

import asyncio
import json
import random
import re
from collections import defaultdict
from typing import Dict, List
import datetime as dt

from fastapi import HTTPException
from sqlalchemy import and_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

import models

# LLM client (kept from original behaviour)
from openai import AsyncOpenAI
from key.apikey_vault import APIKeyVault

APIKeyVault = APIKeyVault()
async_client = AsyncOpenAI(
    api_key=APIKeyVault.get_key("DASHSCOPE_API_KEY"),
    base_url=APIKeyVault.get_key("DASHSCOPE_BASE_URL"),
)

# ----------------------- helpers -----------------------

def _caiji_to_cefr(x: float) -> str:
    """Map average_caiji (1 → 6) to CEFR band."""
    if   1 <= x < 2: return "A1"
    elif 2 <= x < 3: return "A2"
    elif 3 <= x < 4: return "B1"
    elif 4 <= x < 5: return "B2"
    elif 5 <= x < 6: return "C1"
    else:            return "C2"        # x ≥ 6 or anything unexpected


# ----------------------- core functions (async) -----------------------

async def assign_word_book(
    user_id: int,
    word_book_id: int,
    db: AsyncSession,
):
    """Assign a word-book to a user and seed missing Word_status rows.
    Behaviour preserved; only DB access changed to async.
    """
    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()
    if not setting:
        raise HTTPException(status_code=404, detail="Learning setting not found for this user")

    word_book = (
        await db.execute(
            select(models.Word_book)
            .options(selectinload(models.Word_book.l_words))
            .where(models.Word_book.id == word_book_id)
        )
    ).scalars().first()
    if not word_book:
        raise HTTPException(status_code=404, detail="Word book not found")

    setting.chosed_word_book_id = word_book_id

    existing_word_ids = set(
        (
            await db.execute(
                select(models.Word_status.words_id).where(models.Word_status.users_id == user_id)
            )
        ).scalars().all()
    )

    new_status_objects = [
        models.Word_status(words_id=w.id, users_id=user_id, status="unlearned")
        for w in word_book.l_words
        if w.id not in existing_word_ids
    ]
    if new_status_objects:
        db.add_all(new_status_objects)

    await db.commit()
    await db.refresh(setting)
    return setting


async def set_daily_goal(user_id: int, goal: int, db: AsyncSession):
    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()
    if not setting:
        raise HTTPException(status_code=404, detail="Learning setting not found for this user")

    setting.daily_goal = goal
    await db.commit()
    await db.refresh(setting)
    return setting


async def create_five_learning_logs(
    user_id: int, today: dt.date, db: AsyncSession
) -> list[models.Learning_log]:
    """
    1. Verify user exists.
    2. Convert user's average_caiji → CEFR.
    3. Build the list of tags that still have *something* left to learn/review
       for this user (Word_status ∈ {"unlearned", "learning"}).
    4. Pick up to five tags; duplicates are allowed only if <5 eligible tags.
    5. Insert five Learning_log rows (distinct dates+tags) and return them.
    """
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()
    if not setting:
        raise HTTPException(404, "Learning_setting not found")

    cefr_level = _caiji_to_cefr(setting.average_caiji)

    eligible_tags = (
        await db.execute(
            select(models.Tag)
            .join(models.Tag.l_words)
            .join(
                models.Word_status,
                and_(
                    models.Word_status.words_id == models.Word.id,
                    models.Word_status.users_id == user_id,
                ),
            )
            .where(models.Word_status.status.in_(("unlearned", "learning")))
            .distinct()
        )
    ).scalars().all()

    if not eligible_tags:
        raise HTTPException(400, "No tag has words left in 'unlearned' or 'learning' status")

    chosen_tags = random.sample(eligible_tags, min(5, len(eligible_tags)))
    while len(chosen_tags) < 5:
        chosen_tags.append(random.choice(eligible_tags))

    new_logs = [
        models.Learning_log(user_id=user_id, tag=tag.name, CEFR=cefr_level, date=today)
        for tag in chosen_tags
    ]
    db.add_all(new_logs)
    await db.commit()
    for log in new_logs:
        await db.refresh(log)
    return new_logs


async def assign_daily_new_words(
    user_id: int, today: dt.date, db: AsyncSession
) -> Dict[int, List[int]]:
    """
    For each of today’s five newest Learning_log rows:
      • pick ⌊daily_goal/2⌋ words tagged like the log,
      • pick the remaining words from tag == 'None',
      • priority: unlearned → learning,
      • obey same-book & higher-CEFR rules,
      • allow shortage (log may end up with < daily_goal words).
    """
    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    daily_goal, word_book_id = 10, setting.chosed_word_book_id
    if word_book_id is None:
        raise HTTPException(400, "No word-book chosen for user")

    logs = (
        await db.execute(
            select(models.Learning_log)
            .options(selectinload(models.Learning_log.daily_new_words))
            .where(models.Learning_log.user_id == user_id, models.Learning_log.date == today)
            .order_by(models.Learning_log.id.desc())
            .limit(5)
        )
    ).scalars().all()
    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")

    ws_result = await db.execute(
        select(models.Word_status)
        .join(models.Word)
        .options(
            joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags),
            joinedload(models.Word_status.l_words).joinedload(models.Word.l_word_books),
        )
        .where(
            models.Word_status.users_id == user_id,
            models.Word_status.status.in_(("unlearned", "learning")),
        )
    )
    ws_rows = ws_result.unique().scalars().all()

    pool = defaultdict(lambda: defaultdict(list))  # status → tag → list[Word]
    for ws in ws_rows:
        status = ws.status
        word = ws.l_words
        for tag in word.l_tags:
            pool[status][tag.name].append(word)

    def _candidates(words, log):
        rank = {"C2": 6, "C1": 5, "B2": 4, "B1": 3, "A2": 2, "A1": 1}
        target_rank = rank.get(log.CEFR, 1)
        buckets: list[list[models.Word]] = [[] for _ in range(target_rank, 0, -1)]
        for w in words:
            if not any(wb.id == word_book_id for wb in w.l_word_books):
                continue
            if w in log.daily_new_words:
                continue
            r = rank.get(w.CEFR, 0)
            if r:
                idx = target_rank - r
                if idx >= 0:
                    buckets[idx].append(w)
        flat = []
        for lst in buckets:
            if lst:
                flat.extend(lst)
                break
        return flat

    assigned: Dict[int, List[int]] = {}

    for log in logs:
        tag_half = daily_goal // 2
        none_half = daily_goal - tag_half
        selected: list[models.Word] = []
        already = set()

        def _pick(tag_name, quota):
            out: list[models.Word] = []
            if quota <= 0:
                return out
            pool_unl = _candidates(pool["unlearned"].get(tag_name, []), log)
            need = min(quota, len(pool_unl))
            if need:
                out.extend(random.sample(pool_unl, need))
                quota -= need
            if quota > 0:
                pool_lear = _candidates(pool["learning"].get(tag_name, []), log)
                pool_lear = [w for w in pool_lear if w.id not in already]
                need = min(quota, len(pool_lear))
                if need:
                    out.extend(random.sample(pool_lear, need))
            return out

        tag_words = _pick(log.tag, tag_half)
        selected += tag_words
        already |= {w.id for w in tag_words}

        none_words = _pick("None", none_half)
        none_words = [w for w in none_words if w.id not in already]
        selected += none_words

        if selected:
            log.daily_new_words.extend(selected)
        assigned[log.id] = [w.id for w in selected]

    await db.commit()
    return assigned


async def assign_daily_review_words(
    user_id: int, today: dt.date, db: AsyncSession
) -> Dict[int, List[models.Word_status]]:
    """See original docstring — behaviour unchanged, async DB now."""
    setting = (
        await db.execute(
            select(models.Learning_setting).where(models.Learning_setting.user_id == user_id)
        )
    ).scalars().first()
    if not setting:
        raise HTTPException(404, "Learning_setting not found")
    daily_goal = 10
    wb_id = setting.chosed_word_book_id
    if wb_id is None:
        raise HTTPException(400, "User has no chosen word-book")

    total_logs = await db.scalar(
        select(func.count(models.Learning_log.id)).where(models.Learning_log.user_id == user_id)
    )
    allow_learning_in_none = (total_logs or 0) >= 20

    logs = (
        await db.execute(
            select(models.Learning_log)
            .options(selectinload(models.Learning_log.daily_review_words))
            .where(models.Learning_log.user_id == user_id, models.Learning_log.date == today)
            .order_by(models.Learning_log.id.desc())
            .limit(5)
        )
    ).scalars().all()
    if len(logs) < 5:
        raise HTTPException(400, f"Need 5 logs for today, found {len(logs)}")

    ws_result = await db.execute(
        select(models.Word_status)
        .join(models.Word)
        .join(models.Word.l_word_books)
        .options(joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags))
        .where(
            models.Word_status.users_id == user_id,
            models.Word_book.id == wb_id,
            models.Word_status.status.in_(("learning", "unlearned")),
        )
    )
    ws_rows = ws_result.unique().scalars().all()

    pool = defaultdict(lambda: defaultdict(list))  # status → tag → list[Word_status]
    for ws in ws_rows:
        for tag in ws.l_words.l_tags:
            pool[ws.status][tag.name].append(ws)

    def _ordered_then_random(cands: List[models.Word_status]) -> List[models.Word_status]:
        return sorted(cands, key=lambda ws: ((ws.learning_factor or 0.0), random.random()))

    def _pick(
        tag_name: str,
        quota: int,
        already_word_ids: set[int],
        allow_learning: bool,
        random_unlearned: bool,
    ) -> List[models.Word_status]:
        picked: List[models.Word_status] = []
        if allow_learning and quota > 0:
            candidates = [
                ws for ws in pool["learning"].get(tag_name, []) if ws.l_words.id not in already_word_ids
            ]
            candidates = _ordered_then_random(candidates)
            need = min(quota, len(candidates))
            picked.extend(candidates[:need])
            quota -= need
        if quota > 0:
            candidates = [
                ws for ws in pool["unlearned"].get(tag_name, []) if ws.l_words.id not in already_word_ids
            ]
            if random_unlearned:
                random.shuffle(candidates)
            else:
                candidates = _ordered_then_random(candidates)
            need = min(quota, len(candidates))
            picked.extend(candidates[:need])
        return picked

    result: Dict[int, List[models.Word_status]] = {}

    for log in logs:
        tag_quota = daily_goal
        none_quota = daily_goal
        already_ids = {w.id for w in log.daily_review_words}
        selected_ws: List[models.Word_status] = []

        ws_tag = _pick(
            tag_name=log.tag,
            quota=tag_quota,
            already_word_ids=already_ids,
            allow_learning=True,
            random_unlearned=False,
        )
        selected_ws.extend(ws_tag)
        already_ids.update(ws.l_words.id for ws in ws_tag)

        ws_none = _pick(
            tag_name="None",
            quota=none_quota,
            already_word_ids=already_ids,
            allow_learning=allow_learning_in_none,
            random_unlearned=not allow_learning_in_none,
        )
        selected_ws.extend(ws_none)

        for ws in selected_ws:
            if ws.l_words not in log.daily_review_words:
                log.daily_review_words.append(ws.l_words)

        result[log.id] = selected_ws

    await db.commit()
    return result
<<<<<<< Updated upstream
from openai import OpenAI

# build once per worker
async_client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY", "sk-5ccb1709bc5b4ecbbd3aedaf69ca969b"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
=======

>>>>>>> Stashed changes

PROMPT_TMPL = (
    "词汇：{words}\n\n"
    "请用以上词汇生成一个一百词左右的英语文章大纲（此大纲应能概括一篇五百词英语文章的内容），"
    "再生成与此文章对应的中英文标题；回答应以json的格式输出（"
    '{{"outline":"", "english_title":"", "chinese_title":""}}'
    "）标题语言应生动且吸引人"
)
MAX_RETRIES = 3
RETRY_DELAY = 2.0

async def _call_llm(prompt: str) -> str:
    r = await async_client.chat.completions.create(
        model="deepseek-v3",
        messages=[{"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content.strip()


async def generate_outlines_for_date_async(
    user_id: int,
    today: dt.date,
    db: AsyncSession,
) -> List[Dict]:
    """Async end-to-end: read logs → call LLMs → save outlines & titles.
    Retries preserved from original implementation.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logs = (
                await db.execute(
                    select(models.Learning_log)
                    .options(
                        selectinload(models.Learning_log.daily_new_words),
                        selectinload(models.Learning_log.daily_review_words),
                    )
                    .where(
                        models.Learning_log.user_id == user_id,
                        models.Learning_log.date == today,
                    )
                    .order_by(models.Learning_log.id.desc())
                    .limit(5)
                )
            ).scalars().all()

            if len(logs) != 5:
                raise HTTPException(400, f"Expected 5 logs on {today}, found {len(logs)}")

            prompts, metas = [], []
            for log in logs:
                words = {w.word for w in (log.daily_new_words + log.daily_review_words)}
                prompts.append(PROMPT_TMPL.format(words=", ".join(words)))
                metas.append(log)

            raw_answers = await asyncio.gather(*[_call_llm(p) for p in prompts])

            results: List[Dict] = []
            for log, prompt, raw in zip(metas, prompts, raw_answers):
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
                try:
                    ans = json.loads(cleaned)
                except json.JSONDecodeError:
                    ans = {"outline": raw, "english_title": "", "chinese_title": ""}

                log.outline = ans.get("outline", "")
                log.english_title = ans.get("english_title", "")
                log.chinese_title = ans.get("chinese_title", "")

                results.append({"log": log, "prompt": prompt, "answer": ans})

            await db.commit()
            return results

        except Exception as exc:
            await db.rollback()
            if attempt == MAX_RETRIES:
                raise
            # Optional log
            print(f"[{attempt}/{MAX_RETRIES}] generate_outlines_for_date_async failed: {exc}. Retrying…")
            await asyncio.sleep(RETRY_DELAY)
