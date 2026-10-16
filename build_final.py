"""Final private playlist: free + Xtream US + Vietnam + Adult, deduped, every channel categorized
using EPG genre tags -> name keywords -> source group. Output combined.m3u (contains login, keep local)."""
import re, gzip, io, urllib.parse, collections
import xml.etree.ElementTree as ET
exec(open("xtream_groups.py", encoding="utf-8").read().split("rows = []")[0])  # server/user/pw + get()

GROUPS = ["DFW Local", "Teams", "Local News", "News", "Sports", "NFL", "NBA", "MLB", "NHL", "College Sports",
          "Soccer", "Kids", "Movies", "Comedy", "Crime & Drama", "Reality", "Game Shows", "Home & Food",
          "Nature & Science", "Sci-Fi & Horror", "Anime & Gaming", "Classic & Westerns", "Music", "Entertainment",
          "Lifestyle & Travel", "Faith", "Ambiance", "Premium", "En Español", "Vietnam", "Adult"]

# keyword -> group (checked against EPG genres first, then channel name, then source group)
RULES = [
    ("Local News",       r"local news|cbs news (texas|dallas)|dallas|fort worth|dfw"),
    ("En Español",       r"español|espanol|latino|spanish|telemundo|univision|\bvix\b|en espa|noticias|telenovela|novela|azteca|estrella|canela|\bcine\b|acci[oó]n|emoci[oó]n|naturaleza|buen viaje|mi casa|pitufo|atres|alerta|luz y amor|cl[aá]sicos"),
    ("Premium",          r"prime video|paramount\+|peacock|hbo|max original|apple tv|hulu|netflix|showtime|starz"),
    ("NFL",              r"\bnfl\b|football league|redzone"),
    ("NBA",              r"\bnba\b|basketball"),
    ("MLB",              r"\bmlb\b|baseball"),
    ("NHL",              r"\bnhl\b|hockey"),
    ("College Sports",   r"\bncaa\b|college|\bsec\b|\bacc\b|big ?ten|\bbtn\b|pac-?12"),
    ("Soccer",           r"soccer|\bmls\b|futbol|fútbol|premier league|fifa"),
    ("News",             r"\bnews\b|weather|politic|business|finance|bloomberg|cnbc|opinion|current affairs|court"),
    ("Sports",           r"sport|espn|golf|tennis|mma|boxing|wrestling|racing|motor|nascar|f1\b|poker|fight|outdoor|fishing|hunting"),
    ("Kids",             r"child|kids|kid\b|cartoon|animation|animated|toon|baby|nick|disney|pbs kids|preschool|family"),
    ("Anime & Gaming",   r"anime|gaming|esport|video game|minecraft|gameplay|sonic|pokemon|unspeakable"),
    ("Classic & Westerns", r"heroes ?& ?icons|\bfetv\b|\bmetv\b|\bion\b|grit|cozi|antenna|decades|classic|western|retro"),
    ("Faith",            r"3abn|impact network|tbn|daystar|ewtn|spark tv|god|gospel|christian|church|bible"),
    ("Movies",           r"\bmovie|\bfilm|cinema|feature"),
    ("Sci-Fi & Horror",  r"sci-?fi|science fiction|horror|thriller|supernatural|halloween|fantasy"),
    ("Comedy",           r"comedy|sitcom|funny|laugh|stand-?up"),
    ("Game Shows",       r"game show|quiz|gameshow|buzzr|jeopardy|feud|price is right|supermarket sweep|wheel of fortune|deal or no deal|match game"),
    ("Crime & Drama",    r"crime|drama|mystery|detective|police|cops|investigat|true crime|action|soap|legal|\bfbi\b|rookie|blue bloods|\bcsi\b|ncis|criminal|midsomer|forensic|court|law ?&|homicide|murder|caught in"),
    ("Reality",          r"reality|competition|dating|wedding|makeover|docuseries|big brother|bachelor|love (and|&) marriage|say yes|love thy|survivor|repair shop|extreme jobs|unique lives|cleo|tru ?tv"),
    ("Sports",           r"\bfuel\b|bowling|players tv|\bwwe\b|nxt|impact wrestling|unbeaten|billiard|surf|skate"),
    ("Music",            r"\btrace\b|vevo|stingray|\bxite\b"),
    ("Home & Food",      r"cook|food|kitchen|home|garden|diy|renovat|house|real estate|handyman"),
    ("Nature & Science", r"nature|animal|wildlife|\bwild\b|earthx|history|science|documentar|space|technology|educat|aliens|pbs|\bsci\b|vice"),
    ("Classic & Westerns", r"western|classic|retro|vintage|replay|nostalg|\bmetv\b"),
    ("Music",            r"music|concert|\bmtv\b|vevo|karaoke|\bradio\b|hits"),
    ("Faith",            r"relig|faith|christian|church|gospel|bible|inspiration"),
    ("Ambiance",         r"ambiance|ambient|fireplace|aquarium|scenic|relax|slow tv|nature sounds"),
    ("Lifestyle & Travel", r"travel|lifestyle|fashion|beauty|health|fitness|shopping|pop culture|celebrity"),
]
# exact show/network names (checked on channel name before anything else)
NAME_RULES = [
    ("En Español",       r"noticias|novelisima|pelimex|\btr3s\b|universo|\blatv\b|coraz[oó]n|delito|freetv|lucha|[eé]xitos|\brcn\b|autopista|ideas en|nosey esc|fiebre|grjngo|revry latinx|el rey"),
    ("Faith",            r"osteen|jakes|catholic|word network|victory channel|pureflix|\buptv\b|highway to heaven"),
    ("Sci-Fi & Horror",  r"scream|shudder|scares|monsters are real|outer limits|farscape|continuum|defiance|librarians|teen wolf|dungeons"),
    ("Classic & Westerns", r"dick van dyke|green acres|carol burnett|ed sullivan|johnny carson|that girl|bonanza|tv land|remember the|\by2k\b|felicity|bold and the beautiful"),
    ("Comedy",           r"mr\.? bean|corner gas|\balf\b|trailer park|sketchy|adult swim|\bifc\b|penn & teller|graham norton|weeds|failarmy|afv"),
    ("Music",            r"billboard|hip-hop|smooth jazz|metal\.rocks|\bcmt\b|circle country|^fm\b|\bboot\b|black effect|ringer from spotify"),
    ("Sports",           r"big 12|pickleball|speedvision|racer|strongman|cricket|cowboy channel|combatv|\bcharge\b|slopes"),
    ("Reality",          r"biggest loser|the challenge|project runway|little women|love after lockup|osbournes|girls next door|made in chelsea|four in a bed|drag race|top chef|iron chef|baking|judge judy|tribunal|on patrol|sheriffs|dr\.? phil|the doctors|wendy|american gladiators|celebrity name game|let's make a deal|gsn|tlc|\bown\b|lmn|wb love kills|legacy|reign with"),
    ("Crime & Drama",    r"bosch|mi-5|nikita|declassified|confess|hallmark|freeform|wgn america|a&e|\bamc\b|outlaw|pop \["),
    ("Nature & Science", r"dog whisperer|pet collective|paws|ice pilots|highway thru hell|jade|survive|shouldn't be alive|curiosity|insight tv|get\.factual|danger tv|great american adventures|in the garage|chopper|grand designs|drone|startalk|medical incredible|bob ross|outpost"),
    ("Kids",             r"wiggles|hasbro|fluffy|eddie's wonderland|ryan trahan"),
    ("News",             r"cheddar|infowars|local now|district of columbia|wjxt|tnbc"),
    ("Lifestyle & Travel", r"beach tv|nomad|tastemade|travel escapes|gotraveler|bbc travel|qvc|hsn|\bjtv\b|gem shopping|fashiontv|tony robbins|growthday|more u|eat your feed|addictatv"),
    ("Premium",          r"amc plus|amc presents|mgm presents|tribeca|cinelife|rakuten viki|asiancrush|shemaroo|blackpix|cindie"),
]
def name_group(name):
    for g, pat in NAME_RULES:
        if re.search(pat, name, re.I):
            return g

