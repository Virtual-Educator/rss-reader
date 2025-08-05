import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from urllib.parse import urlparse
from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# apply page layout and center container
st.set_page_config(page_title="Personal News Reader", layout="wide")
st.markdown(
    """
    <style>
      div.block-container {
        max-width: 1200px;
        margin-left: auto;
        margin-right: auto;
      }
      a {
        text-decoration: none !important;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# load data
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

feeds = load_json(FEEDS_PATH, default=[])
archived = load_json(ARCHIVE_PATH, default=[])

# fetch and dedupe
with st.spinner("Loading articles..."):
    raw_entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

seen, entries = set(), []
for e in raw_entries:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        entries.append(e)

# top controls
col_refresh, col_cat = st.columns([1, 4], gap="small")
if col_refresh.button("Refresh"):
    st.rerun()

categories = sorted({e["source"] for e in entries})
selected_cat = col_cat.selectbox("Category", ["All"] + categories)

# filter and sort
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

# display articles
for idx, e in enumerate(filtered):
    link = e.get("link", "#")
    title = e.get("title", "[No title]")

    # Parse date and source domain
    if e.get("published_parsed"):
        date_str = e["published_parsed"].strftime("%Y-%m-%d")
    else:
        date_str = e.get("published", "")[:10]
    domain = urlparse(link).netloc

    # Create three columns: Title/Meta, Snippet, Actions
    col1, col2, col3 = st.columns([3, 5, 2], gap="small")

    with col1:
        # Hyperlinked title without underline
        st.markdown(f'<a href="{link}" style="font-size:1.25rem;">{title}</a>', unsafe_allow_html=True)
        st.markdown(f'*{domain} • {date_str}*')

    with col2:
        full = e.get("summary", "")
        length = e.get("snippet_length", 250) or 250
        snippet = full[:length]
        suffix = "..." if len(full) > length else ""
        st.write(snippet + suffix)

    with col3:
        action = st.selectbox(
            "",
            [" ", "Copy link", "Copy citation", "Print view", "Archive"],
            key=f"act_{idx}",
            label_visibility="collapsed"
        )
        if action == "Copy link":
            pyperclip.copy(link)
            st.info("Link copied")
        elif action == "Copy citation":
            cit = build_apa_citation(e, authors)
            pyperclip.copy(cit)
            st.info("Citation copied")
        elif action == "Print view":
            st.markdown(f'[Print]({link})')
        elif action == "Archive":
            add_to_archive(link, ARCHIVE_PATH)
            st.info("Archived")

st.caption("Powered by your local RSS reader")
