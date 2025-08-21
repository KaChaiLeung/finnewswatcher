from __future__ import annotations

import re

from finnewswatcher.models import NormalizedItem

_NUM_RE = re.compile(
    r"(\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def detect_has_numbers(item: NormalizedItem) -> None:
    text = f"{item.headline} {item.body_snippet or ''}"
    item.has_numbers = bool(_NUM_RE.search(text))