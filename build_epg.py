"""Build one guide (guide.xml.gz) for every channel in combined.m3u.
Order: existing ids (free + Xtream guides) -> fill from epgshare01 by call sign / name -> placeholder blocks.
Rewrites combined.m3u with stable ids (ch0001...) that match the guide."""
import re, gzip, io, urllib.parse, collections, datetime as dt
import xml.etree.ElementTree as ET
exec(open("xtream_groups.py", encoding="utf-8").read().split("rows = []")[0])
from build_final_norm import norm

E = "https://epgshare01.online/epgshare01/epg_ripper_"
FILL = [E + "US2.xml.gz", E + "US_LOCALS1.xml.gz", E + "US_SPORTS1.xml.gz", E + "PEACOCK1.xml.gz",
        E + "FANDUEL1.xml.gz", E + "PLEX1.xml.gz", E + "DISTROTV1.xml.gz", E + "VN1.xml.gz", E + "TBNPLUS1.xml.gz",
        "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_guide.xml.gz",
        "https://raw.githubusercontent.com/acidjesuz/EPGTalk/master/US_local_guide.xml.gz"]
import json as _json
for folder in ("Usa", "Sports", "Vietnam"):   # globetvapp daily guides (file list discovered via GitHub API)
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/globetvapp/epg/contents/{folder}", headers={"User-Agent": "x"})
        for f in _json.loads(urllib.request.urlopen(req, timeout=60).read()):
            if f["name"].endswith((".xml", ".xml.gz")):
                FILL.append(f["download_url"])
    except Exception as e:
        print("globetv list failed", folder, type(e).__name__)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = r.read()
    return gzip.decompress(d) if d[:2] == b"\x1f\x8b" else d

# --- playlist ---
chans, lines, cur = [], [], None
for l in open("combined.m3u", encoding="utf-8"):
    l = l.rstrip("\n")
    if l.startswith("#EXTINF"):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', l)); cur = a
    elif l and not l.startswith("#") and cur is not None:
        chans.append({"a": cur, "name": cur.get("tvg-name", ""), "group": cur.get("group-title", ""),
                      "tid": cur.get("tvg-id", ""), "url": l,
                      "id": "c" + __import__("hashlib").sha1((cur.get("group-title", "") + "|" + norm(cur.get("tvg-name", ""))).encode()).hexdigest()[:10],
                      "src": None})
        cur = None
want_tid = {c["tid"] for c in chans if c["tid"]}
callsign = lambda n: (re.search(r"\(([KW][A-Z]{2,4})\)", n.upper()) or [None, None])[1]
need_name = {}  # norm/callsign -> channel (filled later)

NOW = dt.datetime.now(dt.timezone.utc)
START, END = NOW - dt.timedelta(hours=3), NOW + dt.timedelta(days=4)
def in_window(p):
    try:
        s = dt.datetime.strptime(p.get("start")[:20].strip(), "%Y%m%d%H%M%S %z")
        e = dt.datetime.strptime(p.get("stop")[:20].strip(), "%Y%m%d%H%M%S %z")
        return e > START and s < END
    except Exception:
        return True

progs = collections.defaultdict(list)   # our id -> [programme elements]
def scan(data, idmap, label, name_match=False):
    """idmap: source channel id -> our id. If name_match, map new ids by display-name/call sign."""
    got = 0
    for ev, el in ET.iterparse(io.BytesIO(data), events=("end",)):
        if el.tag == "channel" and name_match:
            sid = el.get("id")
            names = [d.text or "" for d in el.findall("display-name")] + [re.sub(r"\.[a-z]{2}$", "", sid or "")]
            for n in names:
                c = None
                for cs in re.findall(r"\b([KW][A-Z]{2,3})(?:-?(?:DT|TV|HD|LD|CD))?\b", n.upper()):
                    c = c or need_name.get(("cs", cs))
                c = c or need_name.get(("n", norm(n)))
                if c and c["src"] is None:
                    idmap[sid] = c["id"]; c["src"] = label
                    break
            el.clear()
        elif el.tag == "programme":
            oid = idmap.get(el.get("channel"))
            if oid and in_window(el):
                el.set("channel", oid); progs[oid].append(el); got += 1
            else:
                el.clear()
    print(f"  {label}: {got} programmes")

