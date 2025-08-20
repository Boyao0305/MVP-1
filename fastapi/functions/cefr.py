# functions/cefr_compare_lists.py — async conversion of DB I/O (minimal changes)
from __future__ import annotations

import sys
import os
import json
from collections import Counter
from typing import List, Tuple, Dict

import pandas as pd  # kept from original (unused here)
from fastapi import HTTPException

# Keep original sys.path tweak
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# DB / ORM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

# Project models & DB
from database import SessionLocal, engine, Base  # kept for compatibility
import models

# NLP
import spacy
from cefrpy import CEFRSpaCyAnalyzer, CEFRLevel

# ──────────────────────────────────────────────────────────────────────────────
# NLP setup (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
NLP = spacy.load("en_core_web_sm")

ABBREVIATION_MAPPING = {
    "'m": "am", "'s": "is", "'re": "are", "'ve": "have",
    "'d": "had", "n't": "not", "'ll": "will"
}

ENTITY_TYPES_TO_SKIP_CEFR = {
    "QUANTITY", "MONEY", "LANGUAGE", "LAW",
    "WORK_OF_ART", "PRODUCT", "GPE",
    "ORG", "FAC", "PERSON"
}

ANALYZER = CEFRSpaCyAnalyzer(
    entity_types_to_skip=ENTITY_TYPES_TO_SKIP_CEFR,
    abbreviation_mapping=ABBREVIATION_MAPPING
)

LEVEL_NAMES = ["A1", "A2", "B1", "B2", "C1", "C2"]   # index = level-1


def cefr_unique_stats(text_to_process: str) -> Dict[str, int]:
    doc = NLP(text_to_process)
    level_tokens = ANALYZER.analize_doc(doc)

    seen = set()
    counter = Counter({name: 0 for name in LEVEL_NAMES})

    for word, pos, is_skipped, level, *_ in level_tokens:
        if is_skipped or not level:
            continue
        key = (word.lower(), pos)
        if key in seen:
            continue
        seen.add(key)
        counter[LEVEL_NAMES[round(level) - 1]] += 1

    return dict(counter)


# Duplicated constants retained to match original file
LEVEL_NAMES = ["A1", "A2", "B1", "B2", "C1", "C2"]
THRESHOLDS   = [0.1, 0.1, 0.1, 0.2, 0.2]   # for A1…C1 in order


# ----------------------------------------------------------------------
# Core helpers (unchanged logic)
# ----------------------------------------------------------------------

def _proportions(text_stats: dict, list_stats: dict) -> List[float]:
    """Return p(level) for all six CEFR bands."""
    props: List[float] = []
    for lvl in LEVEL_NAMES:
        denom = text_stats.get(lvl, 0)
        numer = list_stats.get(lvl, 0)
        props.append(0.0 if denom == 0 else numer / denom)
    return props


def _score(props: List[float]) -> int:
    """
    Apply ordered thresholds:
        if A1–C1 all satisfied  -> 6
        if A1–B2 satisfied      -> 5
        if A1–B1 satisfied      -> 4
        if A1–A2 satisfied      -> 3
        if A1      satisfied    -> 2
        else                    -> 1
    """
    satisfied = [
        props[0] < THRESHOLDS[0],  # A1
        props[1] < THRESHOLDS[1],  # A2
        props[2] < THRESHOLDS[2],  # B1
        props[3] < THRESHOLDS[3],  # B2
        props[4] < THRESHOLDS[4],  # C1
    ]

    longest_ok = 0
    for ok in satisfied:
        if ok:
            longest_ok += 1
        else:
            break
    return longest_ok + 1  # maps 0→1, 1→2, …, 5→6


# ----------------------------------------------------------------------
# Public API — now async (DB I/O only)
# ----------------------------------------------------------------------
from sqlalchemy.orm import joinedload

async def compare_lists_to_text(log_id: int, db: AsyncSession) -> Tuple[int, List[float]]:
    """Async version using AsyncSession + SELECT. Logic unchanged.

    Returns (score, proportions).
    """
    result = await db.execute(
        select(models.Learning_log)
        .options(selectinload(models.Learning_log.l_daily_searched_words))
        .where(models.Learning_log.id == log_id)
    )
    log = result.scalars().first()

    if not log:
        raise HTTPException(404, "Log not found")

    # Flatten searched words for this log
    word_list = [w.word for w in log.l_daily_searched_words]
    wordstext = " ".join(word_list)

    # Compute CEFR stats
    textresult = log.artical
    text_stats = cefr_unique_stats(str(textresult))
    list_stats = cefr_unique_stats(wordstext)

    props = _proportions(text_stats, list_stats)
    scr   = _score(props)

    # Persist daily_caiji
    log.daily_caiji = scr
    await db.commit()
    await db.refresh(log)

    # (kept original debug prints)
    print(wordstext)
    print(scr, props)
    return scr, props

# Example manual test (kept as comment)
# async with SessionLocal() as db:
#     await compare_lists_to_text(1, db)
