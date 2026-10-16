"""Pull every Xtream group in one go. Reads login from xtream.txt (3 lines: server, username, password).
Never prints the login. Writes xtream_groups.csv (type, group, channel_count)."""
import json, urllib.request, urllib.parse, csv, collections

import re
lines = [l.strip() for l in open("xtream.txt", encoding="utf-8-sig") if l.strip() and "your-" not in l]
server = user = pw = None
for l in lines:
    m = re.match(r"(?i)\s*(server|url|host|portal|dns|username|user|password|pass|pwd)\s*[:=]?\s*(.+)$", l)
    if m:
        k, v = m.group(1).lower(), m.group(2).strip().split()[-1].lstrip(":=")
        if k in ("username", "user"): user = v
        elif k in ("password", "pass", "pwd"): pw = v
        else: server = v
    else:
        tok = l.split()[-1]
        if server is None and ("." in tok or tok.startswith("http")): server = tok
        elif user is None: user = tok
        elif pw is None: pw = tok
if not (server and user and pw):
    raise SystemExit(f"could not read login (found server={bool(server)} user={bool(user)} pass={bool(pw)})")
if not server.startswith("http"):
    server = "http://" + server
_u = urllib.parse.urlparse(server)
server = f"{_u.scheme}://{_u.netloc}"
base = server.rstrip("/") + "/player_api.php?" + urllib.parse.urlencode({"username": user, "password": pw})

def get(action):
    req = urllib.request.Request(base + "&action=" + action, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

rows = []
for kind, cat_act, item_act in [("live", "get_live_categories", "get_live_streams"),
                                ("movies", "get_vod_categories", "get_vod_streams"),
                                ("series", "get_series_categories", "get_series")]:
    cats = {c["category_id"]: c["category_name"] for c in get(cat_act)}
    counts = collections.Counter(str(i.get("category_id")) for i in get(item_act))
    for cid, name in cats.items():
        rows.append((kind, name, counts.get(str(cid), 0)))
    print(f"{kind}: {len(cats)} groups, {sum(counts.values())} items")

with open("xtream_groups.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["type", "group", "count"]); w.writerows(rows)
print("saved xtream_groups.csv")
