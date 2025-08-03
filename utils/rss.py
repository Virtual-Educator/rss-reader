# File: utils/rss.py

import feedparser
import os
import json
from datetime import datetime

def fetch_and_parse_feeds(feeds, cache_dir):
    """
    Fetches and parses RSS feeds according to per-feed filters and limits.
    Caches raw feed data in cache_dir and returns a list of article dicts.
    """
    os.makedirs(cache_dir, exist_ok=True)
    all_entries = []

    for feed in feeds:
        url = feed.get("url")
        category = feed.get("category", "Uncategorized")
        include_keywords = [k.lower() for k in feed.get("filters", {}).get("include", [])]
        exclude_keywords = [k.lower() for k in feed.get("filters", {}).get("exclude", [])]
        max_items = feed.get("max_items")
        snippet_length = feed.get("snippet_length")
        parsed = feedparser.parse(url)

        entries = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            title_lc = title.lower()
            summary_lc = summary.lower()

            # Exclude filter
            if exclude_keywords and any(k in title_lc or k in summary_lc for k in exclude_keywords):
                continue

            # Include filter
            if include_keywords and not any(k in title_lc or k in summary_lc for k in include_keywords):
                continue

            # Parse publication date
            published_parsed = None
            if entry.get("published_parsed"):
                try:
                    published_parsed = datetime(*entry.published_parsed[:6])
                except Exception:
                    published_parsed = None

            entries.append({
                "title": title,
                "link": entry.get("link"),
                "published": entry.get("published", ""),
                "published_parsed": published_parsed,
                "author": entry.get("author"),
                "summary": summary,
                "source": category,
                "feed_url": url,
                "snippet_length": snippet_length
            })

        # Limit number of items per feed
        if isinstance(max_items, int) and max_items > 0:
            entries = entries[:max_items]

        all_entries.extend(entries)

        # Cache raw feed data
        safe_category = category.replace(" ", "_").replace("/", "_")
        cache_file = os.path.join(cache_dir, f"{safe_category}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(parsed.entries, f, default=str)

    return all_entries
