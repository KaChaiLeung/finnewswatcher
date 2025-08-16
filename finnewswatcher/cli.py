import argparse
from datetime import datetime, timezone
import sys

from finnewswatcher.config import load_sources
from finnewswatcher.fetchers.rss import pull_feed
from finnewswatcher.models import NormalizedItem, SourceType
from typing import get_args


ALLOWED_TYPES = {t.lower() for t in get_args(SourceType)}


def parse_args():
    parser = argparse.ArgumentParser(prog="finnewswatcher",
                                     description="Fetches recent items from configured sources (rns, press, wire, filing), normalizes them to FinNewsWatcher items, and prints a UTC-sorted headline list. Use --types to filter source types, --sources to limit how many feeds to pull, --per-source to cap entries per feed, --max-items for output size, and --verbose to include URLs/snippets")
    parser.add_argument("--types", type=str, default="rns", help="Comma-separated list of source types to pull: rns,press,wire,filing")
    parser.add_argument("--max-items", type=int, default=20, help="Max number of items to print overall (after sorting)")
    parser.add_argument("--per-source", type=int, default=0, help="Number of entries to read per source")
    parser.add_argument("--sources", type=int, default=0, help="Number of sources to pull (0 = all)")
    parser.add_argument("--verbose", action="store_true", help="When set, print URL and snippet lines")

    ns = parser.parse_args()

    types = [s for s in (t.strip().lower() for t in ns.types.split(",")) if s]
    types = list(dict.fromkeys(types))
    invalid = [t for t in types if t not in ALLOWED_TYPES]

    if invalid:
        parser.error(f"Invalid --types {invalid}; valid: {", ".join(sorted(ALLOWED_TYPES))}")

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

    if opts.sources > 0:
        sources = sources[:opts.sources]

    if not sources:
        print(f"No enabled sources match types: {", ".join(opts.types)}."
              f"Check configs/sources.yaml or --types.")
        sys.exit(1)
    
    all_items = []
    
    for s in sources:
        limit = opts.per_source if opts.per_source > 0 else s.fetch_limit
        items = pull_feed(s)
        all_items.extend(items)
        print(f"{s.name}: {len(items)} items")
    
    if not all_items:
        print("No items fetched")
        sys.exit(0)

    filtered_items = sorted(all_items, key=lambda it: it.published_at, reverse=True)[:opts.max_items]

    now_utc = datetime.now(timezone.utc).isoformat()
    
    print(f"FinNewsWatcher CLI — {now_utc}"
          f"Sources: {len(sources)} | Types: {",".join(opts.types)} | Items: {len(all_items)}")

    for item in filtered_items:
        print(f"{item.published_at.isoformat()} | [{item.source_type}] {item.headline} ({item.source_name})")
    
    if opts.verbose:
        print(f"{item.url}\n{item.body_snippet[:200]}")

    return None


if __name__ == "__main__":
    main()