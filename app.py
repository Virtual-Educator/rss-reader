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

# ─── Page Config & Global CSS ────────────────────────────────────────────────
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  /* Center container and set max width */
  div.block-container {
    max-width: 1200px;
    margin-left: auto;
    margin-right: auto;
  }
  /* Remove link underlines */
  a { text-decoration: none !important; }
  /* Card container (transparent to remove white bar) */
  .card {
    border: 1px solid #444;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 16px;
    background-color: transparent !important;
  }
  /* Thumbnail */
  .card-thumb {
    width: 100%;
    height: auto;
    border-radius: 4px;
    margin-bottom: 8px;
  }
  /* Title styling */
  .card-title a {
    font-size: 1.1rem;
    font-weight: bold;
    color: inherit;
  }
  /* Meta line */
  .card-meta {
    color: #888;
    font-size: 0.85rem;
    margin: 4px 0 8px 0;
  }
  /* Snippet */
  .card-snippet {
    font-size: 0.95rem;
    margin-bottom: 8px;
  }
  /* Make icon buttons smaller */
  button[role="button"] {
    padding: 4px 6px !important;
    font-size: 18px !important;
    min-width: 32px !important;
    min-height: 32px !important;
  }
</style>
""", unsafe_allow_html=True)

# ─── File Paths & Load JSON ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

feeds = load_json(FEEDS_PATH, default=[])
archived = load_json(ARCHIVE_PATH, default=[])

# ─── Fetch & Deduplicate ──────────────────────────────────────────────────────
with st.spinner("Loading articles…"):
    raw_entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

seen = set()
entries = []
for e in raw_entries:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        entries.append(e)

# ─── Top Controls ─────────────────────────────────────────────────────────────
col_refresh, col_cat = st.columns([1, 4], gap="small")
if col_refresh.button("🔄 Refresh"):
    st.rerun()

categories = sorted({e["source"] for e in entries})
selected_cat = col_cat.selectbox("Category", ["All"] + categories)

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

# ─── Render Cards (Three per row) ─────────────────────────────────────────────
for start in range(0, len(filtered), 3):
    cols = st.columns(3, gap="small")
    for i, e in enumerate(filtered[start:start+3]):
        with cols[i]:
            link = e.get("link", "#")
            title = e.get("title", "[No title]")
            domain = urlparse(link).netloc
            if e.get("published_parsed"):
                date_str = e["published_parsed"].strftime("%Y-%m-%d")
            else:
                date_str = e.get("published", "")[:10]

            # Extract thumbnail if present
            thumb = None
            soup = BeautifulSoup(e.get("summary", ""), "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                thumb = img["src"]

            # Snippet text
            text = soup.get_text()
            length = e.get("snippet_length", 250) or 250
            snippet = text[:length] + ("..." if len(text) > length else "")

            # Card HTML
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if thumb:
                st.markdown(f'<img src="{thumb}" class="card-thumb"/>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-title"><a href="{link}">{title}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-meta">{domain} • {date_str}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card-snippet">{snippet}</div>', unsafe_allow_html=True)

            # Icon buttons
            b1, b2, b3, b4 = st.columns(4, gap="small")
            if b1.button("🔗", key=f"lnk_{start+i}"):
                pyperclip.copy(link)
                st.info("Link copied")
            if b2.button("📋", key=f"cite_{start+i}"):
                cit = build_apa_citation(e, {})
                pyperclip.copy(cit)
                st.info("Citation copied")
            if b3.button("🖨️", key=f"prt_{start+i}"):
                st.markdown(f'<a href="{link}" target="_blank">Print view</a>', unsafe_allow_html=True)
            if b4.button("📂", key=f"arc_{start+i}"):
                add_to_archive(link, ARCHIVE_PATH)
                st.info("Archived")

            st.markdown('</div>', unsafe_allow_html=True)
