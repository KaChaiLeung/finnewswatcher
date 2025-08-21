import argparse
from datetime import datetime, timezone
import sys
from typing import get_args
import os
import time
from dotenv import load_dotenv
from pathlib import Path

from finnewswatcher.config import load_sources, load_watchlist, load_classifier_ruleset
from finnewswatcher.fetchers.rss import pull_feed
from finnewswatcher.models import SourceType
from finnewswatcher.match import build_alias_index, attach_tickers
from finnewswatcher.classifier.core import build_regex_cache, classify_item
from finnewswatcher.enrich import detect_has_numbers
from finnewswatcher.notify.slack import build_blocks_for_item, post_to_slack, should_alert
from finnewswatcher.state import was_sent, mark_sent


ALLOWED_TYPES = {t.lower() for t in get_args(SourceType)}

_dotenv_loaded = False
for p in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
    if p.exists():
        load_dotenv(p, override=False)  # always pass an explicit path on Py 3.13
        _dotenv_loaded = True
        break

if not os.getenv("FNW_SLACK_WEBHOOK"):
    print("[slack] no FNW_SLACK_WEBHOOK set; skipping Slack posts")


def parse_args():
    parser = argparse.ArgumentParser(prog="finnewswatcher",
                                     description="Fetches recent items from configured sources (rns, press, wire, filing), normalizes them to FinNewsWatcher items, and prints a UTC-sorted headline list. Use --types to filter source types, --sources to limit how many feeds to pull, --per-source to cap entries per feed, --max-items for output size, and --verbose to include URLs/snippets")
    parser.add_argument("--types", type=str, default="rns", help="Comma-separated list of source types to pull: rns,press,wire,filing")
    parser.add_argument("--max-items", type=int, default=20, help="Max number of items to print overall (after sorting)")
    parser.add_argument("--per-source", type=int, default=0, help="Number of entries to read per source")
    parser.add_argument("--sources", type=int, default=0, help="Number of sources to pull (0 = all)")
    parser.add_argument("--verbose", action="store_true", help="When set, print URL and snippet lines")
    parser.add_argument("--debug-classify", action="store_true", help="Print per-class scoring/eligibility details for each item")
    parser.add_argument("--sort", choices=("time", "score"), default="time", help="Sort output by 'time' or 'score'")
    parser.add_argument("--only-eligible", action="store_true", help="Only show items that classifier assigned an event class")
    parser.add_argument("--slack-webhook", type=str, default=None, help="Slack Incoming Webhook URL (or set FNW_SLACK_WEBHOOK)")
    parser.add_argument("--slack-min-score", type=int, default=2, help="Minimum classifier score to alert")
    parser.add_argument("--slack-classes", type=str, default="", help="Comma list of classes to alert (empty = any)")
    parser.add_argument("--slack-only-watchlist", action="store_true", help="Only alert items that match watchlist")
    parser.add_argument("--slack-require-numbers", action="store_true", help="Only alert items containing numeric signals")
    parser.add_argument("--slack-dry-run", action="store_true", help="Print Slack payloads instead of posting")
    parser.add_argument("--slack-rate-limit", type=float, default=1.0, help="Seconds to sleep between Slack posts")

    ns = parser.parse_args()

    types = [s for s in (t.strip().lower() for t in ns.types.split(",")) if s]
    types = list(dict.fromkeys(types))
    invalid = [t for t in types if t not in ALLOWED_TYPES]

    if invalid:
        parser.error(f"Invalid --types {invalid}; valid: {', '.join(sorted(ALLOWED_TYPES))}")

    if not types:
        types = ["rns"]
    
    ns.types = tuple(types)

    if ns.max_items < 1:
        parser.error(f"max_items should be >= 1; currently {ns.max_items}")
    
    if ns.per_source < 0:
        parser.error(f"per_source should be >= 0; currently {ns.per_source}")

    if ns.sources < 0:
        parser.error(f"sources should be >= 0; currently {ns.sources}")
    
    return ns


