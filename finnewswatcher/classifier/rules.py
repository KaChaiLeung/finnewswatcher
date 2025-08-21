from __future__ import annotations

from collections.abc import Iterable
from typing import get_args, Dict
from pydantic import BaseModel, Field, field_validator, model_validator

from finnewswatcher.models import EventClass


# Canonical list of classes derived from the EventClass Literal
EVENT_CLASSES: list[EventClass] = list(get_args(EventClass))
_EVENT_MAP_LOWER_TO_CANON: Dict[str, EventClass] = {
    c.lower(): c for c in EVENT_CLASSES
}


class ClassRules(BaseModel):
    """Per-class keyword rules."""
    headline_keywords: list[str] = Field(default_factory=list)
    snippet_keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)

    @field_validator("headline_keywords", "snippet_keywords", "negative_keywords", mode="before")
    def normalize_keywords(cls, v) -> list[str]:
        # Treat None as empty
        if v is None:
            return []

        # Accept string or any iterable of strings
        if isinstance(v, str):
            raw = [v]
        elif isinstance(v, Iterable):
            raw = list(v)
        else:
            return []

        cleaned: list[str] = []
        seen: set[str] = set()

        for item in raw:
            if not isinstance(item, str):
                continue
            kw = item.strip().lower()
            if not kw:
                continue
            # Optional: drop single-letter alpha tokens (too noisy)
            if len(kw) == 1 and kw.isalpha():
                continue
            if kw not in seen:
                seen.add(kw)
                cleaned.append(kw)

        return cleaned


class Ruleset(BaseModel):
    """Global classifier configuration and per-class keyword rules."""
    # Weights and thresholds
    headline_weight: int = 2
    snippet_weight: int = 1
    min_total_hits: int = 1
    min_headline_hits: int = 0

    # Negative keyword logic
    disqualify_if_negative: bool = True
    negative_keywords_global: list[str] = Field(default_factory=list)

    # Priority order for tie-breaks / scanning
    priority_order: list[EventClass] = Field(default_factory=list)

    # Per-class rules (any missing classes will be auto-filled with defaults)
    classes: dict[EventClass, ClassRules] = Field(default_factory=dict)

    # ---- Validators ----

    @field_validator("headline_weight", "snippet_weight", mode="after")
    def _weights_nonnegative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("headline_weight and snippet_weight must be >= 0")
        return v

    @field_validator("min_total_hits", "min_headline_hits", mode="after")
    def _hits_nonnegative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("min_total_hits and min_headline_hits must be >= 0")
        return v

    @field_validator("negative_keywords_global", mode="before")
    def _normalize_neg_global(cls, v) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            raw = [v]
        elif isinstance(v, Iterable):
            raw = list(v)
        else:
            return []

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, str):
                continue
            kw = item.strip().lower()
            if not kw:
                continue
            if len(kw) == 1 and kw.isalpha():
                continue
            if kw not in seen:
                seen.add(kw)
                cleaned.append(kw)
        return cleaned

    @field_validator("priority_order", mode="before")
    def _normalize_priority(cls, v) -> list[EventClass]:
        """
        Accepts None / str / iterable of str; returns a full permutation of EVENT_CLASSES
        in canonical casing. Unknown values raise a ValueError.
        """
        if v is None:
            return EVENT_CLASSES.copy()

        if isinstance(v, str):
            raw = [v]
        elif isinstance(v, Iterable):
            raw = list(v)
        else:
            return EVENT_CLASSES.copy()

        out: list[EventClass] = []
        seen: set[EventClass] = set()
        unknown: list[str] = []

        for item in raw:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            canon = _EVENT_MAP_LOWER_TO_CANON.get(name.lower())
            if canon is None:
                unknown.append(item)
                continue
            if canon not in seen:
                seen.add(canon)
                out.append(canon)

        if unknown:
            raise ValueError(f"Unknown event classes in priority_order: {unknown}")

        # Fill in any classes not provided by the user (keep canonical order)
        for c in EVENT_CLASSES:
            if c not in seen:
                out.append(c)

        return out

    @field_validator("classes", mode="before")
    def _normalize_classes_dict(cls, v) -> dict[EventClass, ClassRules]:
        """
        Accepts dict with keys as str/EventClass and values as dict/ClassRules.
        Unknown keys raise a ValueError. Returns a dict keyed by canonical EventClass.
        """
        if v is None:
            return {}

        if not isinstance(v, dict):
            raise TypeError("classes must be a dict mapping EventClass -> ClassRules")

        out: dict[EventClass, ClassRules] = {}
        unknown: list[str] = []

        for k, rules in v.items():
            # Map key to canonical EventClass
            if isinstance(k, str):
                canon = _EVENT_MAP_LOWER_TO_CANON.get(k.strip().lower())
            else:
                # If someone passed the Literal value directly, coerce to str for lookup
                canon = _EVENT_MAP_LOWER_TO_CANON.get(str(k).strip().lower())

            if canon is None:
                unknown.append(str(k))
                continue

            # Normalize value to ClassRules
            if isinstance(rules, ClassRules):
                out[canon] = rules
            elif isinstance(rules, dict):
                out[canon] = ClassRules(**rules)
            else:
                raise TypeError(f"classes[{canon!r}] must be a ClassRules or dict")

        if unknown:
            raise ValueError(f"Unknown class keys in classes: {unknown}")

        return out

    @model_validator(mode="after")
    def _fill_missing_classes(self) -> Ruleset:
        """Ensure every EventClass has a ClassRules entry."""
        if not self.priority_order:
            self.priority_order = EVENT_CLASSES.copy()

        # Fill missing per-class configs with defaults
        for c in EVENT_CLASSES:
            if c not in self.classes:
                self.classes[c] = ClassRules()

        return self

    # ---- Convenience helpers ----

    def classes_in_priority(self) -> list[tuple[EventClass, ClassRules]]:
        """Return list of (EventClass, ClassRules) following the priority order."""
        return [(c, self.classes[c]) for c in self.priority_order]