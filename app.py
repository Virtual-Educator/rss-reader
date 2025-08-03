import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from utils.file_io import load_json, save_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# Paths
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
AUTHORS_PATH = os.path.join(BASE_DIR, "authors.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Load settings & data
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

def refresh():
    st.rerun()

# Sidebar controls
st.sidebar.title("Settings")
st.sidebar.button("Refresh Feeds", on_click=refresh)

show_arch = st.sidebar.checkbox("Show archived items", settings["show_archived"])
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

# Save updated filters
settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
settings["filters"]["include_keywords"] = [
    k.strip() for k in include.split(",") if k.strip()
]
settings["filters"]["exclude_keywords"] = [
    k.strip() for k in exclude.split(",") if k.strip()
]
save_json(SETTINGS_PATH, settings)

st.title("Personal News Reader")

# Fetch
with st.spinner("Fetching latest articles..."):
    entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Filter & sort
inc = [k.lower() for k in settings["filters"]["include_keywords"]]
exc = [k.lower() for k in settings["filters"]["exclude_keywords"]]
filtered = []
for e in entries:
    if not show_arch and is_archived(e["link"], archived):
        continue
    txt = (e.get("title","") + " " + e.get("summary","")).lower()
    if any(k in txt for k in exc):
        continue
    if inc and not any(k in txt for k in inc):
        continue
    filtered.append(e)

filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=(sort_order == "newest_first"),
)

# Display
for idx, e in enumerate(filtered):
    st.subheader(e.get("title"))
    # Source URL + Date only
    feed_url = e.get("feed_url", "")
    if e.get("published_parsed"):
        date_str = e["published_parsed"].strftime("%Y-%m-%d")
    else:
        date_str = e.get("published", "").split(",")[0]
    st.write(f"Source: {feed_url} | Date: {date_str}")
    # 150-char snippet
    snippet = e.get("summary","")
    st.write(snippet[:150] + ("…" if len(snippet) > 150 else ""))
    cols = st.columns(3)
    if cols[0].button("Copy link", key=f"link_{idx}"):
        pyperclip.copy(e.get("link"))
        st.success("Link copied")
    if cols[1].button("Copy citation", key=f"cite_{idx}"):
        c = build_apa_citation(e, authors)
        pyperclip.copy(c)
        st.success("Citation copied")
    if cols[2].button("Archive", key=f"arch_{idx}"):
        add_to_archive(e.get("link"), ARCHIVE_PATH)
        st.success("Archived")
    st.markdown(f"[Print view]({e.get('link')})")

st.write("Powered by your local RSS reader.")
