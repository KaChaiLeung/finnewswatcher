from __future__ import annotations

from typing import Dict, List
import re

from finnewswatcher.config import WatchlistEntry
from finnewswatcher.models import NormalizedItem


def build_alias_index(watchlist: List[WatchlistEntry]) -> dict[str, str]:
    index: Dict[str, str] = {}

    for entry in watchlist:
        candidates = {entry.name, entry.ticker, *entry.aliases}
        seen = set()

        for alias in candidates:
            a = " ".join(str(alias).split()).strip()
            if a == "":
                continue
            key = a.casefold()
            if key in seen:
                continue
            seen.add(key)
            if len(a) < 3 and a.upper() != entry.ticker:
                continue
            index.setdefault(key, entry.ticker)
    
    return index


def attach_tickers(items: List[NormalizedItem], alias_index: Dict[str, str]) -> None:
    # 1) Precompile patterns: keep (alias, regex) pairs
    aliases = sorted(alias_index.keys(), key=len, reverse=True)
    compiled_patterns = []
    for alias in aliases:
        escaped = re.escape(alias)
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        compiled_patterns.append((alias, re.compile(pattern, re.IGNORECASE)))

    # 2) Scan each item and populate tickers
    for item in items:
        # normalize whitespace a bit
        text = " ".join(f"{item.headline} {item.body_snippet}".split())
        found = set()

        for alias, regex in compiled_patterns:
            if regex.search(text):
                ticker = alias_index[alias]  # already a string, e.g., "NVDA"
                found.add(ticker)

        item.tickers = sorted(found)