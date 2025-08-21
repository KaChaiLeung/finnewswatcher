# tests/test_classifier_core.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pytest

from finnewswatcher.models import NormalizedItem, EventClass
from finnewswatcher.classifier.rules import Ruleset, ClassRules
from finnewswatcher.classifier.core import build_regex_cache, classify_item


def _mk_item(headline: str, snippet: str = "") -> NormalizedItem:
    return NormalizedItem(
        id="test",
        published_at=datetime.now(timezone.utc),
        source_name="TestWire",
        source_type="wire",
        url="https://example.com/item",
        headline=headline,
        body_snippet=snippet,
    )


def _base_ruleset(
    *,
    headline_weight: int = 2,
    snippet_weight: int = 1,
    min_total_hits: int = 1,
    min_headline_hits: int = 0,
    disqualify_if_negative: bool = True,
    negative_global: list[str] | None = None,
    priority: list[EventClass] | None = None,
) -> Ruleset:
    # Minimal but expressive rules for tests
    classes: Dict[EventClass, ClassRules] = {
        "Earnings": ClassRules(
            headline_keywords=["earnings", "eps", "profit"],
            snippet_keywords=["revenue", "sales"],
            negative_keywords=[],
        ),
        "Guidance": ClassRules(
            headline_keywords=["guidance", "outlook"],
            snippet_keywords=["forecast", "expects", "sees"],
            negative_keywords=[],
        ),
        "Exec": ClassRules(
            headline_keywords=["ceo", "cfo", "resigns", "steps down"],
            snippet_keywords=["leadership", "management"],
            negative_keywords=[],
        ),
        "Macro": ClassRules(
            headline_keywords=["inflation", "rates", "tariffs"],
            snippet_keywords=["macro", "economy"],
            negative_keywords=[],
        ),
    }

    return Ruleset(
        headline_weight=headline_weight,
        snippet_weight=snippet_weight,
        min_total_hits=min_total_hits,
        min_headline_hits=min_headline_hits,
        disqualify_if_negative=disqualify_if_negative,
        negative_keywords_global=(negative_global or []),
        priority_order=priority
        or ["M&A", "Guidance", "Earnings", "Legal-Reg", "Financing", "Exec", "Product-Customer", "Macro"],
        classes=classes,
    )


def test_headline_weight_beats_snippet():
    rules = _base_ruleset()
    cache = build_regex_cache(rules)

    # Headline hits Guidance; snippet hits Earnings
    item = _mk_item("Company issues guidance for 2025", "Strong revenue growth expected")

    best, score, _debug = classify_item(item, rules, cache)

    # Guidance headline match (2 pts) vs Earnings snippet match (1 pt) → Guidance wins
    assert best == "Guidance"
    assert score == 2


def test_global_negative_disqualifies_all():
    rules = _base_ruleset(negative_global=["rumor", "speculation"])
    cache = build_regex_cache(rules)

    item = _mk_item("Company announces earnings", "Market rumors suggest this is speculation")

    best, score, _debug = classify_item(item, rules, cache)

    # Any class would be disqualified due to global negative terms
    assert best is None
    assert score == 0


def test_min_total_hits_threshold_blocks():
    # Require at least 2 total hits across headline+snippet
    rules = _base_ruleset(min_total_hits=2)
    cache = build_regex_cache(rules)

    # Only one keyword present ("earnings") → should be ineligible
    item = _mk_item("Earnings preview", "Nothing else to see")

    best, score, _debug = classify_item(item, rules, cache)

    assert best is None
    assert score == 0


def test_tiebreakers_priority_order_applies():
    # Make priority favor Earnings over Guidance to force the last tie-breaker
    rules = _base_ruleset(
        priority=["Earnings", "Guidance", "M&A", "Legal-Reg", "Financing", "Exec", "Product-Customer", "Macro"]
    )
    cache = build_regex_cache(rules)

    # One snippet hit for Earnings ("revenue") and one for Guidance ("forecast")
    # No headline hits → score equal (1 vs 1), headline_hits equal (0), total_hits equal (1)
    # Priority order decides: Earnings wins
    item = _mk_item("Company update", "Revenue trend and forecast discussed")

    best, score, _debug = classify_item(item, rules, cache)

    assert best == "Earnings"
    assert score == 1


def test_word_boundaries_do_not_match_inside_longer_words():
    rules = _base_ruleset()
    cache = build_regex_cache(rules)

    # "earnings" must not match "earningslike" (alpha character immediately after)
    item = _mk_item("Company posts earningslike metrics", "")

    best, score, _debug = classify_item(item, rules, cache)

    assert best is None
    assert score == 0


def test_word_boundaries_allow_hyphen_and_punctuation():
    rules = _base_ruleset()
    cache = build_regex_cache(rules)

    # Hyphen before "earnings" is allowed (non-alnum boundary)
    item1 = _mk_item("Pre-earnings call scheduled", "")
    best1, score1, _ = classify_item(item1, rules, cache)
    assert best1 == "Earnings"
    assert score1 >= 1

    # Trailing punctuation after "earnings" is allowed (non-alnum boundary)
    item2 = _mk_item("Blowout earnings!", "")
    best2, score2, _ = classify_item(item2, rules, cache)
    assert best2 == "Earnings"
    assert score2 >= 1