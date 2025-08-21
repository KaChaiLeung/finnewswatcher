from __future__ import annotations

import re
from typing import Dict, List, Tuple, TypedDict, Optional

from finnewswatcher.classifier.rules import Ruleset
from finnewswatcher.models import NormalizedItem, EventClass


Pattern = re.Pattern[str]
GLOBAL_NEG_KEY = "__GLOBAL_NEGATIVE__"


class ScoreInfo(TypedDict):
    class_name: EventClass
    headline_hits: int
    snippet_hits: int
    total_hits: int
    negative_hit: bool
    disqualified: bool
    reason: str


def _compile_keyword(kw: str) -> Pattern:
    return re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(kw)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _compile_many(keywords: List[str]) -> List[Pattern]:
    return [_compile_keyword(k) for k in keywords if k]


def build_regex_cache(rules: Ruleset) -> Dict[str, Dict[str, List[Pattern]]]:
    """
    Cache shape:
        {
            "<EventClass>": {
                "headline": [Pattern, ...],
                "snippet":  [Pattern, ...],
                "negative": [Pattern, ...],
            },
            "__GLOBAL_NEGATIVE__": {
                "negative": [Pattern, ...]
            }
        }
    """
    cache: Dict[str, Dict[str, List[Pattern]]] = {}

    for class_name, class_rules in rules.classes.items():
        cache[class_name] = {
            "headline": _compile_many(class_rules.headline_keywords),
            "snippet": _compile_many(class_rules.snippet_keywords),
            "negative": _compile_many(class_rules.negative_keywords),
        }

    cache[GLOBAL_NEG_KEY] = {"negative": _compile_many(rules.negative_keywords_global)}
    return cache


def _count_distinct_hits(patterns: List[Pattern], text: str) -> int:
    if not text or not patterns:
        return 0
    return sum(1 for p in patterns if p.search(text))


def score_item_for_class(
    item: NormalizedItem,
    class_name: EventClass,
    rules: Ruleset,
    regex_cache: Dict[str, Dict[str, List[Pattern]]],
) -> Tuple[int, ScoreInfo]:
    """
    Returns (score, info) for a single class.
    - Applies class-specific and global negatives (if disqualify flag is set).
    - Enforces min_total_hits and min_headline_hits.
    - Weights headline/snippet *distinct* hit counts.
    """
    text_headline = item.headline or ""
    text_snippet = item.body_snippet or ""

    cls_patterns = regex_cache.get(class_name, {})
    headline_pats = cls_patterns.get("headline", [])
    snippet_pats = cls_patterns.get("snippet", [])
    class_neg_pats = cls_patterns.get("negative", [])
    global_neg_pats = regex_cache.get(GLOBAL_NEG_KEY, {}).get("negative", [])

    neg_hit = any(
        p.search(text_headline) or p.search(text_snippet)
        for p in (class_neg_pats + global_neg_pats)
    )
    if rules.disqualify_if_negative and neg_hit:
        return 0, ScoreInfo(
            class_name=class_name,
            headline_hits=0,
            snippet_hits=0,
            total_hits=0,
            negative_hit=True,
            disqualified=True,
            reason="negative_keyword",
        )

    h_hits = _count_distinct_hits(headline_pats, text_headline)
    s_hits = _count_distinct_hits(snippet_pats, text_snippet)
    total = h_hits + s_hits

    if total < rules.min_total_hits:
        return 0, ScoreInfo(
            class_name=class_name,
            headline_hits=h_hits,
            snippet_hits=s_hits,
            total_hits=total,
            negative_hit=neg_hit,
            disqualified=True,
            reason="min_total_hits",
        )

    if h_hits < rules.min_headline_hits:
        return 0, ScoreInfo(
            class_name=class_name,
            headline_hits=h_hits,
            snippet_hits=s_hits,
            total_hits=total,
            negative_hit=neg_hit,
            disqualified=True,
            reason="min_headline_hits",
        )

    score = rules.headline_weight * h_hits + rules.snippet_weight * s_hits
    return score, ScoreInfo(
        class_name=class_name,
        headline_hits=h_hits,
        snippet_hits=s_hits,
        total_hits=total,
        negative_hit=neg_hit,
        disqualified=False,
        reason="",
    )


def classify_item(
    item: NormalizedItem,
    rules: Ruleset,
    regex_cache: Dict[str, Dict[str, List[Pattern]]],
) -> Tuple[Optional[EventClass], int, List[str]]:
    """
    Classify an item across all classes in the ruleset.

    Tie-break order:
      1) Higher score
      2) Higher headline_hits
      3) Higher total_hits
      4) Earlier in rules.priority_order
    """
    results: List[Tuple[EventClass, int, ScoreInfo]] = []
    for class_name in rules.classes.keys():
        score, info = score_item_for_class(item, class_name, rules, regex_cache)
        results.append((class_name, score, info))

    # Debug lines per class
    debug: List[str] = []
    for cls, sc, info in results:
        line = (
            f"{cls}: score={sc} "
            f"hh={info['headline_hits']} sh={info['snippet_hits']} tot={info['total_hits']}"
        )
        if info["disqualified"]:
            line += f" DISQ({info['reason']})"
        debug.append(line)

    # Eligible only
    eligibles = [(cls, sc, info) for cls, sc, info in results if not info["disqualified"]]
    if not eligibles:
        return None, 0, debug

    prio_index = {c: i for i, c in enumerate(rules.priority_order)}

    winner_cls, winner_score, _ = max(
        eligibles,
        key=lambda t: (
            t[1],  # score
            t[2]["headline_hits"],
            t[2]["total_hits"],
            -prio_index.get(t[0], 10_000),
        ),
    )

    return winner_cls, winner_score, debug