print("loading primary guides...")
byid = collections.defaultdict(list)
for c in chans:
    if c["tid"]:
        byid[c["tid"]].append(c)
primary = {}
for tid, cs in byid.items():
    primary[tid] = cs[0]["id"]
scan(gzip.decompress(open("merged.xml.gz", "rb").read()), primary, "free guides")
scan(fetch(f"{server}/xmltv.php?" + urllib.parse.urlencode({"username": user, "password": pw})), primary, "xtream guide")
for c in chans:
    if progs.get(c["id"]):
        c["src"] = "primary"

missing = [c for c in chans if c["src"] is None and c["group"] != "Adult"]
print("missing after primary:", len(missing))
for c in missing:
    cs = callsign(c["name"])
    if cs:
        need_name.setdefault(("cs", cs), c)
    k = norm(re.sub(r"^(NFL|NBA|MLB|NHL|NCAA|VIETNAM)\s*[:|]?\s*", "", c["name"], flags=re.I))
    if k:
        need_name.setdefault(("n", k), c)
cache = {}
for url in FILL:
    label = url.rsplit("/", 1)[-1].replace("epg_ripper_", "").replace(".xml.gz", "").replace(".xml", "")
    try:
        cache[label] = fetch(url)
        scan(cache[label], {}, label, name_match=True)
    except Exception as e:
        print(f"  {label}: failed ({type(e).__name__})")

# fuzzy pass for national/cable channels still missing (names like "NBC GOLF CHANNEL HD" vs "Golf Channel")
import difflib
SKIP = re.compile(r"on-demand|originals|series \d|sereis|premiere \d|event|\bvs\b|@|play kidz|nba |nfl |mlb |nhl |ncaa|live \[", re.I)
left = {norm(re.sub(r"^(NBC|FOX|CBS|ABC)\s+(?=GOLF|NEWS|SPORTS)", "", c["name"], flags=re.I)): c
        for c in chans if c["src"] is None and c["group"] not in ("Adult",) and not SKIP.search(c["name"])}
for label in [l for l in cache if l not in ("US_LOCALS1", "US_local_guide", "PLEX1", "DISTROTV1", "FANDUEL1")]:
    if label not in cache or not left:
        continue
    idmap = {}
    for ev, el in ET.iterparse(io.BytesIO(cache[label]), events=("end",)):
        if el.tag == "channel":
            for d in el.findall("display-name"):
                k = norm(re.sub(r"^(MLB|NBA|NFL|NHL)\s*[-:|]\s*", "", d.text or "", flags=re.I))
                if len(k) < 4:
                    continue
                def ok(x):  # strict: same start, very similar, and no number mismatch (Plus 2 vs Plus 3)
                    if re.findall(r"\d+", x) != re.findall(r"\d+", k) or x[:4] != k[:4]:
                        return False
                    if any((w in x) != (w in k) for w in ("fat", "alt", "plu", "kid", "intl", "international")):
                        return False   # FAST/ALT/Plus/Kids variants are different channels
                    r = difflib.SequenceMatcher(None, x, k).ratio()
                    short, long_ = sorted((x, k), key=len)
                    return r >= 0.9 or (short in long_ and len(short) / len(long_) >= 0.7)
                hit = [x for x in difflib.get_close_matches(k, list(left), n=3, cutoff=0.8) if ok(x)][:1] or \
                      [x for x in left if len(x) >= 6 and (x in k or k in x) and ok(x)][:1]
                if hit:
                    c = left.pop(hit[0]); idmap[el.get("id")] = c["id"]; c["src"] = label + "~fuzzy"
                    print(f"    ~ {c['name']}  <=  {d.text}")
                    break
            el.clear()
        elif el.tag != "programme":
            continue
        else:
            oid = idmap.get(el.get("channel"))
            if oid and in_window(el):
                el.set("channel", oid); progs[oid].append(el)
            else:
                el.clear()
    print(f"  fuzzy {label}: matched {len(idmap)}")

