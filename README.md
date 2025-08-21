FinNewsWatcher

A tiny CLI that fetches finance news, tags tickers, classifies headlines by event type, scores materiality, and (optionally) fires Slack alerts.
Built with Python 3.13, Poetry, Pydantic v2, Ruff, and Mypy.

⸻

✨ Features
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

🧰 Requirements
• Python 3.13
• Poetry
• (Optional) Slack Incoming Webhook

⸻

🚀 Quickstart

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

⸻

🗂️ Project Layout (high level)

finnewswatcher/
classifier/
core.py # scoring, classification, regex cache
rules.py # Ruleset & ClassRules (Pydantic)
fetchers/
rss.py # feed fetching/normalization
config.py # YAML/.env loaders
match.py # watchlist alias index & ticker tagging
cli.py # the CLI entry point
configs/
sources.yaml
watchlist.yaml
classifier.yaml
.env (optional) # FNW*SLACK*\* variables

⸻

⚙️ Configuration

1. .env (optional, for Slack)

# .env

FNW_SLACK_WEBHOOK=https://hooks.slack.com/services/XXX/YYY/ZZZ

If you use Poetry, environment variables loaded from .env are visible to the subprocess if your app calls dotenv.load_dotenv() (the CLI does this).
If the CLI still “doesn’t see” variables, ensure .env sits at the project root and the key is spelled exactly FNW_SLACK_WEBHOOK.

2. configs/sources.yaml

Define feeds & their type:

# Example

- name: BBC Business
  url: https://feeds.bbci.co.uk/news/business/rss.xml
  type: wire
  enabled: true
  fetch_limit: 20

- name: MarketWatch Top Stories
  url: https://www.marketwatch.com/feeds/topstories
  type: wire
  enabled: true
  fetch_limit: 20

If a feed returns text/html (not real RSS), it’s skipped. Replace with a proper RSS URL.

3. configs/watchlist.yaml

Ticker universe + aliases for matching:

tickers:

- symbol: INTC
  aliases: ["intel", "intel corp", "intel corporation"]
- symbol: WMT
  aliases: ["walmart", "wal-mart"]
- symbol: LOW
  aliases: ["lowe’s", "lowes", "lowe"]

4. configs/classifier.yaml

Rules that drive classification (example starter):

headline_weight: 2
snippet_weight: 1
min_total_hits: 1
min_headline_hits: 0
disqualify_if_negative: true

negative_keywords_global:

- "rumor"
- "speculation"

priority_order:

- "M&A"
- "Guidance"
- "Earnings"
- "Legal-Reg"
- "Financing"
- "Exec"
- "Product-Customer"
- "Macro"

classes:
M&A:
headline_keywords: ["acquire", "acquisition", "merger", "stake", "buyout", "takeover", "deal"]
snippet_keywords: ["acquire", "acquisition", "merger", "stake", "buyout", "takeover", "deal"]
negative_keywords: []
Guidance:
headline_keywords: ["guidance", "outlook", "forecast", "warns", "warning", "raises", "lowers"]
snippet_keywords: ["guidance", "outlook", "forecast", "warns", "warning", "raises", "lowers"]
negative_keywords: []
Earnings:
headline_keywords: ["earnings", "eps", "revenue", "profit", "beat", "miss"]
snippet_keywords: ["earnings", "eps", "revenue", "profit", "beat", "miss"]
negative_keywords: []
Legal-Reg:
headline_keywords: ["lawsuit", "fine", "ban", "antitrust", "investigation", "regulator", "probe", "settlement"]
snippet_keywords: ["lawsuit", "fine", "ban", "antitrust", "investigation", "regulator", "probe", "settlement"]
negative_keywords: []
Financing:
headline_keywords: ["offering", "secondary", "debt", "bond", "loan", "credit facility"]
snippet_keywords: ["offering", "secondary", "debt", "bond", "loan", "credit facility"]
negative_keywords: []
Exec:
headline_keywords: ["ceo", "cfo", "coo", "chair", "executive", "resigns", "steps down", "appoints", "hires"]
snippet_keywords: ["ceo", "cfo", "coo", "chair", "executive", "resigns", "steps down", "appoints", "hires"]
negative_keywords: []
Product-Customer:
headline_keywords: ["launch", "product", "contract", "customer", "order", "deal", "wins"]
snippet_keywords: ["launch", "product", "contract", "customer", "order", "deal", "wins"]
negative_keywords: []
Macro:
headline_keywords: ["inflation", "cpi", "ppi", "fed", "interest rate", "tariff", "economy", "unemployment"]
snippet_keywords: ["inflation", "cpi", "ppi", "fed", "interest rate", "tariff", "economy", "unemployment"]
negative_keywords: []

