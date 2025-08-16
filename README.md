# FinNewsWatcher

A watchlist-based financial news monitor that classifies events, scores materiality, and posts a concise **08:30 Europe/London** Slack digest. High-impact items can trigger instant alerts. The pipeline is config-driven (YAML) and validated with Pydantic.

> **Goal:** Cut daily “scan the feeds” time from ~15 → ~5 minutes while missing fewer important updates.

---

## Features (MVP)

- **Normalized item model** (`NormalizedItem`) with UTC timestamps
- **Config-driven scoring** (base weights + bonuses in `configs/thresholds.yaml`)
- **Validation:** strict Pydantic model for thresholds + tests
- **Fetch (next):** RSS/RNS → `NormalizedItem`
- **Classify (next):** rules → 8 event classes
- **Score (next):** materiality = base weight + bonuses
- **Deliver (next):** Slack digest + instant alerts

---

## Architecture

1. **Fetch** → RSS/HTTP → `NormalizedItem`
2. **Classify** → rules → one of 8 event classes
3. **Score** → base weight + bonuses → `materiality_score`
4. **Summarize** → “What / Why / Next” (≤4 lines)
5. **Judge** → groundedness / clarity / actionability
6. **Deliver** → Slack morning digest + alerts

---

## Project Status

- ✅ `finnewswatcher/models.py` (data model + UTC validator)
- ✅ `finnewswatcher/config.py` (`_project_root`, `load_yaml`, `Thresholds`, validation)
- ✅ Tests for config (`tests/test_config.py`)
- ⏳ Fetcher (`fetchers/rss.py`) & CLI
- ⏳ Classifier, scoring, Slack delivery

---

## Quickstart

```bash
# Install
poetry install

# Lint, type-check, test
poetry run ruff check .
poetry run mypy finnewswatcher
poetry run pytest -q

# (Soon) Run the CLI
poetry run python -m finnewswatcher.cli
```