# event channels: build a real listing from the event text in the channel name
EDT = dt.timezone(dt.timedelta(hours=-4))
def event_time(name):
    m = re.search(r"@\s*([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s*([AP]M)", name)
    if m:
        mon = dt.datetime.strptime(m.group(1), "%b").month; h = int(m.group(3)) % 12 + (12 if m.group(5) == "PM" else 0)
        return dt.datetime(NOW.year, mon, int(m.group(2)), h, int(m.group(4)), tzinfo=EDT)
    m = re.search(r"\((\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})", name)
    if m:
        return dt.datetime(*map(int, m.groups()), tzinfo=EDT)
def ev_title(name):
    m = re.search(r"\[([^\]]*?)(?:\s*@[^\]]*|\s*\(\d{4}-[^\]]*)?\]", name)
    return m.group(1).strip() if m and "EVENT ONLY" not in m.group(1).upper() else None
events = 0
for c in chans:
    if c["src"] is None and (t := event_time(c["name"])) and ev_title(c["name"]):
        def P(s, e, title, desc):
            p = ET.Element("programme", {"start": ts(s), "stop": ts(e), "channel": c["id"]})
            ET.SubElement(p, "title", {"lang": "en"}).text = title
            ET.SubElement(p, "desc", {"lang": "en"}).text = desc
            progs[c["id"]].append(p)
        def ts(x): return x.astimezone(dt.timezone.utc).strftime("%Y%m%d%H%M%S +0000")
        if t + dt.timedelta(hours=3) <= START:
            P(START, END, "No event scheduled", "Last event: " + ev_title(c["name"]))
        else:
            if t > START:
                P(START, t, "Up next: " + ev_title(c["name"]), "Event starts " + t.strftime("%b %d %I:%M %p ET"))
            P(max(t, START), t + dt.timedelta(hours=3), "LIVE: " + ev_title(c["name"]), c["group"] + " event")
            P(t + dt.timedelta(hours=3), END, "No event scheduled", "")
        c["src"] = "event"; events += 1
print("  event listings built:", events)

# TMDB: give single-show channels (e.g. "PLAY KIDZ BLUEY HD") a real description + poster
import json, os
TMDB_KEY = open("tmdb_key.txt").read().strip() if os.path.exists("tmdb_key.txt") else None
tcache = json.load(open("tmdb_cache.json", encoding="utf-8")) if os.path.exists("tmdb_cache.json") else {}
NOSHOW = re.compile(r"on-demand|originals|series \d|sereis|premiere|live \[|event|\bvs\b|network|channel|news|sports?\b|\btv\b$|^vietnam|^(nfl|nba|mlb|nhl|ncaa)\b", re.I)
def show_title(name):
    t = re.sub(r"(?i)^(play kidz|24/7|tv)\s+|\b(hd|fhd|uhd|4k|sd|east|west|tv|channel|by \w+.*)\b|\[.*?\]|\(.*?\)", " ", name)
    return re.sub(r"\s+", " ", t).strip(" -:|")
def tmdb(name):
    q = show_title(name)
    if not TMDB_KEY or len(q) < 3:
        return None
    if q in tcache:
        return tcache[q]
    best = None
    for kind in ("tv", "movie"):
        try:
            url = f"https://api.themoviedb.org/3/search/{kind}?" + urllib.parse.urlencode({"api_key": TMDB_KEY, "query": q})
            res = json.loads(fetch(url)).get("results", [])
        except Exception:
            res = []
        for r in res[:3]:
            title = r.get("name") or r.get("title") or ""
            nq, nt = norm(q), norm(title)
            if nq == nt or (len(nq) >= 6 and nq in nt and len(nq) / max(1, len(nt)) >= 0.6):
                best = {"title": title, "overview": r.get("overview", ""),
                        "poster": f"https://image.tmdb.org/t/p/w500{r['poster_path']}" if r.get("poster_path") else ""}
                break
        if best:
            break
    tcache[q] = best
    return best
