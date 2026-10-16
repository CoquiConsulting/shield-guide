import re
QUALITY = r"\b(hd|fhd|uhd|sd|4k|hevc|h265|raw|backup|vip|us|usa|east|west|feed|live|tv|channel|the)\b"
import unicodedata
TYPOS = {"amiricans": "americas", "americans": "americas"}
def norm(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(a and e|a&e|ae|wb|en)\b", " ", s)
    s = " ".join(TYPOS.get(w, re.sub(r"(?<=[a-z]{3})s$", "", w)) for w in re.split(r"[\s']+", s))
    s = re.sub(r"^\s*[a-z]{2,3}\s*[|:]\s*", "", s)        # "US| " / "VN: " prefixes
    s = re.sub(r"\[.*?\]|\(.*?\)|\{.*?\}", "", s)          # bracketed notes
    s = re.sub(r"\bby\s+\w+.*$", "", s)                     # "... by DUST"
    s = re.sub(QUALITY, "", s)
    s = re.sub(r"\bby\s*$", "", s.strip())
    s = re.sub(r"[^a-z0-9]", "", s)
    s = re.sub(r"^tv|tv$", "", s)          # "TVOne" / "PickleballTV"
    return s.replace("s", "")               # "SportsGrid" == "Sports Grid", "World's" == "Worlds"


