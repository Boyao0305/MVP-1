#!/usr/bin/env python
"""
Flip exactly two 'learned' Word_status rows under one tag back to 'unlearned'.

If --user is omitted, *all* users’ rows are considered.
"""

import argparse, random
from sqlalchemy import select, update
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models
from typing import Optional

def pick_two_word_ids(
    db: Session,
    tag_name: str,
    user_id: Optional[int] = None,
) -> list[int]:
    """
    Return up to two word-IDs that
    • carry the given tag  AND
    • already have status == "learned" for that user.
      (If user_id is None, look at ALL users’ rows.)
    """
    # 1️⃣ locate the tag
    tag = db.execute(
        select(models.Tag).where(models.Tag.name == tag_name)
    ).scalar_one_or_none()
    if tag is None:
        raise ValueError(f'Tag "{tag_name}" not found')

    # 2️⃣ build the query:
    #    Word_status ⟶ Word_tag_link (to check the tag)
    stmt = (
        select(models.Word_status.words_id)
        .join(models.Word_tag_link,
              models.Word_tag_link.word_id == models.Word_status.words_id)
        .where(
            models.Word_tag_link.tag_id == tag.id,
            models.Word_status.status == "unlearned",
        )
    )
    if user_id is not None:
        stmt = stmt.where(models.Word_status.users_id == user_id)

    word_ids = [r[0] for r in db.execute(stmt)]
    if not word_ids:
        raise ValueError(
            f'No "learned" words found under tag "{tag_name}"'
            + (f" for user {user_id}" if user_id else "")
        )

    random.shuffle(word_ids)      # avoid always picking the same two
    return word_ids[:2]




def flip_status(
        db: Session,
        word_ids: list[int],
        new_status: str,
        old_status: str = "unlearned",
        user_id: Optional[int] = None,
) -> int:
    """Bulk-update rows and return how many were touched."""
    if not word_ids:
        return 0

    stmt = (
        update(models.Word_status)
        .where(
            models.Word_status.words_id.in_(word_ids),
            models.Word_status.status == old_status,
        )
        .values(status=new_status)
    )

    if user_id is not None:
        stmt = stmt.where(models.Word_status.users_id == user_id)

    res = db.execute(stmt)
    db.commit()
    return res.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag",  required=True, help="Tag name (e.g. Tech)")
    parser.add_argument("--user", type=int,   help="User-ID to restrict update")

    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        to_flip = pick_two_word_ids(db, args.tag)

        changed = flip_status(
            db,
            word_ids=to_flip,
            new_status="learning",
            user_id=args.user,
        )

        if changed == 0:
            print("⚠ Nothing changed - maybe no rows were 'learned' yet.")
        else:
            print(
                f"✔ Set {changed} row(s) (word-ids {to_flip}) "
                f"from 'learned' → 'unlearned'"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