FIXED = {  # Xtream source groups that already say exactly what they are
    "AM | USA NFL": "NFL", "AM | USA NBA": "NBA", "AM | USA MLB": "MLB", "AM | USA NHL": "NHL",
    "AM | USA NCAA": "College Sports", "AM | USA MLS": "Soccer", "AM | USA ESPN": "Sports",
    "AM | USA FOX SPORT": "Sports", "AM | USA NBC SPORT": "Sports", "AM | USA SPORTS": "Sports",
    "AM | USA PEACOCK": "Premium", "AM | USA PARAMOUNT": "Premium", "AM | USA HBO MAX": "Premium",
    "AM | USA HULU": "Premium", "AM | USA APPLE TV+": "Premium", "AM | USA FANDUEL": "Sports",
    "AM | USA NEWS": "News", "AM | USA KIDS&FAMLIY": "Kids", "AM | USA PLAY KIDZ": "Kids",
    "AM | USA CINEMA": "Movies", "AM | USA DOCUMENTARY": "Nature & Science", "AM | USA MUSIC": "Music",
    "AS | VIETNAM": "Vietnam", "XX | FOR ADULT": "Adult",
}
CLASSIFY = {"AM | USA GENERAL", "AM | USA ENTERTAINMENT", "AM | USA STREAMED CHANNELS",
            "AM | USA 24/7 SEREIS", "AM | USA 24/7 ON-DEMAND"}
