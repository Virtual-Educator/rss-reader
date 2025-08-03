import json
import os
import hashlib

def _hash_link(link):
    return hashlib.sha256(link.encode("utf-8")).hexdigest()

def is_archived(link, archived_list):
    return _hash_link(link) in archived_list

def add_to_archive(link, path):
    archived = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            archived = json.load(f)
    h = _hash_link(link)
    if h not in archived:
        archived.append(h)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(archived, f, indent=2)
