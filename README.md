FinNewsWatcher

A tiny CLI that fetches finance news, tags tickers, classifies headlines by event type, scores materiality, and (optionally) fires Slack alerts.
Built with Python 3.13, Poetry, Pydantic v2, Ruff, and Mypy.

⸻

Features
• Pulls recent items from configured feeds (e.g., BBC Business, MarketWatch).
• Normalizes items with source type/time/tickers.
• Rule-based classifier:
• Event classes: M&A, Guidance, Earnings, Legal-Reg, Financing, Exec, Product-Customer, Macro.
• Weighted headline vs snippet hits, eligibility thresholds, negative keywords.
• Deterministic tie-breaks using score, hits, and priority_order.
• Ticker tagging via a simple alias index from configs/watchlist.yaml.
• Slack alerts with filtering (min score, require numbers, only watchlist tickers) + rate limiting and dry-run.
• Clean CLI output with optional verbose/debug views.
• Tests (pytest), lint (ruff), types (mypy).

⸻

Requirements
• Python 3.13
• Poetry
• (Optional) Slack Incoming Webhook

⸻

Quickstart

# 1) Install deps

poetry install

# 2) (Recommended) Create .env with your Slack webhook

cp .env.example .env

# then edit .env

# 3) Run tests & quality checks

poetry run pytest -q
poetry run ruff check --fix .
poetry run mypy finnewswatcher

# 4) Run the CLI (example)

poetry run python -m finnewswatcher.cli --types wire --max-items 20 --verbose
