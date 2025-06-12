import random
from collections import defaultdict
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
import models                                            # ORM definitions :contentReference[oaicite:0]{index=0}

WORD_BOOK_ID   = 1
BATCH_PER_TAG  = 20

def promote_unlearned_per_tag(
    user_id: int, db: Session
) -> dict[str, list[models.Word_status]]:
    """
    • For each tag, pick ≤60 rows in Word_status that
        – belong to word-book 1,
        – have status 'unlearned'.
    • Flip status→'learning' and set learning_factor=random().
    • Return {tag_name: [Word_status, …]} so we still have learning_factor.
    """
    ws_rows = (
        db.query(models.Word_status)
          .join(models.Word)
          .options(
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_tags),
              joinedload(models.Word_status.l_words).joinedload(models.Word.l_word_books),
          )
          .filter(
              models.Word_status.users_id == user_id,
              models.Word_status.status == "unlearned"
          )
          .all()
    )

    pool: dict[str, list[models.Word_status]] = defaultdict(list)
    for ws in ws_rows:
        w = ws.l_words
        if any(wb.id == WORD_BOOK_ID for wb in w.l_word_books):
            for tag in w.l_tags:
                pool[tag.name].append(ws)

    if not pool:
        raise HTTPException(404, "No matching 'unlearned' words in word-book 1")

    promoted: dict[str, list[models.Word_status]] = {}
    for tag, rows in pool.items():
        chosen = random.sample(rows, min(BATCH_PER_TAG, len(rows)))
        for ws in chosen:
            ws.status = "learning"
            ws.learning_factor = random.random()
        promoted[tag] = chosen     # ⬅ return Word_status rows, not Word objects

    db.commit()
    return promoted