import json
import os
import hashlib

def _hash_link(link: str) -> str:
    return hashlib.sha256((link or "").encode("utf-8")).hexdigest()

def _load_raw(path: str):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_archived(path: str):
    """
    Returns a list of archived article dicts:
    {link, title, published, author, source, summary, thumbnail}
    If the file contains old hashed strings, they are ignored here.
    """
    raw = _load_raw(path)
    if not raw:
        return []
    # if old format (list of hashes/strings), we cannot reconstruct details
    if raw and isinstance(raw[0], str):
        return []
    return raw

def is_archived(link: str, archived_items: list):
    """
    True if link is present in archived items or in legacy hashed list.
    """
    # check dict format
    if archived_items and isinstance(archived_items[0], dict):
        return any(a.get("link") == link for a in archived_items)
    # legacy compatibility: read file again and check hashes
    # (this path used only if caller passed the dict list but file is legacy)
    return False

def add_to_archive(entry: dict, path: str):
    """
    Append entry if not already present. Entry should include:
    link, title, published, author, source, summary, thumbnail
    """
    data = _load_raw(path)
    # legacy file: convert to object list on first write
    if data and isinstance(data[0], str):
        data = []

    if not any(e.get("link") == entry.get("link") for e in data):
        data.append(entry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

def remove_from_archive(link: str, path: str):
    data = _load_raw(path)
    if not data:
        return
    if isinstance(data[0], str):
        # legacy hashes; remove by hash
        h = _hash_link(link)
        data = [x for x in data if x != h]
    else:
        data = [e for e in data if e.get("link") != link]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
