#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tech Frontier Monitor — constructor de feeds.json
Corre en GitHub Actions cada 30 min. Lee la configuración de fuentes
directamente desde index.html (una sola fuente de verdad), descarga
todo en paralelo y escribe feeds.json para que la página cargue al instante.
Solo usa la librería estándar de Python.
"""
import concurrent.futures as cf
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
TIMEOUT = 20
MAX_ITEMS = 15
NITTERS = ["https://xcancel.com", "https://nitter.net", "https://lightbrd.com",
           "https://nitter.space", "https://nitter.poast.org", "https://nitter.privacydev.net"]


# ---------- utilidades ----------
def http_get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-zA-Z#0-9]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def local(tag):
    return tag.split("}")[-1].lower()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    from email.utils import parsedate_to_datetime
    try:
        return int(parsedate_to_datetime(s).timestamp() * 1000)
    except Exception:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", s)
    if m:
        import calendar
        y, mo, d, h, mi, se = map(int, m.groups())
        return int(calendar.timegm((y, mo, d, h, mi, se)) * 1000)
    return None


def parse_feed_xml(xml_text, limit=MAX_ITEMS):
    """Devuelve items [{title, link, desc, date, author, vid}] de RSS o Atom."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8", errors="replace"))
    except ET.ParseError:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", xml_text)
        try:
            root = ET.fromstring(cleaned.encode("utf-8", errors="replace"))
        except ET.ParseError:
            return []
    items = []
    nodes = [el for el in root.iter() if local(el.tag) in ("item", "entry")]
    for n in nodes[:limit]:
        title = link = desc = author = vid = ""
        date = None
        for c in n.iter():
            t = local(c.tag)
            txt = (c.text or "").strip()
            if t == "title" and not title:
                title = strip_html(txt)
            elif t == "link" and not link:
                link = txt or c.attrib.get("href", "")
            elif t in ("description", "summary", "encoded", "content") and len(desc) < 50:
                d = strip_html(txt)
                if len(d) > len(desc):
                    desc = d
            elif t in ("pubdate", "published", "updated", "date") and not date:
                date = parse_date(txt)
            elif t == "name" and not author:
                author = strip_html(txt)
            elif t == "videoid":
                vid = txt
        if not title or not (link or vid):
            continue
        items.append({
            "title": title[:300],
            "link": link,
            "desc": desc[:600],
            "date": date or int(time.time() * 1000),
            "author": author,
            "vid": vid,
        })
    return items


# ---------- leer configuración desde index.html ----------
def read_config(html):
    def block(name):
        m = re.search(r"const %s = \[(.*?)\n\];" % name, html, re.S)
        return m.group(1) if m else ""

    feeds = []
    for m in re.finditer(r"\{name:'([^']*)',\s*url:'([^']*)',\s*region:'([^']*)',\s*panel:'([^']*)',\s*w:([\d.]+)\}", block("FEEDS")):
        feeds.append({"name": m.group(1), "url": m.group(2), "region": m.group(3),
                      "panel": m.group(4), "w": float(m.group(5))})

    xaccounts = []
    for m in re.finditer(r"\{name:'((?:[^'\\]|\\.)*)',\s*handle:'([^']*)'\}", block("XACCOUNTS")):
        name = m.group(1).encode().decode("unicode_escape")
        xaccounts.append({"name": name, "handle": m.group(2)})

    ytchannels = []
    for m in re.finditer(r"\{name:'((?:[^'\\]|\\.)*)',\s*(handle|id|playlist):'([^']*)'(,\s*strict:true)?\}", block("YTCHANNELS")):
        name = m.group(1).encode().decode("unicode_escape")
        ch = {"name": name, m.group(2): m.group(3)}
        if m.group(4):
            ch["strict"] = True
        ytchannels.append(ch)

    return feeds, xaccounts, ytchannels


# ---------- clasificador de temas (espejo simplificado de la página) ----------
TOPIC_PATTERNS = [
    r"chip|semiconductor|tsmc|asml|smic|euv|nvidia|gpu|wafer|lithograph|silicon|transistor|foundr",
    r"\bai\b|artificial intelligence|inteligencia artificial|llm|openai|anthropic|deepmind|deepseek|machine learning|neural|agentic|frontier model",
    r"quantum|qubit|entanglement",
    r"robot|humanoid|automation|autonomous|drone",
    r"energy|energ|nuclear|solar|battery|batteries|fusion|reactor|wind power|hydrogen|renewabl|grid|geotherm|photovolta|smr\b",
    r"uranium|fission|tokamak|thorium|enrichment",
    r"\bev\b|\bevs\b|electric vehicle|electric car|tesla|byd|nio|xpeng|li auto|zeekr|rivian|robotaxi|self-driving|lidar|gigafactory|charging",
    r"rare earth|lithium|cobalt|gallium|germanium|graphite|nickel|critical mineral|mining|magnet|neodymium|tungsten|polysilicon",
    r"5g|6g|telecom|huawei|zte|ericsson|nokia|spectrum|broadband|undersea cable|submarine cable|fiber optic|starlink|satellite internet",
    r"export control|sanction|tariff|chips act|ai act|antitrust|regulation|blacklist|entity list|trade war|decoupl|de-risk|subsid|industrial policy",
    r"biotech|drug|cancer|gene|genom|crispr|vaccine|clinical trial|\bfda\b|protein|pharma|medicine|medical|obesity|alzheimer|mrna",
    r"space|rocket|satellite|nasa|spacex|orbit|lunar|mars|starship|\besa\b|astronaut",
    r"military|defen[cs]e|pentagon|\bpla\b|missile|weapon|army|navy|air force|warfare|nato|darpa|hypersonic|carrier|submarine|deterrence",
    r"infrastructure|rail|railway|port|construction|highway|bridge|data center|datacenter|manufactur|factory|factories|supply chain|shipyard|housing|transmission",
    r"physics|physicist|quantum|mathemat|telescope|particle|superconduct|breakthrough|nobel|dark matter|black hole|genome|evolution|neuroscience|paleontolog|archaeolog|fossil|astronom|chemist|biolog",
    r"china|chinese|beijing|shanghai|shenzhen|huawei|byd|alibaba|tencent|baidu|xiaomi|taiwan|xi jinping",
]
TOPIC_RE = [re.compile(p, re.I) for p in TOPIC_PATTERNS]

