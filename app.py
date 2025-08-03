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

# Load configuration and data
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

st.set_page_config(page_title="Personal News Reader", layout="wide")

# Sidebar controls
st.sidebar.title("Controls")
if st.sidebar.button("Refresh"):
    st.rerun()

show_arch = st.sidebar.checkbox("Show archived", settings["show_archived"])
sort_order = st.sidebar.selectbox("Sort by", ["newest_first", "oldest_first"], index=0)

inc = st.sidebar.text_input(
    "Include keywords", value=",".join(settings["filters"]["include_keywords"])
)
exc = st.sidebar.text_input(
    "Exclude keywords", value=",".join(settings["filters"]["exclude_keywords"])
)

# Save sidebar settings
settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
settings["filters"]["include_keywords"] = [k.strip() for k in inc.split(",") if k.strip()]
settings["filters"]["exclude_keywords"] = [k.strip() for k in exc.split(",") if k.strip()]
save_json(SETTINGS_PATH, settings)

st.title("Personal News Reader")

# Fetch and dedupe
with st.spinner("Loading…"):
    raw = fetch_and_parse_feeds(feeds, CACHE_DIR)
seen = set()
entries = []
for e in raw:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        entries.append(e)

# Apply filters
inc_lc = [k.lower() for k in settings["filters"]["include_keywords"]]
exc_lc = [k.lower() for k in settings["filters"]["exclude_keywords"]]
filtered = []
for e in entries:
    if not show_arch and is_archived(e["link"], archived):
        continue
    text = (e.get("title","") + " " + e.get("summary","")).lower()
    if any(k in text for k in exc_lc):
        continue
    if inc_lc and not any(k in text for k in inc_lc):
        continue
    filtered.append(e)

filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=(sort_order == "newest_first"),
)

# Display with expanders
for idx, e in enumerate(filtered):
    title = e.get("title", "[No title]")
    if e.get("published_parsed"):
        date_str = e["published_parsed"].strftime("%Y-%m-%d")
    else:
        date_str = e.get("published", "")[:10]
    feed_url = e.get("feed_url", "")

    with st.expander(f"{title} | {date_str}", expanded=False):
        st.markdown(f"*Source: <{feed_url}>*")

        # Summary snippet
        full_summary = e.get("summary", "")
        length = e.get("snippet_length", 150) or 150
        snippet = full_summary[:length]
        suffix = "..." if len(full_summary) > length else ""
        st.write(snippet + suffix)

        # Action buttons
        c1, c2, c3 = st.columns([1, 1, 1])
        if c1.button("Link", key=f"link_{idx}"):
            pyperclip.copy(e.get("link"))
            st.info("Link copied")
        if c2.button("Cite", key=f"cite_{idx}"):
            citation = build_apa_citation(e, authors)
            pyperclip.copy(citation)
            st.info("Citation copied")
        if c3.button("Archive", key=f"arch_{idx}"):
            add_to_archive(e.get("link"), ARCHIVE_PATH)
            st.info("Archived")

        st.markdown(f"[Print]({e.get('link')})")

st.caption("Powered by your local RSS reader")
