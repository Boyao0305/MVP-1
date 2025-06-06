import random
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models      # adjust import paths as needed

import random
import datetime as dt
from sqlalchemy.orm import Session
from fastapi import HTTPException
import models           # adjust path if your models file lives elsewhere

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

        selected = random.sample(candidates, min(daily_goal, len(candidates)))
        log.daily_new_words.extend(selected)      # inserts into daily_new_word_links
        assigned[log.id] = [w.id for w in selected]

    db.commit()
    return assigned

