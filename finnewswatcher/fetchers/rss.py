from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import calendar
import time as _time
from typing import List, cast
import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import re
import feedparser
import httpx
from pydantic import HttpUrl

from finnewswatcher.config import SourceConfig
from finnewswatcher.models import NormalizedItem


def _as_dt(entry) -> datetime:
    """Convert a feedparser entry's timestamp to a timezone-aware UTC datetime. Falls back on current time if no published or updated timestamp."""
    try:
        # --- struct-time sources ---
        published_parsed = getattr(entry, "published_parsed", None)
        if published_parsed is None and hasattr(entry, "get"):
            published_parsed = entry.get("published_parsed")

        if isinstance(published_parsed, _time.struct_time):
            ts = calendar.timegm(published_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        updated_parsed = getattr(entry, "updated_parsed", None)
        if updated_parsed is None and hasattr(entry, "get"):
            updated_parsed = entry.get("updated_parsed")

        if isinstance(updated_parsed, _time.struct_time):
            ts = calendar.timegm(updated_parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        # --- string date sources ---
        published = getattr(entry, "published", None)
        if published is None and hasattr(entry, "get"):
            published = entry.get("published")

        if isinstance(published, str) and published.strip():
            dt = parsedate_to_datetime(published)
            return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc))

        updated = getattr(entry, "updated", None)
        if updated is None and hasattr(entry, "get"):
            updated = entry.get("updated")

        if isinstance(updated, str) and updated.strip():
            dt = parsedate_to_datetime(updated)
            return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc))

    except Exception:
        pass

    return datetime.now(timezone.utc)


def _canonical_url(url:str) -> str:
    """Lowercase scheme/host, drop fragments and common tracking params."""
    try:
        parts = urlsplit((url or "").strip())
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = parts.path or "/"

        # Remove tracking query params like utm_*, fbclid, gclid, etc.
        drop_keys = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref"}
        qs = parse_qsl(parts.query, keep_blank_values=True)
        qs = [(k, v) for (k, v) in qs if not (k.lower().startswith("utm_") or k.lower() in drop_keys)]
        query = urlencode(qs, doseq=True)

        return urlunsplit((scheme, netloc, path, query, ""))

    except Exception:
        return (url or "").strip()
    

def _norm_text(s:str) -> str:
    """Trim, lowercase, and collapse internal whitespace for stability."""
    s = (s or "").strip().lower()
    return " ".join(s.split())


def _make_id(link:str, title:str, length:int=12) -> str:
    """Stable short ID derived from canonical URL + normalized title."""
    link_c = _canonical_url(link or "")
    title_n = _norm_text(title or "")
    raw = f"{link_c}|{title_n}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def _extract_summary(entry) -> str:
    """
    Get short, readable snippet for item. Prefers "summary" then "description", the first "content" block. Strips HTML tags and collapses whitespace.
    """
    whitespace_re = re.compile(r"\s+")
    html_tag_re = re.compile("<[^>]+>")

    text = ""

    for key in ("summary", "description"):
        val = getattr(entry, key, None)
        if val is None and hasattr(entry, "get"):
            val = entry.get(key)
        if isinstance(val, str) and val.strip():
            text = val
            break
    
    if not text:
        content = getattr(entry, "content", None)
        if content is None and hasattr(entry, "get"):
            content = entry.get("content")
        if isinstance(content, list) and content:
            block = content[0]
            val = getattr(block, "value", None)
            if val is None and isinstance(block, dict):
                val = block.get("value")
            if isinstance(val, str):
                text = val
    
    if text:
        text = html_tag_re.sub(" ", text)
        text = whitespace_re.sub(" ", text).strip()
        text = text[:400]
    
    return text


def pull_feed(src: SourceConfig, limit: int | None = None) -> List[NormalizedItem]:
    """
    Fetch one RSS/Atom feed and map entries to NormalizedItem.
    - limit: optional cap on number of entries to read from the feed.
    - Falls back to src.fetch_limit or 20 if not provided.
    """
    items: List[NormalizedItem] = []
    # prefer explicit limit; fall back to src.fetch_limit; then 20
    eff_limit = limit if (isinstance(limit, int) and limit > 0) else (getattr(src, "fetch_limit", 20) or 20)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; FinNewsWatcher/1.0; +https://example.local)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
        }
        resp = httpx.get(str(src.url), headers=headers, timeout=10, follow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        if not any(t in content_type for t in ("xml", "rss", "atom")):
            print(f"[pull_feed] Not XML for '{src.name}': {content_type} — skipping")
            return items

        feed = feedparser.parse(resp.content)

        if getattr(feed, "bozo", 0) and not getattr(feed, "entries", []):
            exc = getattr(feed, "bozo_exception", None)
            exc_msg = f"{type(exc).__name__}: {exc}" if exc else "unknown parse error"
            preview = resp.content[:200].decode("utf-8", errors="ignore").replace("\n", " ")
            print(f"[pull_feed] Malformed feed for '{src.name}': {exc_msg} | body preview: {preview}")
            return items

        entries = getattr(feed, "entries", []) or []
    except Exception as e:
        print(f"[pull_feed] Failed to fetch/parse '{src.name}': {e}")
        return items

    for entry in entries[:eff_limit]:
        try:
            title = getattr(entry, "title", None)
            if title is None and hasattr(entry, "get"):
                title = entry.get("title")
            title = title or ""

            link = getattr(entry, "link", None)
            if link is None and hasattr(entry, "get"):
                link = entry.get("link")
            link = (link or "").strip()

            published_at = _as_dt(entry)
            snippet = _extract_summary(entry)

            url_value: HttpUrl = src.url if not link else cast(HttpUrl, link)
            item = NormalizedItem(
                id=_make_id(link or str(src.url), title),
                published_at=published_at,
                source_name=src.name,
                source_type=src.type,
                url=url_value,                # now typed as HttpUrl
                headline=title or "(no title)",
                body_snippet=snippet or "",
            )

            items.append(item)

        except Exception as e:
            print(f"[pull_feed] Skipped one entry from '{src.name}': {e}")

    items.sort(key=lambda x: x.published_at, reverse=True)
    return items