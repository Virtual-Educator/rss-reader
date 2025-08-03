from dateutil import parser

def build_apa_citation(entry, author_overrides):
    author = entry.get("author") or author_overrides.get(entry.get("source")) or "[Author]"
    try:
        date = parser.parse(entry.get("published")).strftime("%Y, %B %d")
    except Exception:
        date = "[n.d.]"
    title = entry.get("title", "[No title]")
    source = entry.get("source", "[Source]")
    url = entry.get("link")
    return f"{author}. ({date}). {title}. {source}. {url}"
