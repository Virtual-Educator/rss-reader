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

st.sidebar.title("Settings")
if st.sidebar.button("Refresh Feeds"):
    st.experimental_rerun()

show_arch = st.sidebar.checkbox("Show Archived", settings.get("show_archived", False))
sort_order = st.sidebar.selectbox("Sort Order", ["newest_first", "oldest_first"], index=0)
settings["show_archived"] = show_arch
settings["sort_order"] = sort_order
save_json(SETTINGS_PATH, settings)

with st.sidebar.expander("Manage RSS Feeds"):
    st.write(feeds)
    new_url = st.text_input("New RSS URL")
    new_cat = st.text_input("Category")
    if st.button("Add Feed") and new_url:
        feeds.append({"url": new_url, "category": new_cat or "Uncategorized"})
        save_json(FEEDS_PATH, feeds)
        st.experimental_rerun()

st.title("Personal News Reader")

entries = fetch_and_parse_feeds(feeds, CACHE_DIR)

filtered = []
for e in entries:
    if not show_arch and is_archived(e["link"], archived):
        continue
    title = e.get("title", "")
    inc = settings["filters"]["include_keywords"]
    exc = settings["filters"]["exclude_keywords"]
    if any(k.lower() in title.lower() for k in exc):
        continue
    filtered.append(e)

filtered.sort(
    key=lambda x: x.get("published_parsed", datetime.min),
    reverse=(sort_order == "newest_first")
)

for entry in filtered:
    st.subheader(entry.get("title"))
    st.write(f"Source: {entry.get('source')} | Published: {entry.get('published')}")
    cols = st.columns(3)
    if cols[0].button("Copy Link", key=entry.get("link")):
        pyperclip.copy(entry.get("link"))
        st.success("Link copied to clipboard")
    if cols[1].button("Copy APA Citation", key=entry.get("link") + "cite"):
        citation = build_apa_citation(entry, authors)
        pyperclip.copy(citation)
        st.success("APA citation copied")
    if cols[2].button("Archive", key=entry.get("link") + "arch"):
        add_to_archive(entry.get("link"), ARCHIVE_PATH)
        st.success("Article archived")
    st.markdown(f"[Print view]({entry.get('link')})")

st.write("Powered by your local RSS reader.")
