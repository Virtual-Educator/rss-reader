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

# Page layout and styling
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  /* Center container and remove link underlines */
  div.block-container { max-width: 1200px; margin-left: auto; margin-right: auto; }
  a { text-decoration: none !important; }
  /* Card styles */
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 16px; background-color: #f9f9f9; }
  .card-title a { font-size: 1.1rem; font-weight: bold; color: inherit; }
  .card-meta { color: #555; font-size: 0.9rem; margin: 4px 0 8px 0; }
  .card-snippet { font-size: 0.95rem; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# File paths
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Load feeds and archive list
feeds = load_json(FEEDS_PATH, default=[])
archived = load_json(ARCHIVE_PATH, default=[])

# Fetch and dedupe entries
with st.spinner("Loading articles…"):
    raw_entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

seen = set()
entries = []
for e in raw_entries:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        entries.append(e)

# Top controls: Refresh and Category filter
col_refresh, col_cat = st.columns([1, 4], gap="small")
if col_refresh.button("Refresh"):
    st.rerun()

categories = sorted({e["source"] for e in entries})
selected_cat = col_cat.selectbox("Category", ["All"] + categories)

# Filter entries by category and archive status
filtered = []
for e in entries:
    if is_archived(e["link"], archived):
        continue
    if selected_cat != "All" and e["source"] != selected_cat:
        continue
    filtered.append(e)

# Sort by most recent
filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=True
)

# Display in rows of three cards
for row_start in range(0, len(filtered), 3):
    cols = st.columns(3, gap="small")
    for col_idx, e in enumerate(filtered[row_start:row_start + 3]):
        with cols[col_idx]:
            link = e.get("link", "#")
            title = e.get("title", "[No title]")
            domain = urlparse(link).netloc
            if e.get("published_parsed"):
                date_str = e["published_parsed"].strftime("%Y-%m-%d")
            else:
                date_str = e.get("published", "")[:10]
            full = e.get("summary", "")
            length = e.get("snippet_length", 250) or 250
            snippet = full[:length] + ("..." if len(full) > length else "")

            # Card container
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f'<div class="card-title"><a href="{link}">{title}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-meta">{domain} • {date_str}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-snippet">{snippet}</div>', unsafe_allow_html=True)

            # Actions dropdown
            action = st.selectbox(
                "",
                ["", "Copy link", "Copy citation", "Print view", "Archive"],
                key=f"action_{row_start + col_idx}",
                label_visibility="collapsed"
            )
            if action == "Copy link":
                pyperclip.copy(link)
                st.info("Link copied")
            elif action == "Copy citation":
                citation = build_apa_citation(e, {})
                pyperclip.copy(citation)
                st.info("Citation copied")
            elif action == "Print view":
                st.markdown(f'[Print]({link})')
            elif action == "Archive":
                add_to_archive(link, ARCHIVE_PATH)
                st.info("Archived")

            st.markdown('</div>', unsafe_allow_html=True)
