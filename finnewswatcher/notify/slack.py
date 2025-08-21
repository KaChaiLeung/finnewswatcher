from __future__ import annotations

import json
import urllib.request
from typing import Optional, Sequence

from finnewswatcher.models import NormalizedItem


def post_to_slack(webhook_url:str, payload:dict, timeout:float=10.0) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Slach webhook HTTP {resp.status}")


def build_blocks_for_item(item:NormalizedItem) -> list[dict]:
    title = item.headline
    subtitle = f"[{item.source_type}] {item.source_name} | {item.published_at.isoformat()}"
    fields: list[dict] = []

    if item.event_class:
        fields.append({"type": "mrkdwn", "text": f"*Class:* {item.event_class}"})
    fields.append({"type": "mrkdwn", "text": f"*Score:* {item.materiality_score}"})
    if item.tickers:
        fields.append({"type": "mrkdwn", "text": f"*Tickers:* `{', '.join(item.tickers)}`"})
    if getattr(item, "entities", None):
        fields.append({"type": "mrkdwn", "text": f"*Entities:* {', '.join(item.entities)[:150]}"})
    if getattr(item, "has_numbers", False):
        fields.append({"type": "mrkdwn", "text": "*Has numbers:* yes"})
    
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*<{str(item.url)}|{title}>*"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": subtitle}]}
    ]
    if item.body_snippet:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": item.body_snippet[:300]}})
    if fields:
        blocks.append({"type": "section", "fields": fields})
    
    return blocks


def should_alert(item:NormalizedItem, *, min_score:int=2, classes:Optional[Sequence[str]]=None, only_watchlist:bool=False, require_numbers:bool=False) -> bool:
    if item.event_class is None:
        return False
    if min_score and item.materiality_score < min_score:
        return False
    if classes and item.eventclass not in classes:
        return False
    if only_watchlist and not item.tickers:
        return False
    if require_numbers and not getattr(item, "has_numbers", False):
        return False
    return True