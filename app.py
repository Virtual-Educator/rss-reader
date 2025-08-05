import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# Page layout and styling
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  /* Center container */
  div.block-container { max-width: 700px; margin-left: auto; margin-right: auto; }
  /* Remove link underlines */
  a { text-decoration: none !important; }
  /* Card styles */
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 16px; background-color: #f9f9f9; }
  .card-title a { font-size: 1.1rem; font-weight: bold; color: inherit; }
  .card-meta { color: #555; font-size: 0.9rem; margin: 4px 0 8px 0; }
  .card-snippet { font-size: 0.95rem; margin-bottom: 8px; }
  .card-thumb { width: 100%; height: auto; border-radius: 4px; margin-bottom: 8px; }
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
if col_refresh.button("🔄 Refresh"):
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

            # Extract thumbnail from summary HTML
            thumb = None
            soup = BeautifulSoup(e.get("summary", ""), "html.parser")
            img_tag = soup.find("img")
            if img_tag and img_tag.get("src"):
                thumb = img_tag["src"]

            # Card container start
            st.markdown('<div class="card">', unsafe_allow_html=True)

            # Thumbnail if available
            if thumb:
                st.markdown(f'<img src="{thumb}" class="card-thumb"/>', unsafe_allow_html=True)

            # Title and meta
            st.markdown(f'<div class="card-title"><a href="{link}">{title}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-meta">{domain} • {date_str}</div>', unsafe_allow_html=True)

            # Snippet
            full = BeautifulSoup(e.get("summary", ""), "html.parser").get_text()
            length = 250
            snippet = full[:length] + ("..." if len(full) > length else "")
            st.markdown(f'<div class="card-snippet">{snippet}</div>', unsafe_allow_html=True)

            # Icons for actions
            ic1, ic2, ic3, ic4 = st.columns(4, gap="small")
            if ic1.button("🔗", key=f"link_{row_start+col_idx}"):
                pyperclip.copy(link)
                st.info("Link copied")
            if ic2.button("📋", key=f"cite_{row_start+col_idx}"):
                citation = build_apa_citation(e, {})
                pyperclip.copy(citation)
                st.info("Citation copied")
            if ic3.button("🖨️", key=f"print_{row_start+col_idx}"):
                st.markdown(f'[Print view]({link})')
            if ic4.button("📂", key=f"arch_{row_start+col_idx}"):
                add_to_archive(link, ARCHIVE_PATH)
                st.info("Archived")

            # Card container end
            st.markdown('</div>', unsafe_allow_html=True)
