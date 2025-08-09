import os
from datetime import datetime
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup

import streamlit as st
import pyperclip

from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# Page config and CSS
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  /* Center app like a timeline */
  div.block-container { max-width: 1200px; margin-left:auto; margin-right:auto; }

  /* Links: no underline */
  a { text-decoration: none !important; }

  /* Category column container (card) */
  .cat-card {
    border: 1px solid #444;
    border-radius: 16px;
    padding: 14px 14px 6px 14px;
    background: transparent;
  }

  /* Category header */
  .cat-header {
    display:flex; align-items:center; justify-content:space-between;
    font-size:1.1rem; font-weight:700; margin-bottom:8px;
  }
  .cat-header a { color: inherit; }

  /* News row */
  .news-row {
    display:grid; grid-template-columns: 1fr 84px; gap: 12px; align-items:start;
    padding: 10px 0;
  }
  .news-divider { height:1px; background:#333; margin: 6px 0 4px 0; }

  /* Source line and title */
  .source-line { color:#9aa0a6; font-size:0.9rem; margin-bottom:2px; }
  .title a { color:inherit; font-weight:700; font-size:1.0rem; }

  /* Snippet */
  .snippet { color:#e8eaed; font-size:0.95rem; margin-top:6px; }

  /* Thumbnail */
  .thumb {
    width: 84px; height: 84px; object-fit: cover; border-radius: 12px;
    background:#222;
  }

  /* Tiny icon bar like GN actions */
  .iconbar { display:flex; gap:8px; margin-top:8px; }
  .iconbtn {
    border:1px solid #444; border-radius:8px; padding:4px 6px; font-size:16px;
    background:transparent; cursor:pointer;
  }
  .iconbtn:hover { background:#2a2a2a; }

  /* Back link area */
  .topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

# Paths and data
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

feeds = load_json(FEEDS_PATH, default=[])
archived = load_json(ARCHIVE_PATH, default=[])

# Helpers
def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""

def first_img_from_summary(summary_html: str) -> str | None:
    if not summary_html:
        return None
    soup = BeautifulSoup(summary_html, "html.parser")
    tag = soup.find("img")
    return tag.get("src") if tag and tag.get("src") else None

def plain_text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)

def render_item(e: dict, idx_key: str):
    link = e.get("link", "#")
    title = e.get("title", "[No title]")
    date_str = e["published_parsed"].strftime("%Y-%m-%d") if e.get("published_parsed") else e.get("published", "")[:10]
    src = domain_of(link)
    thumb = first_img_from_summary(e.get("summary", "")) or f"https://www.google.com/s2/favicons?sz=128&domain={src}"
    text = plain_text(e.get("summary", ""))
    length = e.get("snippet_length", 250) or 250
    snippet = text[:length] + ("..." if len(text) > length else "")

    st.markdown('<div class="news-row">', unsafe_allow_html=True)
    # Left block: source, title, snippet, icons
    st.markdown(
        f"""
        <div>
          <div class="source-line">{src} • {date_str}</div>
          <div class="title"><a href="{link}" target="_blank">{title}</a></div>
          <div class="snippet">{snippet}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Right block: thumbnail
    st.markdown(f'<img class="thumb" src="{thumb}"/>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Tiny action icons like GN (link, cite, print, archive)
    c1, c2, c3, c4, _ = st.columns([1,1,1,1,10], gap="small")
    if c1.button("🔗", key=f"lnk_{idx_key}", help="Copy link"):
        pyperclip.copy(link)
        st.info("Link copied")
    if c2.button("📋", key=f"cit_{idx_key}", help="Copy citation"):
        cit = build_apa_citation(e, {})
        pyperclip.copy(cit)
        st.info("Citation copied")
    if c3.button("🖨️", key=f"prt_{idx_key}", help="Print view"):
        st.markdown(f"[Open article]({link})")
    if c4.button("📂", key=f"arc_{idx_key}", help="Archive"):
        add_to_archive(link, ARCHIVE_PATH)
        st.info("Archived")

# Fetch feeds
with st.spinner("Loading articles…"):
    entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Dedupe by link
seen = set()
deduped = []
for e in entries:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        deduped.append(e)

# Group by category
by_cat = {}
for e in deduped:
    cat = e.get("source", "Other")
    if is_archived(e.get("link", ""), archived):
        continue
    by_cat.setdefault(cat, []).append(e)

# Sort each category by recency
for cat in by_cat:
    by_cat[cat].sort(key=lambda x: x.get("published_parsed") or datetime.min, reverse=True)

# Router
view = st.query_params.get("view", "home")
cat_param = st.query_params.get("cat")

# Top bar
left, right = st.columns([1,5], gap="small")
if left.button("Refresh"):
    st.rerun()
if right.button("Home"):
    st.query_params.clear()
    st.rerun()

if view == "cat" and cat_param:
    # Category detail page
    cat = cat_param
    st.markdown(f'<div class="topbar"><h2>{cat}</h2></div>', unsafe_allow_html=True)

    items = by_cat.get(cat, [])
    for idx, e in enumerate(items):
        render_item(e, f"cat_{idx}")
        if idx < len(items) - 1:
            st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)

else:
    # Home dashboard: three columns of categories
    cats = sorted(by_cat.keys())
    # Show up to 9 categories on the first screen; adjust if you want more
    cols = st.columns(3, gap="large")
    for i, cat in enumerate(cats):
        col = cols[i % 3]
        with col:
            st.markdown('<div class="cat-card">', unsafe_allow_html=True)
            # Category header with chevron; clicking navigates to category page
            href = f"?view=cat&cat={quote(cat)}"
            st.markdown(
                f'<div class="cat-header"><a href="{href}">{cat} ›</a></div>',
                unsafe_allow_html=True
            )
            # Render top 4 stories in this category
            for idx, e in enumerate(by_cat[cat][:4]):
                render_item(e, f"{cat}_{idx}")
                if idx < min(3, len(by_cat[cat]) - 1):
                    st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