enriched = 0
for c in chans:
    if not progs.get(c["id"]) and c["group"] in ("Kids", "Movies", "Comedy", "Crime & Drama", "Classic & Westerns",
            "Reality", "Sci-Fi & Horror", "Anime & Gaming", "Game Shows") and not NOSHOW.search(c["name"]) \
            and len(show_title(c["name"])) >= 5:
        info = tmdb(c["name"])
        if info:
            c["tmdb"] = info; enriched += 1
json.dump(tcache, open("tmdb_cache.json", "w", encoding="utf-8"))
print("  TMDB-enriched single-show channels:", enriched)

# placeholders so every row in the guide shows something
def ts(t): return t.strftime("%Y%m%d%H%M%S +0000")
filler = 0
for c in chans:
    if progs.get(c["id"]):
        continue
    c["src"] = "placeholder"; filler += 1
    title = c["name"]
    live = c["group"] in ("Teams", "NFL", "NBA", "MLB", "NHL", "College Sports", "Soccer", "Sports")
    t = NOW.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=2)
    while t < END:
        p = ET.Element("programme", {"start": ts(t), "stop": ts(t + dt.timedelta(hours=2)), "channel": c["id"]})
        info = c.get("tmdb")
        if info:
            ET.SubElement(p, "title", {"lang": "en"}).text = info["title"]
            ET.SubElement(p, "desc", {"lang": "en"}).text = (info["overview"] or f"{info['title']}, all day.") + " (24/7 channel)"
            if info["poster"]:
                ET.SubElement(p, "icon", {"src": info["poster"]})
        else:
            ET.SubElement(p, "title", {"lang": "en"}).text = ("Live: " if live else "") + title
            ET.SubElement(p, "desc", {"lang": "en"}).text = f"{c['group']} channel. No schedule published by the source."
        ET.SubElement(p, "category", {"lang": "en"}).text = c["group"]
        progs[c["id"]].append(p); t += dt.timedelta(hours=2)

# --- write guide ---
root = ET.Element("tv", {"generator-info-name": "shield-guide"})
for c in chans:
    ch = ET.SubElement(root, "channel", {"id": c["id"]})
    ET.SubElement(ch, "display-name").text = c["name"]
    if c["a"].get("tvg-logo"):
        ET.SubElement(ch, "icon", {"src": c["a"]["tvg-logo"]})
for c in chans:
    for p in sorted(progs[c["id"]], key=lambda p: p.get("start")):
        if p.find("category") is None:
            ET.SubElement(p, "category", {"lang": "en"}).text = c["group"]
        root.append(p)
with gzip.open("guide.xml.gz", "wb") as f:
    ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)

# --- rewrite playlist with matching ids ---
GUIDE_URL = os.environ.get("GUIDE_URL", "https://raw.githubusercontent.com/CoquiConsulting/shield-guide/main/guide.xml.gz")
with open("combined.m3u", "w", encoding="utf-8") as f:
    f.write(f'#EXTM3U url-tvg="{GUIDE_URL}"\n')
    for n, c in enumerate(chans, 1):
        a = c["a"]
        f.write(f'#EXTINF:-1 tvg-id="{c["id"]}" tvg-chno="{n}" tvg-name="{c["name"]}" tvg-logo="{a.get("tvg-logo","")}" '
                f'group-title="{c["group"]}",{c["name"]}\n{c["url"]}\n')

src = collections.Counter(c["src"] for c in chans)
real = len(chans) - src["placeholder"]
print(f"\nchannels: {len(chans)} | real schedules: {real} ({real*100//len(chans)}%) | placeholders: {src['placeholder']}")
print("by source:", dict(src))
per = collections.defaultdict(lambda: [0, 0])
for c in chans:
    per[c["group"]][1] += 1; per[c["group"]][0] += c["src"] != "placeholder"
print("groups still mostly placeholder:", {g: f"{a}/{b}" for g, (a, b) in per.items() if a < b * 0.6})



