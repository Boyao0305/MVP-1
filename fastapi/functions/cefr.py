

from __future__ import annotations
from typing import List, Tuple

from function_1 import cefr_unique_stats   # <- keep your original import

import json


from __future__ import annotations
import json
from collections import Counter
from typing import Dict

import spacy
from cefrpy import CEFRSpaCyAnalyzer, CEFRLevel

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




LEVEL_NAMES = ["A1", "A2", "B1", "B2", "C1", "C2"]
THRESHOLDS   = [0.1, 0.1, 0.1, 0.2, 0.2]   # for A1…C1 in order


# ----------------------------------------------------------------------
# Core helper
# ----------------------------------------------------------------------
def _proportions(text_stats: dict, list_stats: dict) -> List[float]:
    """Return p(level) for all six CEFR bands."""
    props: List[float] = []
    for lvl in LEVEL_NAMES:
        denom = text_stats.get(lvl, 0)
        # print(denom)
        numer = list_stats.get(lvl, 0)
        # print(numer)
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

    # find longest prefix of True values
    longest_ok = 0
    for ok in satisfied:
        if ok:
            longest_ok += 1
        else:
            break
    return longest_ok + 1  # maps 0→1, 1→2, …, 5→6


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
with open("data.json", "r", encoding="utf-8") as f:
    python_dict = json.load(f)
text = python_dict["text"]
words = python_dict["words"]
def compare_lists_to_text(text: str, words: str) -> Tuple[int, List[float]]:

    text_stats = cefr_unique_stats(text)

    list_stats = cefr_unique_stats(" ".join(words))


    props = _proportions(text_stats, list_stats)
    scr   = _score(props)
    return scr
print(compare_lists_to_text(text, words))
