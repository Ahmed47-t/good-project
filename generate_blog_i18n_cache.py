#!/usr/bin/env python3
"""Generate static EN/FR/AR translations for blog content.
Uses the existing build_blog.py POSTS data and stores translations in blog_i18n_cache.json.
"""
import json, re, time, urllib.parse, urllib.request, pathlib, runpy
from bs4 import BeautifulSoup, NavigableString

ROOT = pathlib.Path(__file__).resolve().parent
CACHE_PATH = ROOT / "blog_i18n_cache.json"
TARGETS = ["en", "fr", "ar"]

# build_blog.py writes generated files when executed; harmless here and keeps POSTS source of truth.
ns = runpy.run_path(str(ROOT / "build_blog.py"))
POSTS = ns["POSTS"]

if CACHE_PATH.exists():
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
else:
    cache = {}

mem = cache.setdefault("_memory", {})

def translate_text(text: str, src: str, dst: str) -> str:
    if dst == src or not text or not text.strip():
        return text
    key = f"{src}>{dst}:{text}"
    if key in mem:
        return mem[key]
    # Skip pure symbols/numbers
    if not re.search(r"[A-Za-zÀ-ÿ\u0600-\u06FF]", text):
        mem[key] = text
        return text
    url = (
        "https://translate.googleapis.com/translate_a/single?client=gtx&dt=t"
        + "&sl=" + urllib.parse.quote(src)
        + "&tl=" + urllib.parse.quote(dst)
        + "&q=" + urllib.parse.quote(text)
    )
    for attempt in range(4):
        try:
            raw = urllib.request.urlopen(url, timeout=20).read().decode("utf-8")
            data = json.loads(raw)
            out = "".join(part[0] for part in data[0] if part and part[0])
            out = out.replace("BENRO", "BENRO").replace("Benro", "Benro")
            mem[key] = out
            # write progressively so we do not lose a long run
            CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(0.08)
            return out
        except Exception:
            if attempt == 3:
                mem[key] = text
                return text
            time.sleep(0.7 * (attempt + 1))

def translate_html_fragment(fragment: str, src: str, dst: str) -> str:
    if dst == src or not fragment:
        return fragment
    soup = BeautifulSoup(fragment, "html.parser")
    for node in list(soup.descendants):
        if isinstance(node, NavigableString):
            s = str(node)
            if s.strip():
                node.replace_with(translate_text(s, src, dst))
    return str(soup)

def block_html(kind, payload):
    import html as h
    if kind == "p": return f"<p>{payload}</p>"
    if kind in ("h2","h3","h4"): return f"<{kind}>{payload}</{kind}>"
    if kind == "ul": return "<ul>" + "".join(f"<li>{i}</li>" for i in payload) + "</ul>"
    if kind == "ol": return "<ol>" + "".join(f"<li>{i}</li>" for i in payload) + "</ol>"
    if kind == "hr": return "<hr/>"
    if kind == "img": return f'<img class="inline" src="{payload}" loading="lazy" alt=""/>'
    if kind == "note": return f'<div class="note">{payload}</div>'
    if kind == "table":
        thead = "".join(f"<th>{h.escape(x)}</th>" for x in payload["headers"])
        rows = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in payload["rows"])
        return '<div class="table-wrap"><div class="table-scroll">' + f'<table class="t"><thead><tr>{thead}</tr></thead><tbody>{rows}</tbody></table>' + '</div></div>'
    return ""

for idx, post in enumerate(POSTS, 1):
    slug = post["slug"]
    src = post.get("lang", "en")
    entry = cache.setdefault(slug, {})
    print(f"[{idx}/{len(POSTS)}] {slug} ({src})")
    for lang in TARGETS:
        lang_entry = entry.setdefault(lang, {})
        lang_entry["title"] = translate_html_fragment(post["title"], src, lang)
        lang_entry["excerpt"] = translate_text(post["excerpt"], src, lang)
        lang_entry["category"] = translate_text(post["category"], src, lang)
        lang_entry["date_label"] = translate_text(post["date_label"], src, lang)
        bodies = []
        for bi, (kind, payload) in enumerate(post["body"]):
            html_block = block_html(kind, payload)
            bodies.append(translate_html_fragment(html_block, src, lang))
        lang_entry["body"] = bodies
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

# Remove memory helper? Keep it for cheap future regeneration.
CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved", CACHE_PATH)
