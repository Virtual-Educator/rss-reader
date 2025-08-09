import os
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qsl
import re

import streamlit as st
import pyperclip
from bs4 import BeautifulSoup

from utils.file_io import load_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

# Page config and CSS
st.set_page_config(page_title="Personal News Reader", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  /* Center content */
  div.block-container { max-width: 1200px; margin-left: auto; margin-right: auto; }

  /* Remove underline from links */
  a { text-decoration: none !important; }

  /* Category chips */
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0 16px 0; }
  .chip {
    padding: 6px 12px; border: 1px solid #555; border-radius: 999px;
    background: transparent; color: inherit; font-size: 0.95rem; cursor: pointer;
  }
  .chip.active { background: #444; }

  /* Cards */
  .card { border: 1px solid #444; border-radius: 10px; padding: 12px; background: transparent; }
  .thumb { width: 100%; height: 160px; object-fit: cover; border-radius: 8px; margin-bottom: 8px; }
  .title a { font-size: 1.05rem; font-weight: 700; color: inherit; }
  .meta { color: #8a8a8a; font-size: 0.85rem; margin: 4px 0 8px 0; }
  .snippet { font-size: 0.95rem; margin-bottom: 8px; min-height: 3.5em; }

  /* Smaller icon buttons */
  button[role="button"] {
    padding: 2px 6px !important; font-size: 16px !important;
    min-width: 30px !important; min-height: 30px !important;
  }

  /* Trim selectbox top margin used in some themes (not used now, but handy) */
  .stSelectbox label { display: none !important; }
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
def normalize_url(u: str) -> str:
    """Normalize URL to reduce duplicates across feeds."""
    try:
        parsed = urlparse(u)
        # strip tracking params
        qs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if not k.lower().startswith("utm_")]
        query = "&".join([f"{k}={v}" for k, v in qs]) if qs else ""
        # remove trailing slash and fragments
        path = parsed.path.rstrip("/")
        return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", query, ""))
    except Exception:
        return u

def domain_of(u: str) -> str:
    try:
        return urlparse(u).netloc
    except Exception:
        return ""

def first_img_from_summary(html: str) -> str | None:
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        img = soup.find("img")
        return img.get("src") if img else None
    except Exception:
        return None

def plain_text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)

def title_signature(t: str) -> str:
    t = re.sub(r"[^a-zA-Z0-9 ]+", " ", t or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t

# Fetch
with st.spinner("Loading articles…"):
    raw = fetch_and_parse_feeds(feeds, CACHE_DIR)

# Deduplicate across feeds
seen = set()
deduped = []
for e in raw:
    link = e.get("link", "")
    norm = normalize_url(link)
    sig = title_signature(e.get("title", "")) + "::" + norm
    if norm and sig not in seen:
        seen.add(sig)
        deduped.append(e)

# Build category list and search
categories = sorted({e.get("source", "Other") for e in deduped})
if "selected_cat" not in st.session_state:
    st.session_state.selected_cat = "All"
if "limit" not in st.session_state:
    st.session_state.limit = 30

# Top row controls
left, mid, right = st.columns([1, 3, 2], gap="small")
if left.button("Refresh"):
    st.rerun()
query = mid.text_input("Search headlines", value=st.session_state.get("q", ""))  # simple title search
st.session_state.q = query

# Category chips row
st.write("")  # small spacer
chip_html = ['<div class="chips">']
all_cats = ["All"] + categories
for c in all_cats:
    active = "active" if c == st.session_state.selected_cat else ""
    chip_html.append(f'<button class="chip {active}" onclick="window.parent.postMessage({{type:\'chip\',value:\'{c}\'}} , \'*\')">{c}</button>')
chip_html.append("</div>")
st.markdown("".join(chip_html), unsafe_allow_html=True)

# Capture chip clicks from JS
st.components.v1.html("""
<script>
  window.addEventListener("message", (e) => {
    if (e.data && e.data.type === "chip") {
      const cat = e.data.value;
      const streamlitSet = window.parent.streamlitAPI ? window.parent.streamlitAPI.setComponentValue : null;
      if (streamlitSet) { streamlitSet(cat); }
      else { window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:setComponentValue", value: cat}, "*"); }
    }
  });
</script>
""", height=0)

# Simple workaround to read the chip value
chip_value = st.session_state.get("chip_value")
if chip_value:
    st.session_state.selected_cat = chip_value

# Filter
filtered = []
q = (query or "").strip().lower()
for e in deduped:
    if is_archived(e.get("link", ""), archived):
        continue
    if st.session_state.selected_cat != "All" and e.get("source") != st.session_state.selected_cat:
        continue
    if q and q not in (e.get("title", "").lower()):
        continue
    filtered.append(e)

# Sort by recency
filtered.sort(key=lambda x: x.get("published_parsed") or datetime.min, reverse=True)

# Limit and grid
items = filtered[: st.session_state.limit]

# Render in rows of three cards
for start in range(0, len(items), 3):
    cols = st.columns(3, gap="small")
    for i, e in enumerate(items[start:start + 3]):
        with cols[i]:
            link = e.get("link", "#")
            title = e.get("title", "[No title]")

            # Meta
            date_str = e["published_parsed"].strftime("%Y-%m-%d") if e.get("published_parsed") else e.get("published", "")[:10]
            src_domain = domain_of(link)

            # Thumbnail: prefer entry.thumbnail if your fetcher sets it, else first img in summary, else favicon
            thumb = e.get("thumbnail") or first_img_from_summary(e.get("summary", "")) or f"https://www.google.com/s2/favicons?sz=128&domain={src_domain}"

            # Snippet
            text = plain_text(e.get("summary", ""))
            length = e.get("snippet_length", 250) or 250
            snippet = text[:length] + ("..." if len(text) > length else "")

            # Card
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if thumb:
                st.markdown(f'<img class="thumb" src="{thumb}" />', unsafe_allow_html=True)
            st.markdown(f'<div class="title"><a href="{link}" target="_blank">{title}</a></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta">{src_domain} • {date_str}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="snippet">{snippet}</div>', unsafe_allow_html=True)

            # Icon row
            b1, b2, b3, b4 = st.columns(4, gap="small")
            if b1.button("🔗", key=f"lnk_{start+i}"):
                pyperclip.copy(link)
                st.info("Link copied")
            if b2.button("📋", key=f"cit_{start+i}"):
                cit = build_apa_citation(e, {})
                pyperclip.copy(cit)
                st.info("Citation copied")
            if b3.button("🖨️", key=f"prt_{start+i}"):
                st.markdown(f"[Print view]({link})")
            if b4.button("📂", key=f"arc_{start+i}"):
                add_to_archive(link, ARCHIVE_PATH)
                st.info("Archived")

            st.markdown("</div>", unsafe_allow_html=True)

# Load more
if len(filtered) > st.session_state.limit:
    if st.button("Load more"):
        st.session_state.limit += 30
        st.rerun()