⸻

🖥️ CLI Usage

poetry run python -m finnewswatcher.cli [options]

Common options
• --types Comma list of source types: rns,press,wire,filing (default rns)
• --sources Limit number of sources loaded from sources.yaml (0 = all)
• --per-source Max entries fetched per source (0 = use each source’s fetch_limit)
• --max-items Cap final printed items (after sorting; default 20)
• --verbose Print URL and snippet lines
• --debug-classify Dump per-class hits & disqualification reasons
• --sort {time,score} Sort by published_at (default) or classifier score
• --only-eligible Only include items that got a class assigned

Slack options
• --slack-min-score N Only send alerts with score ≥ N
• --slack-only-watchlist Only if item has a tagged ticker from your watchlist
• --slack-require-numbers Only if snippet/headline contains numbers (e.g., “%”, “$”, digits)
• --slack-rate-limit SECONDS Sleep between posts to avoid flooding (default 0)
• --slack-dry-run Build messages but don’t POST to Slack (prints a summary)

Slack requires FNW_SLACK_WEBHOOK (via .env or env).
A 404 usually means the webhook URL is invalid or revoked.

Examples

# Pull 2 wire sources, show 20 items, verbose & debug classification

poetry run python -m finnewswatcher.cli \
 --types wire --sources 2 --per-source 15 --max-items 20 \
 --verbose --debug-classify

# Score-sorted and only eligible

poetry run python -m finnewswatcher.cli \
 --types wire --only-eligible --sort score

# Send Slack alerts for scored items (dry-run first!)

poetry run python -m finnewswatcher.cli \
 --types wire --only-eligible --sort score \
 --slack-min-score 2 --slack-only-watchlist --slack-require-numbers \
 --slack-rate-limit 1.0 --slack-dry-run

Sample output (truncated):

FinNewsWatcher CLI — 2025-08-21T00:24:20+00:00
Sources: 2 | Types: wire | Items: 30 | Sort: score | Only eligible
2025-08-20T22:11:00+00:00 | [wire] Lowe’s ... (MarketWatch Top Stories) [Earnings, 4]
...

⸻

🧪 Tests & Quality

# Run tests

poetry run pytest -q

# Lint (fix) & type check

poetry run ruff check --fix .
poetry run mypy finnewswatcher

⸻

🧠 Classifier Details
• Word-boundary regex for each keyword: (?<![A-Za-z0-9]){term}(?![A-Za-z0-9])
• Case-insensitive.
• Headline vs snippet weights: headline_weight, snippet_weight.
• Disqualify in presence of:
• negative_keywords_global
• class-specific negative_keywords
(only if disqualify_if_negative: true)
• Eligibility thresholds:
• min_total_hits
• min_headline_hits
• Tie-break order: 1. Higher score 2. Higher headline_hits 3. Higher total_hits 4. Earlier in priority_order

⸻

🔌 How It Works (pipeline)

sources.yaml → pull_feed() → NormalizedItem
│
├─ watchlist.yaml → build_alias_index() → attach_tickers()
│
└─ classifier.yaml → Ruleset → build_regex_cache()
└→ classify_item() → event_class + score
└→ (optional) Slack filter → POST

⸻

🐛 Troubleshooting
• Webhook 404
Your Slack webhook is invalid/expired or points to the wrong workspace. Regenerate from Slack and update .env.
• CLI can’t see FNW_SLACK_WEBHOOK
Ensure .env is at the project root and the CLI calls load_dotenv().
You can verify quickly:

poetry run python - <<'PY'
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv(Path.cwd() / ".env")
print("Webhook present?", bool(os.getenv("FNW_SLACK_WEBHOOK")))
PY

    •	Feed returns HTML / Not XML

Replace the URL with a genuine RSS endpoint. Example errors:
• Not XML ... text/html; charset=utf-8 — skipping
• Client error '404 Not Found' ...
• zsh: unknown file attribute: i
That’s zsh interpreting #/redirection oddly when pasting multiple lines. Run one command per line or put commands in a shell script.

⸻

🛠️ Development tips
• Add/adjust keywords in configs/classifier.yaml, then re-run the CLI with --debug-classify to see hit details.
• Use --sort score + --only-eligible to focus on the most material items.
• Start with --slack-dry-run before sending to your channel.