# everything else in Xtream is dropped (other markets' locals, PBS affiliates, event slots, foreign)

DFW = [r"\(WFAA\) DALLAS", r"\(KTVT\)", r"\(KDFW\) DALLAS", r"\(KXAS\)", r"\(KDAF\)", r"\(KDFI\)",
       r"\(KERA\) DALLAS", r"\(KUVN\)", r"\(KXTX\)", r"\(KAZD\)", r"SPECTRUM NEWS 1 - DALLAS"]
TEAMS = [r"TEXAS RANGERS", r"DALLAS MAVERICKS", r"NHL DALLAS STARS", r"Texas Stars"]

QUALITY = r"\b(hd|fhd|uhd|sd|4k|hevc|h265|raw|backup|vip|us|usa|east|west|feed|live|tv|channel|the)\b"
import unicodedata
TYPOS = {"amiricans": "americas", "americans": "americas"}
def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(a and e|a&e|ae|wb|en)\b", " ", s).replace("nature escape", "naturescape")
    s = " ".join(TYPOS.get(w, re.sub(r"(?<=[a-z]{3})s$", "", w)) for w in re.split(r"[\s']+", s))
    s = re.sub(r"^\s*[a-z]{2,3}\s*[|:]\s*", "", s)        # "US| " / "VN: " prefixes
    s = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}", "", s)          # bracketed notes
    s = re.sub(r"\bby\s+\w+.*$", "", s)                     # "... by DUST"
    s = re.sub(QUALITY, "", s)
    s = re.sub(r"\bby\s*$", "", s.strip())
    s = re.sub(r"[^a-z0-9]", "", s)
    s = re.sub(r"^tv|tv$", "", s)          # "TVOne" / "PickleballTV"
    return s.replace("s", "")               # "SportsGrid" == "Sports Grid", "World's" == "Worlds"

def clean_name(n):
    return re.sub(r"^\s*(US|VN)\s*[|:]\s*", "", n).strip()

def rule_group(text):
    t = text.lower()
    for g, pat in RULES:
        if re.search(pat, t):
            return g
    return None

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

def load_genres(data, genres):
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    for ev, el in ET.iterparse(io.BytesIO(data), events=("end",)):
        if el.tag == "programme":
            cid = el.get("channel")
            for c in el.findall("category"):
                if c.text:
                    genres[cid][c.text.strip()] += 1
            if len(texts[cid]) < 30:
                t = " ".join((x.text or "") for x in el if x.tag in ("title", "sub-title", "desc"))
                if t.strip():
                    texts[cid].append(t)
            el.clear()

genres = collections.defaultdict(collections.Counter)
texts = collections.defaultdict(list)
load_genres(open("merged.xml.gz", "rb").read(), genres)
try:
    xml_x = fetch(f"{server}/xmltv.php?" + urllib.parse.urlencode({"username": user, "password": pw}))
    load_genres(xml_x, genres)
except Exception as e:
    print("xtream guide not loaded:", type(e).__name__)
print("channels with genre tags:", sum(1 for v in genres.values() if v), "| with show info:", len(texts))

