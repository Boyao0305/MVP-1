"""
Back-up every Word_status.status, then set to "learned" for words
that are NOT tagged "None".

Usage:
    python set_learned_except_none.py
"""

import json
from pathlib import Path
from sqlalchemy import select, update
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models

BACKUP_FILE = Path("status_backup.json")


def main() -> None:
    db: Session = SessionLocal()

    try:
        # -------- 0. Find the "None" tag’s id ---------------------------------
        none_tag = db.execute(
            select(models.Tag).where(models.Tag.name == "None")
        ).scalar_one_or_none()

        if none_tag is None:
            print('❗ Tag "None" not found – nothing will be excluded.')
            none_tag_word_ids = set()
        else:
            none_tag_word_ids = {
                r[0]
                for r in db.execute(
                    select(models.Word_tag_link.word_id).where(
                        models.Word_tag_link.tag_id == none_tag.id
                    )
                )
            }

        # -------- 1. Grab current statuses and save to backup ------------------
        rows = db.execute(
            select(
                models.Word_status.words_id,
                models.Word_status.users_id,
                models.Word_status.status,
            )
        ).all()

        # backup = [
        #     {"word_id": w, "user_id": u, "status": s} for w, u, s in rows
        # ]
        # BACKUP_FILE.write_text(json.dumps(backup, ensure_ascii=False, indent=2))
        # print(f"✔ Backup written to {BACKUP_FILE.resolve()}")
        change = "learned"
        # -------- 2. Bulk-update all eligible rows -----------------------------
        if none_tag_word_ids:
            stmt = (
                update(models.Word_status)
                .where(~models.Word_status.words_id.in_(none_tag_word_ids))
                .values(status=change)
            )
        else:
            stmt = update(models.Word_status).values(status=change)

        result = db.execute(stmt)
        db.commit()
        print(f"✔ Updated {result.rowcount} rows to status={change}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