def main():
    opts = parse_args()
    sources = [s for s in load_sources() if s.type in opts.types]

    slack_webhook = opts.slack_webhook or os.environ.get("FNW_SLACK_WEBHOOK")
    slack_classes = tuple(s.strip() for s in opts.slack_classes.split(",") if s.strip()) or None

    if opts.sources > 0:
        sources = sources[:opts.sources]

    if not sources:
        print(f"No enabled sources match types: {', '.join(opts.types)}. "
            "Check configs/sources.yaml or --types.")
        sys.exit(1)

    rules = None
    regex_cache = None

    try:
        rules = load_classifier_ruleset()
        regex_cache = build_regex_cache(rules)
    except Exception as e:
        print(f"[classifier] note: couldn't load rules (skipping classification): {e}")

    
    all_items = []
    
    for s in sources:
        limit = opts.per_source if opts.per_source > 0 else s.fetch_limit
        items = pull_feed(s, limit=limit)
        all_items.extend(items)
        print(f"{s.name}: {len(items)} items")
    
    if not all_items:
        print("No items fetched")
        sys.exit(0)
    
    idx = build_alias_index(load_watchlist())
    attach_tickers(all_items, idx)
    tagged = sum(1 for it in all_items if it.tickers)
    print(f"Matched tickers on {tagged}/{len(all_items)} items")

    if rules and regex_cache:
        for it in all_items:
            best, score, debug = classify_item(it, rules, regex_cache)
            it.event_class = best
            it.materiality_score = score
            setattr(it, "_cls_debug", debug)

    for it in all_items:
        detect_has_numbers(it)

    items = all_items
    if opts.only_eligible:
        items = [it for it in items if it.event_class is not None]
    
    if opts.sort == "score":
        items = sorted(
            items,
            key=lambda it: (it.materiality_score, it.published_at),
            reverse=True
        )
    else:
        items = sorted(items, key=lambda it: it.published_at, reverse=True)

    filtered_items = items[:opts.max_items]

    sent = posted = 0
    if slack_webhook:
        candidates = filtered_items
        for it in candidates:
            if not should_alert(
                it,
                min_score=opts.slack_min_score,
                classes=slack_classes,
                only_watchlist=opts.slack_only_watchlist,
                require_numbers=opts.slack_require_numbers
            ):
                continue
            if was_sent(it.source_name, it.headline):
                continue

            payload = {"blocks": build_blocks_for_item(it)}
            if opts.slack_dry_run:
                print("[slack dry-run] would send:", it.headline)
            else:
                try:
                    post_to_slack(slack_webhook, payload)
                    posted += 1
                    mark_sent(it.source_name, it.headline)
                    time.sleep(max(0.0, opts.slack_rate_limit))
                except Exception as e:
                    print(f"[slack] failed: {e}")

    if slack_webhook:
        print(f"Slack: posted {posted} alert(s).")

    now_utc = datetime.now(timezone.utc).isoformat()
    print(
        f"FinNewsWatcher CLI — {now_utc}\n"
        f"Sources: {len(sources)} | Types: {', '.join(opts.types)} | "
        f"Items: {len(all_items)} | Sort: {opts.sort}"
        + (" | Only eligible" if opts.only_eligible else "")
)

    for item in filtered_items:
        ticker_str = f" [{','.join(item.tickers)}]" if item.tickers else ""
        cls_str = f", {item.materiality_score}" if getattr(item, "materiality_score", 0) else ""
        evt = item.event_class or "—"
        print(
            f"{item.published_at.isoformat()}   |   "
            f"[{item.source_type}] {item.headline} ({item.source_name}){ticker_str} "
            f"[{evt}{cls_str}]"
        )
        if opts.verbose:
            print(item.url)
            if item.body_snippet:
                print(item.body_snippet[:200])

        if opts.debug_classify and hasattr(item, "_cls_debug"):
            for line in item._cls_debug:
                print("  ", line)

    return None


if __name__ == "__main__":
    main()