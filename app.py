# File: app.py
import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from utils.file_io import load_json, save_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# File paths
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
AUTHORS_PATH = os.path.join(BASE_DIR, "authors.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Load local data
feeds = load_json(FEEDS_PATH, default=[])
settings = load_json(SETTINGS_PATH, default={
    "show_archived": False,
    "sort_order": "newest_first",
    "filters": {"include_keywords": [], "exclude_keywords": []}
})
authors = load_json(AUTHORS_PATH, default={})
archived = load_json(ARCHIVE_PATH, default=[])

st.set_page_config(page_title="Personal RSS Reader", layout="wide")

# Sidebar: Settings
st.sidebar.title("Settings")
if st.sidebar.button("Refresh Feeds"):
    st.experimental_rerun()

show_arch = st.sidebar.checkbox("Show Archived", settings.get("show_archived", False))
sort_order = st.sidebar.selectbox("Sort Order", ["newest_first", "oldest_first"], index=0)
settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
save_json(SETTINGS_PATH, settings)

st.sidebar.markdown("---")
stide_exp = st.sidebar.expander("Manage RSS Feeds")
with tide_exp:
    st.write(feeds)
    new_url = st.text_input("New RSS URL")
    new_cat = st.text_input("Category")
    if st.button("Add Feed") and new_url:
        feeds.append({"url": new_url, "category": new_cat or "Uncategorized"})
        save_json(FEEDS_PATH, feeds)
        st.experimental_rerun()

# Main App
st.title("Personal News Reader")

# Fetch and parse
entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Filter and sort
filtered = []
for e in entries:
    if not show_arch and is_archived(e["link"], archived):
        continue
    title = e.get("title", "")
    inc = settings["filters"]["include_keywords"]
    exc = settings["filters"]["exclude_keywords"]
    if any(k.lower() in title.lower() for k in exc):
        continue
    filtered.append(e)

filtered.sort(key=lambda x: x.get("published_parsed", datetime.min), reverse=(sort_order=="newest_first"))

# Display
for entry in filtered:
    st.subheader(entry.get("title"))
    st.write(f"Source: {entry.get('source')} | Published: {entry.get('published')}")
    cols = st.columns(3)
    if cols[0].button("Copy Link", key=entry.get("link")):
        pyperclip.copy(entry.get("link"))
        st.toast("Link copied to clipboard")
    if cols[1].button("Copy APA Citation", key=entry.get("link")+"cite"):
        citation = build_apa_citation(entry, authors)
        pyperclip.copy(citation)
        st.toast("APA citation copied")
    if cols[2].button("Archive", key=entry.get("link")+"arch"):
        add_to_archive(entry.get("link"), ARCHIVE_PATH)
        st.toast("Article archived")
    # Print link
    st.markdown(f"[Print view]({entry.get('link')})")

# Footer
st.markdown("---")
st.write("Powered by your local RSS reader.")


# File: utils/rss.py
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
        # Cache raw feed
        fname = os.path.join(cache_dir, f"{cat.replace(' ', '_')}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(parsed.entries, f, default=str)
    return all_entries


# File: utils/citation.py
from dateutil import parser

def build_apa_citation(entry, author_overrides):
    author = entry.get("author") or author_overrides.get(entry.get("source")) or "[Author]"
    try:
        date = parser.parse(entry.get("published")).strftime("%Y, %B %d")
    except Exception:
        date = "[n.d.]"
    title = entry.get("title", "[No title]")
    source = entry.get("source", "[Source]")
    url = entry.get("link")
    return f"{author}. ({date}). {title}. {source}. {url}"


# File: utils/file_io.py
import json
import os

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# File: utils/archive.py
import json
import os
import hashlib

def _hash_link(link):
    return hashlib.sha256(link.encode("utf-8")).hexdigest()

def is_archived(link, archived_list):
    return _hash_link(link) in archived_list

def add_to_archive(link, path):
    archived = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            archived = json.load(f)
    h = _hash_link(link)
    if h not in archived:
        archived.append(h)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(archived, f, indent=2)