def epg_group(tid):
    g = genres.get(tid)
    if g:
        for tag, _ in g.most_common(5):
            r = rule_group(tag)
            if r:
                return r
    # no genre tags: vote using show titles + descriptions from the guide
    votes = collections.Counter(rule_group(t) for t in texts.get(tid, []))
    votes.pop(None, None)
    if votes:
        grp, n = votes.most_common(1)[0]
        if n >= max(2, len(texts.get(tid, [])) // 4):
            return grp
    return None

OLD = {"Lifestyle": "Lifestyle & Travel", "Crime": "Crime & Drama", "Westerns": "Classic & Westerns",
       "Classic TV": "Classic & Westerns", "More Channels": None, "United States": None}
def tag_group(tid):
    for tag, _ in (genres.get(tid) or collections.Counter()).most_common(5):
        r = rule_group(tag)
        if r:
            return r
def pick(tid, name, src_group, default):
    return name_group(name) or tag_group(tid) or rule_group(name) or epg_group(tid) or (OLD.get(src_group, src_group) if src_group in GROUPS or src_group in OLD else None) or rule_group(src_group or "") or default

cats = {c["category_id"]: c["category_name"].strip() for c in get("get_live_categories")}
streams = get("get_live_streams")
def xurl(s):
    return f"{server}/live/{urllib.parse.quote(user)}/{urllib.parse.quote(pw)}/{s['stream_id']}.ts"

out, seen_name, seen_url, dropped = [], set(), set(), collections.Counter()
def add(group, name, logo, tid, url, why):
    k = norm(name)
    if re.match(r"^\W", name.strip()) and re.search(r"\W$", name.strip()):   # "●●● USA| GENERAL ●●●" separators
        dropped["separator rows"] += 1
        return
    if not k or k in seen_name or url in seen_url:
        dropped[why] += 1
        return
    seen_name.add(k); seen_url.add(url)
    out.append([group, clean_name(name), logo or "", tid or "", url])

# 1) pinned DFW + Teams
for label, pats in (("DFW Local", DFW), ("Teams", TEAMS)):
    for p in pats:
        for s in streams:
            if cats.get(s.get("category_id"), "").startswith("AM | USA") and re.search(p, s.get("name", ""), re.I):
                add(label, s["name"], s.get("stream_icon"), s.get("epg_channel_id"), xurl(s), "dup"); break

# 2) free channels (already deduped among themselves)
cur = None
for l in open("merged.m3u", encoding="utf-8"):
    l = l.strip()
    if l.startswith("#EXTINF"):
        a = dict(re.findall(r'([\w-]+)="([^"]*)"', l)); cur = (a, l.split(",", 1)[-1])
    elif l and not l.startswith("#") and cur:
        a, name = cur; cur = None
        g = "Local News" if re.search(RULES[0][1], name, re.I) or a.get("group-title") == "Local News" else \
            pick(a.get("tvg-id"), name, a.get("group-title"), "Entertainment")
        add(g, name, a.get("tvg-logo"), a.get("tvg-id"), l, "dup with free")

# 3) Xtream: fixed groups, then genre-classified groups (dedup against free)
for s in streams:
    src = cats.get(s.get("category_id"), "")
    if src in FIXED:
        add(FIXED[src], s.get("name", ""), s.get("stream_icon"), s.get("epg_channel_id"), xurl(s), "dup with free")
for s in streams:
    src = cats.get(s.get("category_id"), "")
    if src in CLASSIFY:
        g = pick(s.get("epg_channel_id"), s.get("name", ""), None, "Entertainment")
        add(g, s.get("name", ""), s.get("stream_icon"), s.get("epg_channel_id"), xurl(s), "dup with free")

out.sort(key=lambda r: (GROUPS.index(r[0]) if r[0] in GROUPS else 999, r[1].lower()))
stray = [r for r in out if r[0] not in GROUPS]
epg_x = f"{server}/xmltv.php?" + urllib.parse.urlencode({"username": user, "password": pw})
with open("combined.m3u", "w", encoding="utf-8") as f:
    f.write(f'#EXTM3U url-tvg="{epg_x}"\n')
    for n, (g, name, logo, tid, url) in enumerate(out, 1):
        f.write(f'#EXTINF:-1 tvg-id="{tid}" tvg-chno="{n}" tvg-name="{name}" tvg-logo="{logo}" group-title="{g}",{name}\n{url}\n')

# audit
c = collections.Counter(r[0] for r in out)
keys = collections.Counter(norm(r[1]) for r in out)
print("total channels:", len(out))
print("duplicates removed:", dict(dropped))
print("remaining duplicate names:", sum(1 for k, v in keys.items() if v > 1))
print("uncategorized/stray:", len(stray), [r[1] for r in stray][:10])
for g in GROUPS:
    if c[g]:
        print(f"  {g}: {c[g]}")
with open("categories_report.csv", "w", encoding="utf-8") as f:
    f.write("group,channel\n")
    for r in out:
        f.write(f'"{r[0]}","{r[1]}"\n')

