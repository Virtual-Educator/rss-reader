
import os
import re
import json
import time
import html
import datetime as dt
from urllib.parse import urlparse

import streamlit as st

try:
    import feedparser  # type: ignore
except Exception:
    feedparser = None

APP_TITLE = "Newsboard RSS"
ARCHIVE_PATH = "archive.json"

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="📰")

# Show version so you can confirm the right file is loaded
APP_VERSION = "v3-streamlit-primitives"
st.caption(f"Loaded {APP_VERSION} · {__file__}")

# -----------------------------
# Utilities
# -----------------------------

def _get_query_params():
    # Works with recent and older Streamlit
    try:
        return st.query_params.to_dict()
    except Exception:
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}

def _set_query_params(**kwargs):
    try:
        st.query_params.clear()
        for k, v in kwargs.items():
            st.query_params[k] = v
    except Exception:
        st.experimental_set_query_params(**kwargs)

def site_name_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        if not netloc:
            return ""
        parts = [p for p in netloc.split(".") if p not in {"www", "m"}]
        if not parts:
            return netloc.title()
        return parts[-2].replace("-", " ").title() if len(parts) >= 2 else parts[-1].replace("-", " ").title()
    except Exception:
        return ""

def human_time_ago(dt_obj):
    if not dt_obj:
        return ""
    now = dt.datetime.now(dt.timezone.utc)
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    delta = now - dt_obj
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = months // 12
    return f"{years} year{'s' if years != 1 else ''} ago"

def try_parse_datetime(entry):
    fields = ["published_parsed", "updated_parsed", "created_parsed"]
    for f in fields:
        tm_struct = entry.get(f)
        if tm_struct:
            try:
                return dt.datetime.fromtimestamp(time.mktime(tm_struct), tz=dt.timezone.utc)
            except Exception:
                pass
    return None

def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_image(entry):
    for key in ("media_content", "media_thumbnail"):
        media = entry.get(key)
        if isinstance(media, list) and media:
            url = media[0].get("url")
            if url and url.lower().startswith("http"):
                return url
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href")
    summary = entry.get("summary") or entry.get("description") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None

def google_favicon(url: str) -> str:
    try:
        domain = urlparse(url).netloc
        if not domain:
            return ""
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    except Exception:
        return ""

def format_author_for_apa(name: str) -> str:
    name = name.strip().replace(",", "")
    parts = [p for p in name.split() if p]
    if not parts:
        return ""
    last = parts[-1]
    initials = [p[0].upper() + "." for p in parts[:-1] if p]
    if initials:
        return f"{last}, {' '.join(initials)}"
    return last

def make_apa_citation(item: dict) -> str:
    authors = item.get("authors", [])
    author_field = ""
    if authors:
        names = [format_author_for_apa(a) for a in authors if a]
        if len(names) == 1:
            author_field = names[0]
        elif len(names) == 2:
            author_field = f"{names[0]} & {names[1]}"
        elif len(names) > 2:
            author_field = ", ".join(names[:-1]) + f", & {names[-1]}"
    else:
        author_field = item.get("site", "")
    pub_dt = item.get("published_dt")
    if pub_dt:
        month_name = pub_dt.strftime("%B")
        date_str = f"{pub_dt.year}, {month_name} {pub_dt.day}"
    else:
        date_str = dt.datetime.now().strftime("%Y")
    title = item.get("title", "").strip()
    site = item.get("site", "").strip()
    url = item.get("link", "").strip()
    if title:
        title = title[:1].upper() + title[1:]
    return f"{author_field} ({date_str}). {title}. {site}. {url}"

def load_archive():
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_archive(items):
    try:
        with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_to_archive(item):
    items = load_archive()
    if not any(x.get("link") == item.get("link") for x in items):
        items.insert(0, item)
        save_archive(items)

def remove_from_archive(link: str):
    items = [x for x in load_archive() if x.get("link") != link]
    save_archive(items)

