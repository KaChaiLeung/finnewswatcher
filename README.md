# FinNewsWatcher

A watchlist-based financial news monitor that fetches RSS/Atom feeds, normalizes entries, tags them to your tickers via alias matching, and prints a UTC-sorted digest. Config is YAML, validated with Pydantic. Designed to cut your daily “scan the feeds” from ~15 → ~5 minutes.

---

## What’s included (MVP)

- ✅ **Normalized item model** (`NormalizedItem`) with **UTC** timestamp validator
- ✅ **Config loading & validation** (`thresholds.yaml`, `sources.yaml`, `watchlist.yaml`)
- ✅ **RSS/Atom fetcher** (`fetchers/rss.py`) with defensive parsing & canonical IDs
- ✅ **Alias matching & ticker tagging** (from `watchlist.yaml`)
- ✅ **CLI** to pull, sort, and print digest (+ optional snippets)
- ✅ **Quality gates**: Ruff, Mypy (with types-PyYAML), Pytest (config & watchlist tests)
- ⏳ **Classifier**: map to 8 event classes
- ⏳ **Scoring**: base weights + bonuses → `materiality_score`
- ⏳ **Delivery**: Slack digest at **08:30 Europe/London** + instant alerts

---

## Architecture

1. **Fetch** → RSS/HTTP → `feedparser` → `NormalizedItem`
2. **Tag** → regex alias match (headline + snippet) → `item.tickers`
3. **(Next) Classify** → rules → one of 8 event classes
4. **(Next) Score** → base weight + bonuses → `materiality_score`
5. **(Next) Summarize/Judge** → compact summary + sanity checks
6. **(Next) Deliver** → Slack morning digest + alerts

---

## Quickstart

```bash
# Install deps & project
poetry install

# Lint, type-check, test
poetry run ruff check .
poetry run mypy finnewswatcher
poetry run pytest -q
```
