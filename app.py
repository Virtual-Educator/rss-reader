
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


def _get_query_params():
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
    citation = f"{author_field} ({date_str}). {title}. {site}. {url}"
    return citation

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

def remove_from_archive(link: str) -> None:
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
        # Merge in any missing categories without overwriting existing ones
        for k, v in default_feeds.items():
            if k not in st.session_state["feeds"] or not isinstance(st.session_state["feeds"][k], list):
                st.session_state["feeds"][k] = v
    if "per_column" not in st.session_state:
        st.session_state["per_column"] = 5


ensure_default_config()

st.markdown(
    """

    <style>
    :root {
        --card-bg: rgba(255,255,255,0.04);
        --card-border: rgba(255,255,255,0.08);
        --muted: rgba(255,255,255,0.6);
    }
    .page-title { font-size: 1.6rem; margin: 0 0 8px 0; }
    .topnav { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
    .navlink, .navlink:visited {
        color: inherit; text-decoration: none; padding: 6px 10px;
        border-radius: 999px; border: 1px solid var(--card-border); background: var(--card-bg);
        font-size: 0.95rem;
    }
    .navlink.active { border-color: rgba(99,102,241,0.6); box-shadow: 0 0 0 2px rgba(99,102,241,0.25) inset; }
    a.card-title, a.card-title:visited { color: inherit; text-decoration: none; }
    .card {
        border: 1px solid var(--card-border);
        background: var(--card-bg);
        border-radius: 16px;
        padding: 14px 16px;
        margin: 10px 0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.10);
    }
    .card-row {
        display: grid;
        grid-template-columns: 1fr minmax(90px, 110px);
        gap: 14px;
        align-items: center;
    }
    .meta { font-size: 0.87rem; color: var(--muted); display:flex; align-items:center; gap:8px; }
    .meta img { border-radius: 6px; }
    .thumb {
        width: 110px; height: 110px; object-fit: cover; border-radius: 12px; border: 1px solid var(--card-border);
        justify-self: end;
    }
    .actions {
        display: flex; gap: 8px; margin-top: 8px; align-items:center; justify-content: flex-end;
    }
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
    .stButton > button:hover {
        background: rgba(255,255,255,0.07) !important;
    }
    </style>
    """,

    unsafe_allow_html=True,

)


with st.sidebar:

    st.header("Settings")

    per_col = st.slider("Stories per column", 3, 10, st.session_state["per_column"]) 

    st.session_state["per_column"] = per_col



    st.caption("Edit feeds below. One feed per line.")



    with st.expander("Health feeds"):

        txt = st.text_area("Health", "\n".join(st.session_state["feeds"]["Health"]), height=120, key="health_feeds")

        st.session_state["feeds"]["Health"] = [l.strip() for l in txt.splitlines() if l.strip()]



    with st.expander("Gaming feeds"):

        txt = st.text_area("Gaming", "\n".join(st.session_state["feeds"]["Gaming"]), height=120, key="gaming_feeds")

        st.session_state["feeds"]["Gaming"] = [l.strip() for l in txt.splitlines() if l.strip()]



    with st.expander("Higher education feeds"):

        txt = st.text_area("Higher education", "\n".join(st.session_state["feeds"].get("Higher education", [])), height=120, key="highered_feeds")

        st.session_state["feeds"]["Higher education"] = [l.strip() for l in txt.splitlines() if l.strip()]



    with st.expander("World News feeds"):

        txt = st.text_area("World News", "\n".join(st.session_state["feeds"].get("World News", [])), height=120, key="world_feeds")

        st.session_state["feeds"]["World News"] = [l.strip() for l in txt.splitlines() if l.strip()]



    with st.expander("AI in Higher Education feeds"):

        txt = st.text_area("AI in Higher Education", "\n".join(st.session_state["feeds"].get("AI in Higher Education", [])), height=120, key="ai_he_feeds")

        st.session_state["feeds"]["AI in Higher Education"] = [l.strip() for l in txt.splitlines() if l.strip()]



    with st.expander("AI in Business feeds"):

        txt = st.text_area("AI in Business", "\n".join(st.session_state["feeds"].get("AI in Business", [])), height=120, key="ai_biz_feeds")

        st.session_state["feeds"]["AI in Business"] = [l.strip() for l in txt.splitlines() if l.strip()]



    st.caption("Archive data is stored in archive.json located next to the app.py file.")



@st.cache_data(ttl=300, show_spinner=False)

def load_category_items(category: str, per_feed: int = 20):

    items = []

    feeds = st.session_state["feeds"].get(category, [])

    for url in feeds:

        items.extend(parse_feed(url, limit=per_feed))

    items.sort(key=lambda x: x.get("published_dt") or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)

    return items



