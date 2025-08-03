import feedparser
import os
import json
from datetime import datetime

def fetch_and_parse_feeds(feeds, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    all_entries = []
    for feed in feeds:
        url = feed.get("url")
        cat = feed.get("category", "Uncategorized")
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            e = {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "published": entry.get("published", ""),
                "published_parsed": datetime(*entry.published_parsed[:6]) if entry.get("published_parsed") else None,
                "author": entry.get("author", None),
                "summary": entry.get("summary", ""),
                "source": cat
            }
            all_entries.append(e)
            # Cache raw entries with a safe filename
            safe_cat = cat.replace(' ', '_').replace('/', '_')
            fname = os.path.join(cache_dir, f"{safe_cat}.json")
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(parsed.entries, f, default=str)

    return all_entries