def parse_feed(url: str, limit: int | None = None):
    if feedparser is None:
        st.error("Python package 'feedparser' is required. Install it with: pip install feedparser")
        return []
    try:
        fp = feedparser.parse(url)
    except Exception as e:
        st.warning(f"Could not parse feed: {url}. {e}")
        return []

    items = []
    for entry in fp.entries:
        link = entry.get("link") or ""
        title = html.unescape(entry.get("title", "")).strip()
        summary = entry.get("summary") or entry.get("description") or ""
        summary = strip_html(summary)
        if len(summary) > 250:
            summary = summary[:250].rstrip() + "…"
        img = extract_image(entry)
        published_dt = try_parse_datetime(entry)
        site = site_name_from_url(link) or site_name_from_url(url) or (fp.feed.get("title") if fp and fp.feed else "")
        authors = []
        if "authors" in entry and isinstance(entry["authors"], list):
            for a in entry["authors"]:
                name = a.get("name") if isinstance(a, dict) else str(a)
                if name:
                    authors.append(name)
        elif entry.get("author"):
            authors = [entry.get("author")]
        items.append({
            "title": title,
            "summary": summary,
            "link": link,
            "image": img,
            "published_dt": published_dt,
            "published_human": human_time_ago(published_dt) if published_dt else "",
            "site": site,
            "favicon": google_favicon(link),
            "authors": authors,
        })
        if limit and len(items) >= limit:
            break
    return items

def ensure_default_config():
    default_feeds = {
        "Health": [
            "https://www.statnews.com/feed/",
            "https://www.medicalnewstoday.com/rss",
            "https://www.sciencedaily.com/rss/health_medicine.xml",
        ],
        "Gaming": [
            "https://www.gamespot.com/feeds/mashup/",
            "https://www.eurogamer.net/feed/news",
            "https://www.pcgamer.com/rss/",
        ],
        "Higher education": [
            "https://www.highereddive.com/feeds/news/",
            "https://hechingerreport.org/feed/",
            "https://www.insidehighered.com/rss/news",
        ],
        "World News": [
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.npr.org/1004/rss.xml",
            "https://www.theguardian.com/world/rss",
        ],
        "AI in Higher Education": [
            "https://hechingerreport.org/special_reports/artificial-intelligence/feed/",
            "https://www.edsurge.com/arc/feeds/articles.rss",
            "https://er.educause.edu/rss",
        ],
        "AI in Business": [
            "https://venturebeat.com/category/ai/feed/",
            "https://techcrunch.com/tag/artificial-intelligence/feed/",
            "https://www.technologyreview.com/feed/",
            "https://www.theverge.com/ai-artificial-intelligence/rss",
        ],
    }
    if "feeds" not in st.session_state:
        st.session_state["feeds"] = default_feeds
    else:
        for k, v in default_feeds.items():
            if k not in st.session_state["feeds"] or not isinstance(st.session_state["feeds"][k], list):
                st.session_state["feeds"][k] = v
    if "per_column" not in st.session_state:
        st.session_state["per_column"] = 5

ensure_default_config()

# -----------------------------
# Styles
# -----------------------------

st.markdown(
    '''
    <style>
    /* Make st.button look like small icon buttons */
    .stButton > button {
        border: none !important;
        background: transparent !important;
        padding: 4px 6px !important;
        font-size: 1.1rem !important;
        box-shadow: none !important;
        min-height: auto !important;
        min-width: auto !important;
        line-height: 1 !important;
    }
    .stButton > button:hover { background: rgba(255,255,255,0.07) !important; }
    .chip a { text-decoration: none; }
    </style>
    ''',
    unsafe_allow_html=True,
)

# -----------------------------
# Sidebar controls
# -----------------------------

with st.sidebar:
    st.header("Settings")
    per_col = st.slider("Stories per column", 3, 10, st.session_state["per_column"])
    st.session_state["per_column"] = per_col

    st.caption("Edit feeds below. One feed per line.")

    for cat in ["Health", "Gaming", "Higher education", "World News", "AI in Higher Education", "AI in Business"]:
        with st.expander(f"{cat} feeds"):
            txt = st.text_area(cat, "\n".join(st.session_state["feeds"].get(cat, [])), height=120, key=f"{cat}_feeds")
            st.session_state["feeds"][cat] = [l.strip() for l in txt.splitlines() if l.strip()]

    st.caption("Archive data is stored in archive.json located next to the app.py file.")

# -----------------------------
# Data loading helpers
# -----------------------------

