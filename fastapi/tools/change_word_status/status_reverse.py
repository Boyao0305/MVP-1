"""
Restore every Word_status.status using the JSON produced by
set_learned_except_none.py.

Usage:
    python restore_status_from_backup.py
"""

import json
from pathlib import Path
from sqlalchemy import update
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models

BACKUP_FILE = Path("status_backup.json")


def main() -> None:
    if not BACKUP_FILE.exists():
        raise FileNotFoundError(
            "Backup file not found. Did you run set_learned_except_none.py first?"
        )

    backup = json.loads(BACKUP_FILE.read_text())

    db: Session = SessionLocal()
    try:
        # One UPDATE per distinct status is faster than per-row updates
        # so we bucket rows by the old status value.
        by_status: dict[str, list[tuple[int, int]]] = {}
        for row in backup:
            by_status.setdefault(row["status"], []).append(
                (row["word_id"], row["user_id"])
            )

        total = 0
        for status, pairs in by_status.items():
            word_ids, user_ids = zip(*pairs)  # unzip
            stmt = (
                update(models.Word_status)
                .where(
                    models.Word_status.words_id.in_(word_ids),
                    models.Word_status.users_id.in_(user_ids),
                )
                .values(status=status)
            )
            res = db.execute(stmt)
            total += res.rowcount

        db.commit()
        print(f"✔ Restored {total} rows from backup")

    finally:
        db.close()


if __name__ == "__main__":
    main()
