# functions/word_test.py — async version using AsyncSession
from __future__ import annotations

from typing import Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

import models


async def get_word_and_distractor_definitions(db: AsyncSession, word_id: int) -> Dict[str, object]:
    """Return target word + definition and 3 random distractor definitions.
    Behavior is unchanged; only converted to async SQLAlchemy patterns.
    """
    # 1) Find the target word
    result = await db.execute(select(models.Word).where(models.Word.id == word_id))
    word_entry = result.scalars().first()
    if not word_entry:
        raise ValueError("Target word not found in database")

    target_definition = word_entry.definition

    # 2) Pick 3 random *other* definitions (DB-dialect aware RAND)
    try:
        # AsyncSession.bind is an AsyncEngine; pull its dialect name if available
        dialect = getattr(db.bind, "dialect", None)
        dialect_name = getattr(dialect, "name", None)
    except Exception:
        dialect_name = None

    # MySQL uses RAND(); SQLite/PostgreSQL use RANDOM()
    rand_expr = func.rand() if (dialect_name and "mysql" in dialect_name) else func.random()

    rows = await db.execute(
        select(models.Word.definition)
        .where(models.Word.id != word_id)
        .order_by(rand_expr)
        .limit(3)
    )
    distractor_definitions = [r[0] for r in rows.all()]  # (definition,) → definition

    return {
        "word": word_entry.word,
        "definition": target_definition,
        "distractors": distractor_definitions,
    }
