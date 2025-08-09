# File: utils/rss.py

import os
import json
from datetime import datetime
from typing import Optional

import feedparser
from bs4 import BeautifulSoup


def _safe_filename(name: str) -> str:
    """Return a filesystem friendly filename stem."""
    keep = []
    for ch in name.strip():
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "_", "-"):
            keep.append("_")
        else:
            keep.append("_")
    stem = "".join(keep).strip("_")
    return stem[:80] or "feed"


def _first_img_from_summary(summary_html: str) -> Optional[str]:
    if not summary_html:
        return None
    try:
        soup = BeautifulSoup(summary_html, "html.parser")
        tag = soup.find("img")
        return tag.get("src") if tag and tag.get("src") else None
    except Exception:
        return None


def _extract_thumbnail(entry) -> Optional[str]:
    """
    Try common RSS media fields first, then fallback to first <img> in summary.
    Returns a URL or None.
    """
    # media_thumbnail
    try:
        mt = getattr(entry, "media_thumbnail", None)
        if isinstance(mt, list) and mt and isinstance(mt[0], dict):
            url = mt[0].get("url")
            if url:
                return url
    except Exception:
        pass

    # media_content
    try:
        mc = getattr(entry, "media_content", None)
        if isinstance(mc, list):
            for m in mc:
                if isinstance(m, dict) and m.get("url"):
                    if m.get("medium") in (None, "image"):
                        return m["url"]
    except Exception:
        pass

    # enclosure link
    try:
        for l in getattr(entry, "links", []):
            if isinstance(l, dict) and l.get("rel") == "enclosure":
                if str(l.get("type", "")).startswith("image/") and l.get("href"):
                    return l["href"]
    except Exception:
        pass

    # summary <img>
    try:
        return _first_img_from_summary(entry.get("summary", ""))
    except Exception:
        return None


def _extract_author(entry) -> Optional[str]:
    """
    Try a few places where author data often lives.
    """
    # feedparser standard
    if entry.get("author"):
        return entry.get("author")

    # Dublin Core
    if entry.get("dc_creator"):
        return entry.get("dc_creator")

    # authors list
    authors = entry.get("authors")
    if isinstance(authors, list) and authors:
        first = authors[0]
        if isinstance(first, dict) and first.get("name"):
            return first.get("name")
        if isinstance(first, str):
            return first

    return None


def _extract_published(entry) -> tuple[Optional[datetime], str]:
    """
    Return (datetime or None, display_string).
    Prefer published_parsed, then updated_parsed.
    """
    dt = None
    if entry.get("published_parsed"):
        try:
            dt = datetime(*entry.published_parsed[:6])
        except Exception:
            dt = None
    elif entry.get("updated_parsed"):
        try:
            dt = datetime(*entry.updated_parsed[:6])
        except Exception:
            dt = None

    if dt is not None:
        return dt, dt.strftime("%Y-%m-%d")

    # fallback to raw strings
    raw = entry.get("published") or entry.get("updated") or ""
    return None, raw


def fetch_and_parse_feeds(feeds: list[dict], cache_dir: str) -> list[dict]:
    """
    Fetch and parse the list of feeds.
    Supports per-feed filters, item limits, and snippet length passthrough.

    feeds item shape:
      {
        "url": "...",
        "category": "Technology",
        "filters": {"include": ["ai"], "exclude": ["sports"]},
        "max_items": 5,
        "snippet_length": 250
      }

    Returns a flat list of normalized article dicts:
      {
        title, link, published, published_parsed, author,
        summary, source, feed_url, snippet_length, thumbnail
      }
    """
    os.makedirs(cache_dir, exist_ok=True)
    all_entries: list[dict] = []

    for feed in feeds:
        url = feed.get("url")
        category = feed.get("category", "Uncategorized")
        include = [k.lower() for k in feed.get("filters", {}).get("include", [])]
        exclude = [k.lower() for k in feed.get("filters", {}).get("exclude", [])]
        max_items = feed.get("max_items")
        snippet_len = feed.get("snippet_length")

        if not url:
            continue

        parsed = feedparser.parse(url)

        # cache raw feed to disk for troubleshooting
        try:
            fname = f"{_safe_filename(category)}.json"
            with open(os.path.join(cache_dir, fname), "w", encoding="utf-8") as f:
                json.dump(parsed.entries, f, default=str, ensure_ascii=False, indent=2)
        except Exception:
            pass

        items: list[dict] = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link")
            summary_html = entry.get("summary", "") or entry.get("description", "")

            # keyword filters on title+summary
            text_for_filter = f"{title} {BeautifulSoup(summary_html or '', 'html.parser').get_text(' ', strip=True)}".lower()
            if exclude and any(k in text_for_filter for k in exclude):
                continue
            if include and not any(k in text_for_filter for k in include):
                continue

            dt, display_date = _extract_published(entry)
            author = _extract_author(entry)
            thumb = _extract_thumbnail(entry)

            item = {
                "title": title,
                "link": link,
                "published": display_date,
                "published_parsed": dt,
                "author": author,
                "summary": summary_html,
                "source": category,       # category you defined in feeds.json
                "feed_url": url,          # the RSS feed address
                "snippet_length": snippet_len,
                "thumbnail": thumb,
            }
            items.append(item)

        # apply per-feed item cap
        if isinstance(max_items, int) and max_items > 0:
            items = items[:max_items]

        all_entries.extend(items)

    return all_entries
