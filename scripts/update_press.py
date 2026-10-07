#!/usr/bin/env python3
"""Collect public article metadata; publish only links, dates and source names."""
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "sports-infos": ("Sports Infos", "https://www.ski-nordique.net/ski-alpin.87570.fr.html"),
    "ski-chrono": ("Ski Chrono", "https://www.ledauphine.com/skichrono/ski-alpin"),
}

def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)).replace("’", "'")

def relevant(title):
    text = normalize(title)
    if any(word in text for word in ("biathlon", "ski de fond", "snowboard", "freestyle", "ski de bosses", "ski-alpinisme", "combiné nordique", "combine nordique")):
        return False
    return bool(re.search(r"coupe d['’ -]?europe|championnat[s]? de france|ski chrono samse|samse tour|courses? fis.*france|fis france", text))

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.meta, self.ld = [], {}, []
        self.anchor, self.script = None, None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.anchor = [attrs.get("href", ""), attrs.get("title", "")]
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", ""))] = attrs.get("content", "")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.script = ""
    def handle_data(self, text):
        if self.anchor is not None:
            self.anchor[1] += " " + text
        if self.script is not None:
            self.script += text
    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            self.links.append((self.anchor[0], " ".join(self.anchor[1].split())))
            self.anchor = None
        if tag == "script" and self.script is not None:
            try:
                self.ld.append(json.loads(self.script))
            except ValueError:
                pass
            self.script = None

def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)

def fetch(url):
    request = Request(url, headers={"User-Agent": "Infos-FIS-Press/1.0 (+https://infos-fis.fr/presse/)"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")

def article_url(source, url):
    if source == "ski-chrono":
        return bool(re.match(r"https://www\.ledauphine\.com/skichrono/\d{4}/\d{2}/\d{2}/", url))
    return bool(re.match(r"https://www\.ski-nordique\.net/[^/]+\.\d+-87570\.html$", url))

def metadata(text, fallback):
    page = Page(text)
    nodes = [node for ld in page.ld for node in objects(ld)]
    # Respect publishers' explicit paid-access metadata.
    if any(node.get("isAccessibleForFree") in (False, "false", "False") for node in nodes):
        return None
    articles = [n for n in nodes if any("Article" in str(t) for t in (n.get("@type", []) if isinstance(n.get("@type"), list) else [n.get("@type", "")]))]
    node = articles[0] if articles else {}
    title = node.get("headline") or page.meta.get("og:title") or fallback
    date = node.get("datePublished") or page.meta.get("article:published_time")
    if not date or not re.match(r"\d{4}-\d{2}-\d{2}", str(date)):
        return None
    return str(title).strip(), str(date)[:10]

def cards(articles):
    output = []
    for item in sorted(articles, key=lambda a: a["date"], reverse=True)[:24]:
        esc = html.escape
        if item["source"] == "sports-infos":
            logo = '<img class="press-sports-logo" src="/images/sports-infos-logo.svg" width="180" height="32" alt="Sports Infos — ski-nordique.net">'
        else:
            logo = '<svg class="press-source-logo" xmlns="http://www.w3.org/2000/svg" viewBox="1195 37 124 63" width="59" height="30" role="img" aria-label="Ski Chrono"><title>Ski Chrono</title><image href="/images/bandeau infosFIS.png?v=6" width="1536" height="242"/></svg>'
        date = dt.date.fromisoformat(item["date"]).strftime("%d/%m/%Y")
        output.append(f'<a class="card misc external press-article" href="{esc(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">\n<span class="press-source">{logo}<span class="press-circuit">{esc(item["circuit"])}</span></span>\n<strong>{esc(item["title"])}</strong>\n<span class="press-meta">{SOURCES[item["source"]][0]} · <time datetime="{item["date"]}">{date}</time></span>\n</a>')
    return "\n".join(output)

def run():
    data_path = ROOT / "assets/press-articles.json"
    articles = json.loads(data_path.read_text())["articles"]
    known = {a["url"] for a in articles}
    cutoff = dt.date.today() - dt.timedelta(days=90)
    successful, errors = 0, []
    for source, (_, listing) in SOURCES.items():
        try:
            page = Page(fetch(listing))
            if not page.links:
                raise ValueError("listing has no links")
            candidates = {}
            for url, title in page.links:
                if url.startswith("/"):
                    url = listing.split("/", 3)[0] + "//" + listing.split("/")[2] + url
                url = url.split("?")[0].split("#")[0]
                if article_url(source, url) and relevant(title) and url not in known:
                    candidates.setdefault(url, title)
            successful += 1
            for url, title in list(candidates.items())[:30]:
                try:
                    result = metadata(fetch(url), title)
                    if not result:
                        continue
                    title, date = result
                    if not relevant(title) or dt.date.fromisoformat(date) < cutoff or dt.date.fromisoformat(date) > dt.date.today():
                        continue
                    circuit = "Coupe d’Europe" if "europe" in normalize(title) else ("Championnats de France" if "championnat" in normalize(title) else "FIS France · Samse Tour")
                    articles.append(dict(url=url, title=title, date=date, source=source, circuit=circuit))
                    known.add(url)
                    print("Added:", source, date, title)
                except Exception as error:
                    errors.append(f"{url}: {error}")
        except Exception as error:
            errors.append(f"{source}: {error}")
    for error in errors:
        print("WARNING:", error)
    if not successful:
        raise RuntimeError("All sources failed; existing selection preserved")
    articles.sort(key=lambda a: (a["date"], a["url"]), reverse=True)
    data_path.write_text(json.dumps({"articles": articles}, ensure_ascii=False, indent=2) + "\n")
    path = ROOT / "presse/index.html"
    page = path.read_text()
    start, end = "<!-- PRESS-ARTICLES:START -->", "<!-- PRESS-ARTICLES:END -->"
    if page.count(start) != 1 or page.count(end) != 1:
        raise RuntimeError("Missing article markers")
    updated = page.split(start)[0] + start + "\n" + cards(articles) + "\n" + end + page.split(end)[1]
    path.write_text(updated)

if __name__ == "__main__":
    run()
