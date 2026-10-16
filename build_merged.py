"""Build one clean US live-TV playlist + matching guide from Samsung TV Plus, Pluto TV and Plex.
Priority for duplicates: Samsung > Pluto > Plex.  Output: merged.m3u, merged.xml.gz"""
import re, gzip, urllib.request, io, sys
import xml.etree.ElementTree as ET

BASE = "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/"
SOURCES = [  # (name, playlist, epg, keep_group_filter)
    ("samsung", BASE + "samsungtvplus_us.m3u", "https://i.mjh.nz/SamsungTVPlus/us.xml.gz", None),
    ("pluto",   BASE + "plutotv_us.m3u",       "https://i.mjh.nz/PlutoTV/us.xml.gz",       None),
    ("plex",    BASE + "plex_all.m3u",         "https://i.mjh.nz/Plex/us.xml.gz",          {"United States"}),
]

# unified groups: (group, keywords matched against source group or channel name)
GROUPS = [
    ("Local News",        ["local news", "cbs news texas", "dallas", "fort worth", "dfw"]),
    ("News",              ["news", "opinion", "weather", "bloomberg", "cnbc", "court tv"]),
    ("Sports",            ["sport", "motor", "outdoor", "nfl", "nba", "mlb", "nhl", "mma", "fight", "golf", "tennis", "poker", "billiard", "racing", "fubo"]),
    ("Kids",              ["kids", "baby", "cartoon", "toon", "nick", "pbs kids", "sesame", "family"]),
    ("Movies",            ["movie", "cinema", "film"]),
    ("Comedy",            ["comedy", "laugh", "sitcom", "funny"]),
    ("Crime & Drama",     ["crime", "drama", "action", "mystery", "mysteries", "detective", "cops", "48 hours"]),
    ("Reality",           ["reality", "competition", "cheat", "wedding", "housewives"]),
    ("Game Shows",        ["game show", "daytime", "buzzr", "jeopardy", "family feud", "price is right"]),
    ("Home & Food",       ["home", "food", "kitchen", "cook", "garden", "diy", "handyman"]),
    ("Nature & Science",  ["nature", "animal", "history", "science", "documentar", "aliens", "nat geo"]),
    ("Sci-Fi & Horror",   ["sci-fi", "horror", "halloween", "scifi"]),
    ("Anime & Gaming",    ["anime", "gaming", "game"]),
    ("Classic & Westerns",["classic", "western", "retro", "replay"]),
    ("Music",             ["music", "mtv", "vevo", "concert", "radio"]),
    ("Lifestyle",         ["lifestyle", "pop culture", "entertainment", "travel", "fashion"]),
    ("Ambiance",          ["ambiance", "fireplace", "aquarium", "scenic", "relax"]),
    ("En Español",        ["latino", "espa", "spanish", "telemundo", "univision", "en espa"]),
]

def norm(s):
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\b(hd|tv|channel|us|usa|east|west|by .*)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)

def classify(src_group, name):
    hay = f"{src_group} {name}".lower()
    # Spanish first so Spanish news/movies land together
    for g, kws in [GROUPS[-1]] + GROUPS[:-1]:
        if any(k in hay for k in kws):
            return g
    return "More Channels"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def parse_m3u(text):
    out, lines = [], text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("#EXTINF") and i + 1 < len(lines):
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', l))
            name = l.split(",", 1)[-1].strip()
            out.append({"attrs": attrs, "name": name, "url": lines[i + 1].strip()})
    return out

def main():
    seen, keep, epg_ids = set(), [], {}
    stats = {}
    for src, pl, epg, gfilter in SOURCES:
        chans = parse_m3u(fetch(pl).decode("utf-8", "replace"))
        added = dup = 0
        for c in chans:
            sg = c["attrs"].get("group-title", "")
            if gfilter and sg not in gfilter:
                continue
            key = norm(c["name"])
            if not key or key in seen:
                dup += 1
                continue
            seen.add(key)
            c["src"], c["group"] = src, classify(sg, c["name"])
            keep.append(c)
            epg_ids.setdefault(src, set()).add(c["attrs"].get("tvg-id", ""))
            added += 1
        stats[src] = (added, dup)

    order = [g for g, _ in GROUPS[:-1]] + [GROUPS[-1][0], "More Channels"]
    keep.sort(key=lambda c: (order.index(c["group"]), c["name"].lower()))
    with open("merged.m3u", "w", encoding="utf-8") as f:
        f.write('#EXTM3U url-tvg="merged.xml.gz"\n')
        for n, c in enumerate(keep, 1):
            a = c["attrs"]
            f.write(f'#EXTINF:-1 tvg-id="{a.get("tvg-id","")}" tvg-chno="{n}" tvg-name="{c["name"]}" '
                    f'tvg-logo="{a.get("tvg-logo","")}" group-title="{c["group"]}",{c["name"]}\n{c["url"]}\n')

    # filtered combined guide
    root = ET.Element("tv", {"generator-info-name": "shield-merged"})
    progs = []
    for src, pl, epg, _ in SOURCES:
        ids = epg_ids.get(src, set())
        tree = ET.parse(io.BytesIO(gzip.decompress(fetch(epg))))
        for el in tree.getroot():
            cid = el.get("id") if el.tag == "channel" else el.get("channel")
            if cid in ids:
                (root if el.tag == "channel" else progs).append(el) if el.tag == "channel" else progs.append(el)
    for p in progs:
        root.append(p)
    with gzip.open("merged.xml.gz", "wb") as f:
        ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)

    print("kept per source (added, dup-skipped):", stats)
    print("total channels:", len(keep))
    from collections import Counter
    for g, n in sorted(Counter(c["group"] for c in keep).items(), key=lambda x: order.index(x[0])):
        print(f"  {g}: {n}")

if __name__ == "__main__":
    main()
