import streamlit as st
import feedparser
import pyperclip
import os
from datetime import datetime
from utils.file_io import load_json, save_json
from utils.rss import fetch_and_parse_feeds
from utils.citation import build_apa_citation
from utils.archive import is_archived, add_to_archive

BASE_DIR = os.path.dirname(__file__)
FEEDS_PATH = os.path.join(BASE_DIR, "feeds.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
AUTHORS_PATH = os.path.join(BASE_DIR, "authors.json")
ARCHIVE_PATH = os.path.join(BASE_DIR, "read_articles.json")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

feeds = load_json(FEEDS_PATH, default=[])
settings = load_json(SETTINGS_PATH, default={
    "show_archived": False,
    "sort_order": "newest_first",
    "filters": {"include_keywords": [], "exclude_keywords": []}
})
authors = load_json(AUTHORS_PATH, default={})
archived = load_json(ARCHIVE_PATH, default=[])

st.set_page_config(page_title="Personal RSS Reader", layout="wide")

## Sidebar: controls
st.sidebar.title("Settings")

if st.sidebar.button("Refresh Feeds"):
    st.spinner("Fetching latest articles...")
    st.rerun()

show_arch = st.sidebar.checkbox(
    "Show Archived", settings.get("show_archived", False)
)
sort_order = st.sidebar.selectbox(
    "Sort Order", ["newest_first", "oldest_first"],
    index=0
)

include_text = ",".join(settings["filters"]["include_keywords"])
exclude_text = ",".join(settings["filters"]["exclude_keywords"])

include = st.sidebar.text_input(
    "Include keywords (comma-separated)", value=include_text
)
exclude = st.sidebar.text_input(
    "Exclude keywords (comma-separated)", value=exclude_text
)

settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
settings["filters"]["include_keywords"] = [
    k.strip() for k in include.split(",") if k.strip()
]
settings["filters"]["exclude_keywords"] = [
    k.strip() for k in exclude.split(",") if k.strip()
]
save_json(SETTINGS_PATH, settings)

## Manage RSS Feeds
with st.sidebar.expander("Manage RSS Feeds"):
    st.write(feeds)

    new_url = st.text_input("New RSS URL")
    new_cat = st.text_input("Category")

    if st.button("Add Feed") and new_url:
        if any(f["url"] == new_url for f in feeds):
            st.warning("Feed URL already exists")
        else:
            feeds.append({"url": new_url, "category": new_cat or "Uncategorized"})
            save_json(FEEDS_PATH, feeds)
            st.success("Feed added")
            st.rerun()

    st.markdown("#### Bulk add feeds")
    bulk = st.text_area(
        "Paste one URL per line, or 'URL,Category'", height=150
    )
    if st.button("Import Bulk") and bulk:
        lines = [l.strip() for l in bulk.splitlines() if l.strip()]
        added = 0
        for line in lines:
            if "," in line:
                url, cat = line.split(",", 1)
            else:
                url, cat = line, "Uncategorized"
            url = url.strip()
            cat = cat.strip()
            if any(f["url"] == url for f in feeds):
                continue
            feeds.append({"url": url, "category": cat or "Uncategorized"})
            added += 1
        save_json(FEEDS_PATH, feeds)
        st.success(f"Imported {added} new feeds")
        st.rerun()

## Main view
st.title("Personal News Reader")

with st.spinner("Loading articles..."):
    entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

filtered = []
incs = [k.lower() for k in settings["filters"]["include_keywords"]]
excs = [k.lower() for k in settings["filters"]["exclude_keywords"]]

for e in entries:
    if not show_arch and is_archived(e["link"], archived):
        continue
    text = (e.get("title", "") + " " + e.get("summary", "")).lower()
    if any(k in text for k in excs):
        continue
    if incs and not any(k in text for k in incs):
        continue
    filtered.append(e)

filtered.sort(
    key=lambda x: x.get("published_parsed") or datetime.min,
    reverse=(sort_order == "newest_first")
)

for entry in filtered:
    st.subheader(entry.get("title"))
    st.write(f"Source: {entry.get('source')}  |  Published: {entry.get('published')}")
    cols = st.columns(3)
    if cols[0].button("Copy Link", key=entry["link"]):
        pyperclip.copy(entry["link"])
        st.success("Link copied")
    if cols[1].button("Copy APA Citation", key=entry["link"] + "-cite"):
        cit = build_apa_citation(entry, authors)
        pyperclip.copy(cit)
        st.success("Citation copied")
    if cols[2].button("Archive", key=entry["link"] + "-arch"):
        add_to_archive(entry["link"], ARCHIVE_PATH)
        st.success("Article archived")
    st.markdown(f"[Print view]({entry.get('link')})")

st.write("Powered by your local RSS reader.")
