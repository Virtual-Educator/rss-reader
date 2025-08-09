import os
from datetime import datetime
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup

import streamlit as st
import pyperclip

from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import (
    get_archived, is_archived, add_to_archive, remove_from_archive
)

# Page config and CSS
st.set_page_config(
    page_title="Personal News Reader",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
<style>
  /* Center content like a timeline */
  div.block-container { max-width: 1900px; margin-left:auto; margin-right:auto; }

  /* Links without underline */
  a { text-decoration: none !important; }

  /* Category column container */
  /**
  .cat-card {
    border: 1px solid #2f2f2f;
    border-radius: 16px;
    padding: 12px;
    background: transparent;
  }
  **/

  .cat-header {
    display:flex; align-items:center; justify-content:space-between;
    font-size:1.05rem; font-weight:700; margin: 4px 2px 8px 2px;
  }
  .cat-header a { color: inherit; }

  /* Item row: left text, right thumbnail */
  .news-row {
    display:grid;
    grid-template-columns: 1fr 96px;
    gap: 12px;
    align-items:start;
    padding: 8px 0;
  }
  .news-divider { height:1px; background:#2b2b2b; margin: 6px 0 4px 0; }

  .source-line { color:#9aa0a6; font-size:0.85rem; margin:0 0 2px 0; }
  .title a { color:inherit; font-weight:700; font-size:1.0rem; line-height:1.25; }
  .snippet { color:#e8eaed; font-size:0.93rem; margin-top:6px; }

  .thumb {
    width:96px; height:96px; object-fit:cover; border-radius:12px; background:#222;
  }

  /* Small icon row on the right end of the text block */
  .iconrow { display:flex; gap:8px; margin-top:6px; }
  .iconbtn {
    border:1px solid #3a3a3a; border-radius:10px;
    padding:2px 6px; font-size:14px; min-width:30px; min-height:30px;
    background:transparent; cursor:pointer;
  }
  .iconbtn:hover { background:#262626; }

  .topbar { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
</style>
""",
    unsafe_allow_html=True,
)

# Paths
BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")  # we will store objects here
CACHE_DIR = os.path.join(BASE_DIR, "cache")

# Load feeds and archived list
feeds = load_json(FEEDS_PATH, default=[])
archived_items = get_archived(ARCHIVE_PATH)  # list of dicts

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

def render_item(e: dict, idx_key: str, archived_view: bool = False):
    link = e.get("link", "#")
    title = e.get("title", "[No title]")

    # meta: date and author
    date_str = (
        e["published_parsed"].strftime("%Y-%m-%d")
        if e.get("published_parsed")
        else e.get("published", "")[:10]
    )
    src = domain_of(link)
    author = e.get("author")
    byline = f" • By {author}" if author else ""

    # thumbnail
    thumb = e.get("thumbnail") or first_img_from_summary(e.get("summary", "")) \
            or f"https://www.google.com/s2/favicons?sz=128&domain={src}"

    # snippet
    text = plain_text(e.get("summary", ""))
    length = e.get("snippet_length", 250) or 250
    snippet = text[:length] + ("..." if len(text) > length else "")

    # row with right-aligned thumbnail
    st.markdown('<div class="news-row">', unsafe_allow_html=True)
    st.markdown(f'<img class="thumb" src="{thumb}"/>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div>
          <div class="source-line">{src} • {date_str}{byline}</div>
          <div class="title"><a href="{link}" target="_blank">{title}</a></div>
          <div class="snippet">{snippet}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    st.markdown("</div>", unsafe_allow_html=True)

    # The only two actions you asked for
    c1, c2, _ = st.columns([1, 1, 10], gap="small")
    if c1.button("📋", key=f"cit_{idx_key}", help="Copy APA citation"):
        citation = build_apa_citation(e, {})
        pyperclip.copy(citation)
        st.info("Citation copied")
    if not archived_view:
        if c2.button("📂", key=f"arc_{idx_key}", help="Archive"):
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
        if c2.button("🗑", key=f"unarc_{idx_key}", help="Remove from archive"):
            remove_from_archive(link, ARCHIVE_PATH)
            st.info("Removed from archive")

# Simple router
view = st.query_params.get("view", "home")
cat_param = st.query_params.get("cat")

# Top bar
st.markdown('<div class="topbar">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 1, 1], gap="small")
if col1.button("Refresh"):
    st.rerun()
if col2.button("Home"):
    st.query_params.clear()
    st.rerun()
if col3.button("Archived"):
    st.query_params.update({"view": "arch"})
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

if view == "arch":
    st.header("Archived")
    items = archived_items
    if not items:
        st.write("No archived items yet.")
    else:
        # three columns of archived cards
        for start in range(0, len(items), 3):
            cols = st.columns(3, gap="large")
            for i, a in enumerate(items[start : start + 3]):
                with cols[i]:
                    render_item(a, f"arch_{start+i}", archived_view=True)
                    if i < 2 and (start + i) < len(items) - 1:
                        st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)
    st.stop()

# Home dashboard
with st.spinner("Loading articles…"):
    entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Deduplicate by link
seen = set()
deduped = []
for e in entries:
    link = e.get("link")
    if link and link not in seen:
        seen.add(link)
        deduped.append(e)

# Group by category and sort
by_cat = {}
for e in deduped:
    if is_archived(e.get("link", ""), archived_items):
        continue
    cat = e.get("source", "Other")
    by_cat.setdefault(cat, []).append(e)

for cat in by_cat:
    by_cat[cat].sort(key=lambda x: x.get("published_parsed") or datetime.min, reverse=True)

# Three category columns
cats = sorted(by_cat.keys())
cols = st.columns(3, gap="large")
for i, cat in enumerate(cats):
    col = cols[i % 3]
    with col:
        st.markdown('<div class="cat-card">', unsafe_allow_html=True)
        href = f"?view=cat&cat={quote(cat)}"
        st.markdown(f'<div class="cat-header"><a href="{href}">{cat} ›</a></div>', unsafe_allow_html=True)

        for idx, e in enumerate(by_cat[cat][:4]):
            render_item(e, f"{cat}_{idx}")
            if idx < min(3, len(by_cat[cat]) - 1):
                st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Category detail page
if view == "cat" and cat_param:
    st.header(cat_param)
    items = by_cat.get(cat_param, [])
    if not items:
        st.write("No stories found.")
    else:
        for idx, e in enumerate(items):
            render_item(e, f"cat_{idx}")
            if idx < len(items) - 1:
                st.markdown('<div class="news-divider"></div>', unsafe_allow_html=True)
