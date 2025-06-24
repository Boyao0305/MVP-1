#!/usr/bin/env python
"""
Flip up to N (default 30) words in a given word-book from
status='unlearned' → 'learned' for one user.

Examples
--------
# default 30 words
python set_wordbook_learned.py --wordbook "CET-4" --user 5

# pick a specific word-book by id and only 10 words
python set_wordbook_learned.py --wordbook-id 3 --user 5 --count 10
"""
import argparse, random
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.orm import Session

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))
from database import SessionLocal
import models


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def locate_wordbook(db: Session,
                    name: Optional[str] = None,
                    book_id: Optional[int] = None) -> models.Word_book:
    """Return the Word_book row, keyed by name OR id."""
    if name is None and book_id is None:
        raise ValueError("Either --wordbook or --wordbook-id is required")

    if name is not None:
        wordbook = db.execute(
            select(models.Word_book).where(models.Word_book.name == name)
        ).scalar_one_or_none()
        kind, key = "name", name
    else:
        wordbook = db.execute(
            select(models.Word_book).where(models.Word_book.id == book_id)
        ).scalar_one_or_none()
        kind, key = "id", book_id

    if wordbook is None:
        raise ValueError(f"Word-book with {kind} {key!r} not found")
    return wordbook


def candidate_word_ids(db: Session,
                       wb_id: int,
                       user_id: int,
                       max_n: int) -> List[int]:
    """
    Return up to max_n word-ids that
      • belong to the word-book
      • already have status == 'unlearned' for this user
    """
    stmt = (
        select(models.Word_status.words_id)
        # Word_status ⟶ (word_id) ⟵ Word_wordbook_link
        .join(
            models.Word_wordbook_link,
            models.Word_wordbook_link.word_id == models.Word_status.words_id
        )
        .where(
            models.Word_wordbook_link.word_book_id == wb_id,
            models.Word_status.users_id == user_id,
            models.Word_status.status == "unlearned",
        )
    )

    ids = [r[0] for r in db.execute(stmt)]
    random.shuffle(ids)
    return ids[:max_n]


def flip_to_learned(db: Session,
                    word_ids: List[int],
                    user_id: int) -> int:
    """Bulk-update; return #rows modified."""
    if not word_ids:
        return 0

    res = db.execute(
        update(models.Word_status)
        .where(
            models.Word_status.users_id == user_id,
            models.Word_status.words_id.in_(word_ids),
            models.Word_status.status == "unlearned",
        )
        .values(status="learned")
    )
    db.commit()
    return res.rowcount


# --------------------------------------------------------------------------- #
# main CLI                                                                    #
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--wordbook", help="Word-book name (unique)")
    g.add_argument("--wordbook-id", type=int, help="Word-book id")
    parser.add_argument("--user", type=int, required=True,
                        help="User-id whose rows you want to update")
    parser.add_argument("--count", type=int, default=30,
                        help="How many words to flip (default 30)")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        wb = locate_wordbook(db, args.wordbook, args.wordbook_id)
        pick = candidate_word_ids(db, wb.id, args.user, args.count)

        if not pick:
            print("⚠ No 'unlearned' words found for this user in that word-book.")
            return

        changed = flip_to_learned(db, pick, args.user)
        print(f"✔ Changed {changed} word(s) to 'learned' "
              f"(word-ids: {pick}) in word-book '{wb.name}' for user {args.user}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
