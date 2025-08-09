import os
from datetime import datetime
from urllib.parse import urlparse, quote

import streamlit as st
import pyperclip
from bs4 import BeautifulSoup

from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import get_archived, is_archived, add_to_archive, remove_from_archive

# Page config and CSS
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
<style>
  /* centered content */
  div.block-container { max-width: 1900px; margin-left: auto; margin-right: auto; }

  /* links without underline */
  a { text-decoration: none !important; }

  /* category panel */

  .cat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 1.05rem;
    font-weight: 700;
    margin: 4px 2px 8px 2px;
  }
  .cat-header a { color: inherit; }



  /* top line inside card */
  .gn-header { display: flex; align-items: center; justify-content: space-between; }
  .gn-meta { color: #9aa0a6; font-size: 0.85rem; }

  /* small icon buttons in header, top-right */
  .gn-actions { display: flex; gap: 8px; }
  .gn-actions button[role="button"] {
    font-size: 10px !important;
  }

  /* content row: text left, thumbnail right */
  .gn-row {
    display: grid;
    grid-template-columns: 1fr 200px;
    gap: 14px;
    align-items: start;
    margin-top: 8px;
  }
  .gn-title a { color: inherit; font-weight: 700; font-size: 1.05rem; line-height: 1.25; }
  .gn-snippet { color: #e8eaed; font-size: 0.95rem; margin-top: 6px; }

  .gn-thumb {
    width: 200px;
    height: 120px;
    object-fit: cover;
    border-radius: 14px;
    background: #222;
  }

  .news-divider { height: 1px; background: #2b2b2b; margin: 6px 0 4px 0; }

  .topbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
</style>
""",
    unsafe_allow_html=True,
)

# Paths
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Load configuration and archive
feeds = load_json(FEEDS_PATH, default=[])
archived_items = get_archived(ARCHIVE_PATH)  # list of dicts or empty

def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""

def plain_text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)

def thumbnail_for(entry: dict) -> str:
    thumb = entry.get("thumbnail")
    if not thumb:
        soup = BeautifulSoup(entry.get("summary", ""), "html.parser")
        img = soup.find("img")
        if img and img.get("src"):
            thumb = img["src"]
    if not thumb:
        thumb = f"https://www.google.com/s2/favicons?sz=128&domain={domain_of(entry.get('link',''))}"
    return thumb

def render_item(entry: dict, idx_key: str, archived_view: bool = False):
    link = entry.get("link", "#")
    title = entry.get("title", "[No title]")
    date_str = entry["published_parsed"].strftime("%Y-%m-%d") if entry.get("published_parsed") else entry.get("published", "")[:10]
    src = domain_of(link)
    author = entry.get("author")
    byline = f" • By {author}" if author else ""
    text = plain_text(entry.get("summary", ""))
    length = entry.get("snippet_length", 250) or 250
    snippet = text[:length] + ("..." if len(text) > length else "")
    thumb = thumbnail_for(entry)

    # Card wrapper
    st.markdown('<div class="gn-card">', unsafe_allow_html=True)

    # Header with meta on left and two icons on right
    col_meta, col_icons = st.columns([8, 2], gap="small")
    with col_meta:
        st.markdown(f'<div class="gn-header"><div class="gn-meta">{src} • {date_str}{byline}</div></div>', unsafe_allow_html=True)
    with col_icons:
        st.markdown('<div class="gn-actions">', unsafe_allow_html=True)
        b1, b2 = st.columns([1, 1], gap="small")
        if b1.button("📋", key=f"cit_{idx_key}", help="Copy APA citation"):
            citation = build_apa_citation(entry, {})
            pyperclip.copy(citation)
            st.info("Citation copied")
        if not archived_view:
            if b2.button("📂", key=f"arc_{idx_key}", help="Archive"):
                add_to_archive(
                    {
                        "link": link,
                        "title": title,
                        "published": date_str,
                        "author": author,
                        "source": src,
                        "summary": text,
                        "thumbnail": thumb,
                    },
                    ARCHIVE_PATH,
                )
                st.info("Archived")
        else:
            if b2.button("🗑", key=f"unarc_{idx_key}", help="Remove from archive"):
                remove_from_archive(link, ARCHIVE_PATH)
                st.info("Removed from archive")
        st.markdown("</div>", unsafe_allow_html=True)

    # Content row
    st.markdown('<div class="gn-row">', unsafe_allow_html=True)
    with st.container():
        st.markdown(f'<div class="gn-title"><a href="{link}" target="_blank">{title}</a></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="gn-snippet">{snippet}</div>', unsafe_allow_html=True)
    st.markdown(f'<img class="gn-thumb" src="{thumb}" />', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# Router
view = st.query_params.get("view", "home")
cat_param = st.query_params.get("cat")

# Top bar
st.markdown('<div class="topbar">', unsafe_allow_html=True)
tb1, tb2, tb3 = st.columns([1, 1, 1], gap="small")
if tb1.button("Refresh"):
    st.rerun()
if tb2.button("Home"):
    st.query_params.clear()
    st.rerun()
if tb3.button("Archived"):
    st.query_params.update({"view": "arch"})
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# Archived page
if view == "arch":
    st.header("Archived")
    items = archived_items
    if not items:
        st.write("No archived items yet.")
        st.stop()
    for start in range(0, len(items), 3):
        cols = st.columns(3, gap="large")
        for i, a in enumerate(items[start:start + 3]):
            with cols[i]:
                render_item(a, f"arch_{start+i}", archived_view=True)
                if i < 2 and (start + i) < len(items) - 1:
                    st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)
    st.stop()

# Fetch current stories for home and category pages
with st.spinner("Loading articles…"):
    entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Deduplicate by link
seen_links = set()
deduped = []
for e in entries:
    link = e.get("link")
    if link and link not in seen_links:
        seen_links.add(link)
        deduped.append(e)

# Group by category and sort by recency
by_cat = {}
for e in deduped:
    if is_archived(e.get("link", ""), archived_items):
        continue
    cat = e.get("source", "Other")
    by_cat.setdefault(cat, []).append(e)
for cat in by_cat:
    by_cat[cat].sort(key=lambda x: x.get("published_parsed") or datetime.min, reverse=True)

# Category page
if view == "cat" and cat_param:
    st.header(cat_param)
    items = by_cat.get(cat_param, [])
    if not items:
        st.write("No stories found.")
        st.stop()
    for idx, e in enumerate(items):
        render_item(e, f"cat_{idx}")
        if idx < len(items) - 1:
            st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)
    st.stop()

# Home dashboard with three category columns
cats = sorted(by_cat.keys())
cols = st.columns(3, gap="large")
for i, cat in enumerate(cats):
    column = cols[i % 3]
    with column:
        st.markdown('<div class="cat-card">', unsafe_allow_html=True)
        href = f"?view=cat&cat={quote(cat)}"
        st.markdown(f'<div class="cat-header"><a href="{href}">{cat} ›</a></div>', unsafe_allow_html=True)

        for idx, e in enumerate(by_cat[cat][:4]):
            render_item(e, f"{cat}_{idx}")
            if idx < min(3, len(by_cat[cat]) - 1):
                st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