@st.cache_data(ttl=300, show_spinner=False)
def load_category_items(category: str, per_feed: int = 20):
    items = []
    for url in st.session_state["feeds"].get(category, []):
        items.extend(parse_feed(url, limit=per_feed))
    items.sort(key=lambda x: x.get("published_dt") or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
    return items

# -----------------------------
# Card renderer
# -----------------------------

def render_card(item: dict, key_prefix: str):
    # Two-column card: text left, image right
    with st.container():
        left, right = st.columns([1.0, 0.36], gap="medium")
        with left:
            title = item.get("title", "")
            link = item.get("link", "")
            summary = item.get("summary", "")
            st.markdown(f"[{title}]({link})")
            if summary:
                st.write(summary)
        with right:
            img = item.get("image")
            if img:
                st.image(img, use_column_width=True)

        # Actions area bottom-right
        spacer, colA, colB = st.columns([0.75, 0.125, 0.125])
        with colA:
            if st.button("📑", key=f"apa_{key_prefix}", help="APA citation"):
                st.session_state[f"show_apa_{key_prefix}"] = not st.session_state.get(f"show_apa_{key_prefix}", False)
        with colB:
            if st.button("📥", key=f"arc_{key_prefix}", help="Save to archive"):
                add_to_archive(item)
                st.toast("Saved to archive", icon="✅")

        if st.session_state.get(f"show_apa_{key_prefix}"):
            st.code(make_apa_citation(item))

        # Meta row
        fav = item.get("favicon")
        site = item.get("site", "")
        time_h = item.get("published_human", "")
        m1, m2, m3 = st.columns([0.05, 0.65, 0.30])
        with m1:
            if fav:
                st.image(fav, width=16)
        with m2:
            st.caption(site)
        with m3:
            st.caption(time_h)

# -----------------------------
# Category views
# -----------------------------

def render_category_column(category: str, max_items: int):
    st.subheader(category)
    items = load_category_items(category)
    if not items:
        st.info("No items found. Add feeds in the sidebar.")
        return
    for i, item in enumerate(items[:max_items]):
        render_card(item, key_prefix=f"{category}_{i}")
    st.markdown(f"[More]({f'?view=category&name={category}'})")

def render_category_page(category: str):
    st.subheader(category)
    items = load_category_items(category)
    if not items:
        st.info("No items found. Add feeds in the sidebar.")
        return
    for i, item in enumerate(items):
        render_card(item, key_prefix=f"{category}_full_{i}")

def render_archive_page():
    st.subheader("Archived")
    items = load_archive()
    if not items:
        st.info("Nothing here yet. Use the Archive icon on any card.")
        return
    if st.button("Clear all"):
        save_archive([])
        st.experimental_rerun()
    for i, item in enumerate(items):
        render_card(item, key_prefix=f"arch_{i}")
        col1, _, _ = st.columns([0.2, 0.4, 0.4])
        with col1:
            if st.button("🗑️ Remove", key=f"rm_{i}"):
                remove_from_archive(item.get("link", ""))
                st.experimental_rerun()

# -----------------------------
# Header and nav
# -----------------------------

st.title(APP_TITLE)

params = _get_query_params()
view = params.get("view", "home")
name = params.get("name", "")

chips = [
    ("All", "?view=home"),
    ("Health", "?view=category&name=Health"),
    ("Gaming", "?view=category&name=Gaming"),
    ("Higher education", "?view=category&name=Higher education"),
    ("World News", "?view=category&name=World News"),
    ("AI in Higher Education", "?view=category&name=AI in Higher Education"),
    ("AI in Business", "?view=category&name=AI in Business"),
    ("Archived", "?view=archive"),
]
ccols = st.columns(len(chips))
for idx, (label, href) in enumerate(chips):
    with ccols[idx]:
        st.markdown(f"[{label}]({href})")

# -----------------------------
# Main view routing
# -----------------------------

if view == "home":
    c1, c2, c3 = st.columns(3, gap="large")
    cats = ["Health", "Gaming", "Higher education"]
    for idx, cat in enumerate(cats):
        with (c1, c2, c3)[idx]:
            render_category_column(cat, st.session_state["per_column"])
elif view == "category" and name in st.session_state["feeds"]:
    render_category_page(name)
elif view == "archive":
    render_archive_page()
else:
    st.info("Pick a category from the navigation.")
