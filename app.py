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

# Load data from local files
feeds = load_json(FEEDS_PATH, default=[])
settings = load_json(
    SETTINGS_PATH,
    default={
        "show_archived": False,
        "sort_order": "newest_first",
        "filters": {"include_keywords": [], "exclude_keywords": []},
    },
)
authors = load_json(AUTHORS_PATH, default={})
archived = load_json(ARCHIVE_PATH, default=[])

st.set_page_config(page_title="Personal RSS Reader", layout="wide")

# Sidebar: settings
st.sidebar.title("Settings")

def refresh():
    st.experimental_rerun()

st.sidebar.button("Refresh Feeds", on_click=refresh)

show_arch = st.sidebar.checkbox(
    "Show archived items", settings.get("show_archived", False)
)
sort_order = st.sidebar.selectbox(
    "Sort order", ["newest_first", "oldest_first"], index=0
)

include = st.sidebar.text_input(
    "Include keywords (comma-separated)",
    value=",".join(settings["filters"]["include_keywords"])
)
exclude = st.sidebar.text_input(
    "Exclude keywords (comma-separated)",
    value=",".join(settings["filters"]["exclude_keywords"])
)

# Update and save settings
settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
settings["filters"]["include_keywords"] = [
    k.strip() for k in include.split(",") if k.strip()
]
settings["filters"]["exclude_keywords"] = [
    k.strip() for k in exclude.split(",") if k.strip()
]
save_json(SETTINGS_PATH, settings)

with st.sidebar.expander("Manage RSS feeds"):
    st.write(feeds)
    new_url = st.text_input("New feed URL")
    new_cat = st.text_input("Category")
    if st.button("Add feed") and new_url:
        feeds.append({"url": new_url, "category": new_cat or "Uncategorized"})
        save_json(FEEDS_PATH, feeds)
        st.experimental_rerun()

    st.markdown("Bulk add feeds by pasting one URL per line or 'URL,Category'")
    bulk = st.text_area("", height=150)
    if st.button("Import feeds") and bulk:
        lines = [l.strip() for l in bulk.splitlines() if l.strip()]
        for line in lines:
            if "," in line:
                url, cat = line.split(",", 1)
            else:
                url, cat = line, "Uncategorized"
            feeds.append({"url": url.strip(), "category": cat.strip()})
        save_json(FEEDS_PATH, feeds)
        st.experimental_rerun()

# Main view
st.title("Personal news reader")

entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

filtered = []
inc = [k.lower() for k in settings["filters"]["include_keywords"]]
exc = [k.lower() for k in settings["filters"]["exclude_keywords"]]

for entry in entries:
    if not show_arch and is_archived(entry["link"], archived):
        continue
    title = entry.get("title", "").lower()
    summary = entry.get("summary", "").lower()

    if any(k in title or k in summary for k in exc):
        continue
    if inc and not any(k in title or k in summary for k in inc):
        continue

    filtered.append(entry)

filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=(sort_order == "newest_first"),
)

for entry in filtered:
    st.subheader(entry.get("title"))
    st.write(
        f"Source: {entry.get('source')}  |  Published: {entry.get('published')}"
    )
    cols = st.columns(3)
    if cols[0].button("Copy link", key=entry.get("link")):
        pyperclip.copy(entry.get("link"))
        st.success("Link copied")
    if cols[1].button("Copy citation", key=entry.get("link") + "cite"):
        citation = build_apa_citation(entry, authors)
        pyperclip.copy(citation)
        st.success("Citation copied")
    if cols[2].button("Archive", key=entry.get("link") + "arch"):
        add_to_archive(entry.get("link"), ARCHIVE_PATH)
        st.success("Added to archive")
    st.markdown(f"[Print view]({entry.get('link')})")

st.write("Powered by your local RSS reader.")
