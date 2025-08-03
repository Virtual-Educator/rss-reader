import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal News Reader",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Paths and Data Load ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

feeds = load_json(FEEDS_PATH, default=[])
archived = load_json(ARCHIVE_PATH, default=[])

# ─── Fetch & Deduplicate ──────────────────────────────────────────────────────
with st.spinner("Loading articles…"):
    raw = fetch_and_parse_feeds(feeds, CACHE_DIR)

seen, entries = set(), []
for e in raw:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        entries.append(e)

# ─── Top Controls: Refresh & Category Filter ─────────────────────────────────
c1, c2 = st.columns([1, 4], gap="small")
if c1.button("🔄 Refresh"):
    st.rerun()

categories = sorted({e["source"] for e in entries})
selected_cat = c2.selectbox("Category", ["All"] + categories)

# ─── Filter & Sort ────────────────────────────────────────────────────────────
filtered = []
for e in entries:
    if is_archived(e["link"], archived):
        continue
    if selected_cat != "All" and e["source"] != selected_cat:
        continue
    filtered.append(e)

filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=True
)

# ─── Display Articles ─────────────────────────────────────────────────────────
for idx, e in enumerate(filtered):
    title = e.get("title", "[No title]")
    # Date
    if e.get("published_parsed"):
        date_str = e["published_parsed"].strftime("%Y-%m-%d")
    else:
        date_str = e.get("published", "")[:10]
    # Source URL
    feed_url = e.get("feed_url", "")

    left, right = st.columns((4, 1), gap="small")

    # Left: headline, meta, snippet
    with left:
        st.subheader(title)
        st.markdown(f"*Source: <{feed_url}>  |  Date: {date_str}*")
        full = e.get("summary", "")
        snippet = full[:250]
        more = "..." if len(full) > 250 else ""
        st.write(snippet + more)

    # Right: actions dropdown
    with right:
        action = st.selectbox(
            "Actions",
            ["—", "Copy link", "Copy citation", "Print view", "Archive"],
            key=f"act_{idx}"
        )
        if action == "Copy link":
            pyperclip.copy(e.get("link"))
            st.info("Link copied")
        elif action == "Copy citation":
            cit = build_apa_citation(e, {})
            pyperclip.copy(cit)
            st.info("Citation copied")
        elif action == "Print view":
            st.markdown(f"[Open printable article]({e.get('link')})")
        elif action == "Archive":
            add_to_archive(e.get("link"), ARCHIVE_PATH)
            st.info("Archived")

st.caption("Powered by your local RSS reader")