def on_topic(title):
    return any(rx.search(title or "") for rx in TOPIC_RE)


# ---------- fetchers ----------
def fetch_rss(feed):
    try:
        xml = http_get(feed["url"])
        items = parse_feed_xml(xml)
        if not items:
            return feed, None
        for i in items:
            i.pop("author", None); i.pop("vid", None)
        return feed, items
    except Exception:
        return feed, None


def fetch_x(acc):
    for inst in NITTERS:
        try:
            xml = http_get(f"{inst}/{acc['handle']}/rss", timeout=12)
            if "<rss" not in xml:
                continue
            items = parse_feed_xml(xml, limit=8)
            out = []
            for i in items:
                link = i["link"]
                m = re.search(r"(/[^/]+/status/\d+)", link)
                if m:
                    link = "https://x.com" + m.group(1)
                out.append({"title": i["title"][:360], "link": link, "date": i["date"]})
            if out:
                return acc, out
        except Exception:
            continue
    return acc, None


def resolve_yt_id(handle, cache):
    if handle in cache:
        return cache[handle]
    try:
        page = http_get(f"https://www.youtube.com/@{handle}", timeout=15)
        m = re.search(r'"channelId":"(UC[0-9A-Za-z_-]{22})"', page) or \
            re.search(r'channel/(UC[0-9A-Za-z_-]{22})', page)
        if m:
            cache[handle] = m.group(1)
            return m.group(1)
    except Exception:
        pass
    return None


def fetch_yt(ch, id_cache):
    try:
        if "playlist" in ch:
            url = "https://www.youtube.com/feeds/videos.xml?playlist_id=" + ch["playlist"]
        else:
            cid = ch.get("id") or resolve_yt_id(ch["handle"], id_cache)
            if not cid:
                return ch, None
            url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + cid
        xml = http_get(url, timeout=15)
        items = parse_feed_xml(xml, limit=8)
        out = []
        for i in items:
            if not i["vid"]:
                m = re.search(r"v=([\w-]{11})", i["link"])
                i["vid"] = m.group(1) if m else ""
            if not i["vid"]:
                continue
            if ch.get("strict") and not on_topic(i["title"]):
                continue
            entry = {"title": i["title"], "vid": i["vid"], "date": i["date"]}
            if "playlist" in ch and i["author"]:
                entry["author"] = i["author"]
            out.append(entry)
        return ch, (out or None)
    except Exception:
        return ch, None


# ---------- main ----------
def main():
    html = open("index.html", encoding="utf-8").read()
    feeds, xaccounts, ytchannels = read_config(html)
    print(f"Config: {len(feeds)} feeds RSS, {len(xaccounts)} cuentas X, {len(ytchannels)} canales YT")

    yt_ids = {}
    if os.path.exists("yt_ids.json"):
        try:
            yt_ids = json.load(open("yt_ids.json", encoding="utf-8"))
        except Exception:
            yt_ids = {}

    out = {"generated_at": int(time.time() * 1000), "rss": [], "x": [], "yt": [],
           "fails": {"rss": [], "x": [], "yt": []}}

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for feed, items in ex.map(fetch_rss, feeds):
            if items:
                out["rss"].append({"feed": {k: feed[k] for k in ("name", "region", "panel", "w")}, "items": items})
            else:
                out["fails"]["rss"].append(feed["name"])

        for acc, items in ex.map(fetch_x, xaccounts):
            if items:
                out["x"].append({"name": acc["name"], "handle": acc["handle"], "items": items})
            else:
                out["fails"]["x"].append(acc["handle"])

    # YouTube en serie ligera (la resolución de IDs comparte cache)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for ch, items in ex.map(lambda c: fetch_yt(c, yt_ids), ytchannels):
            if items:
                out["yt"].append({"name": ch["name"], "items": items})
            else:
                out["fails"]["yt"].append(ch.get("handle") or ch.get("playlist") or ch["name"])

    json.dump(yt_ids, open("yt_ids.json", "w", encoding="utf-8"))
    json.dump(out, open("feeds.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    ok = len(out["rss"]) + len(out["x"]) + len(out["yt"])
    fail = sum(len(v) for v in out["fails"].values())
    print(f"feeds.json escrito: {ok} fuentes ok, {fail} sin señal")


if __name__ == "__main__":
    main()