def render_card(item: dict, key_prefix: str):

    title = item.get("title", "")

    link = item.get("link", "")

    summary = item.get("summary", "")

    site = item.get("site", "")

    time_h = item.get("published_human", "")

    favicon = item.get("favicon", "")

    img = item.get("image")



    st.markdown('<div class="card">', unsafe_allow_html=True)

    st.markdown('<div class="card-row">', unsafe_allow_html=True)



    st.markdown(f"""

        <div>

            <a class="card-title" href="{html.escape(link)}" target="_blank">

                <div style="font-size:1.05rem; font-weight:600; line-height:1.3;">{html.escape(title)}</div>

            </a>

            <div style="margin-top:6px; font-size:0.95rem;">{html.escape(summary)}</div>

            <div class=\"actions\"> 

    """, unsafe_allow_html=True)



    spacer, colA, colB = st.columns([0.8, 0.1, 0.1])

    with colA:

        if st.button("📑", key=f"apa_{key_prefix}", help="APA citation"):

            st.session_state[f"show_apa_{key_prefix}"] = not st.session_state.get(f"show_apa_{key_prefix}", False)

    with colB:

        if st.button("📥", key=f"arc_{key_prefix}", help="Save to archive"):

            add_to_archive(item)

            st.toast("Saved to archive", icon="✅")



    if st.session_state.get(f"show_apa_{key_prefix}"):

        citation = make_apa_citation(item)

        st.code(citation)



    st.markdown('</div>', unsafe_allow_html=True)  # .actions

    st.markdown('</div>', unsafe_allow_html=True)  # left cell



    if img:

        st.markdown(f'<img class="thumb" src="{html.escape(img)}" alt="" loading="lazy">', unsafe_allow_html=True)

    else:

        st.markdown('<div></div>', unsafe_allow_html=True)



    st.markdown('</div>', unsafe_allow_html=True)  # .card-row



    meta_html = f'''

        <div class="meta">

            {'<img src="'+html.escape(favicon)+'" width="16" height="16">' if favicon else ''}

            <span>{html.escape(site)}</span>

            <span>•</span>

            <span>{html.escape(time_h)}</span>

        </div>

    '''

    st.markdown(meta_html, unsafe_allow_html=True)



    st.markdown('</div>', unsafe_allow_html=True)  # .card



def render_category_column(category: str, max_items: int):

    st.markdown(f'<div class="category-title">{html.escape(category)}</div>', unsafe_allow_html=True)

    items = load_category_items(category)

    if not items:

        st.info("No items found. Add feeds in the sidebar.")

        return

    for i, item in enumerate(items[:max_items]):

        render_card(item, key_prefix=f"{category}_{i}")



    st.markdown(f'<a class="more-link" href="?view=category&name={category}">More</a>', unsafe_allow_html=True)



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

        with st.container():

            render_card(item, key_prefix=f"arch_{i}")

            col1, col2, _ = st.columns([0.2, 0.2, 0.6])

            with col1:

                if st.button("🗑️ Remove", key=f"rm_{i}"):

                    remove_from_archive(item.get("link", ""))

                    st.experimental_rerun()



st.markdown(f'<div class="page-title">{APP_TITLE}</div>', unsafe_allow_html=True)



params = _get_query_params()

view = params.get("view", ["home"] if isinstance(params.get("view"), list) else params.get("view")) or "home"

if isinstance(view, list):

    view = view[0]



name = params.get("name", [""] if isinstance(params.get("name"), list) else params.get("name")) or ""

if isinstance(name, list):

    name = name[0]



nav = st.container()

with nav:

    st.markdown('<div class="topnav">', unsafe_allow_html=True)

    home_class = "navlink active" if view == "home" else "navlink"

    st.markdown(f'<a class="{home_class}" href="?view=home">All</a>', unsafe_allow_html=True)

    for cat in st.session_state["feeds"].keys():

        cls = "navlink active" if (view == "category" and name == cat) else "navlink"

        st.markdown(f'<a class="{cls}" href="?view=category&name={cat}">{html.escape(cat)}</a>', unsafe_allow_html=True)

    arc_cls = "navlink active" if view == "archive" else "navlink"

    st.markdown(f'<a class="{arc_cls}" href="?view=archive">Archived</a>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)



if view == "home":

    cols = st.columns(3, gap="large")

    cats = list(st.session_state["feeds"].keys())

    if len(cats) < 3:

        while len(cats) < 3:

            cats.append("")

    for idx in range(3):

        with cols[idx]:

            cat = cats[idx]

            if cat:

                render_category_column(cat, st.session_state["per_column"])

            else:

                st.write("")

elif view == "category" and name in st.session_state["feeds"]:

    render_category_page(name)

elif view == "archive":

    render_archive_page()

else:

    st.info("Pick a category from the navigation.")

