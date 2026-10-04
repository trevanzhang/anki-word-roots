"""Generate word_roots/data/morphemes.csv from Wikipedia (CC BY-SA 4.0).

    uv run --group tools python tools/import_wikipedia.py [--force]

This is how the first version of the CSV was made. The CSV has been hand-reviewed since, so it
is the deck's source of truth: edit it directly, and only rerun this tool (with --force) to start
over from Wikipedia.

Sources, pinned to the revisions below:
  - "List of Greek and Latin roots in English" (one page per letter)
  - "List of medical roots, suffixes and prefixes" (now titled "List of medical roots and affixes")

Selection: an entry is kept when it has enough familiar example words, measured with the
wordfreq word-frequency data (Zipf scale: 3 means about once per million words). Rows are
sorted by usefulness, the summed frequency of their best examples, which becomes study order.
"""

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from wordfreq import zipf_frequency

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build" / "wikipedia"
OUT = ROOT / "word_roots" / "data" / "morphemes.csv"
API = "https://en.wikipedia.org/w/api.php"
UA = "anki-word-roots (https://github.com/jupsh/anki-word-roots)"

ROOT_PAGES = {  # letter -> revision id ("List of Greek and Latin roots in English/<letter>")
    "A": 1377897064, "B": 1275596589, "C": 1360815995, "D": 1346448644, "E": 1301146259,
    "F": 1222950818, "G": 1371511202, "H": 1347769344, "I": 1350925285, "J": 1369713942,
    "K": 1299697880, "L": 1320808977, "M": 1318218716, "N": 1307355515, "O": 1277566959,
    "P": 1369353691, "Q": 1271579775, "R": 1181415582, "S": 1360399905, "T": 1347769372,
    "U": 1253371142, "V": 1320485430, "X": 1106460130, "Z": 1276421824,
}
MEDICAL_PAGE = 1375557021  # "List of medical roots and affixes"

# Wikipedia doesn't say which entries are prefixes; these are (by first form).
PREFIXES = set("""
a ab abs ad ac af ag al an ap ar as at ambi amphi ana ante anti apo arch auto bene bi bis cata
circum cis co col com con cor contra counter de dia dis di dif dys e ec ecto en em endo epi equi
eu ex exo extra hemi hetero homo hyper hypo in il im ir infra inter intra intro iso juxta mal
mega meso meta micro mono multi ne neo non ob oc of op omni pan para pen per peri poly post pre
preter pro proto pseudo quadr quadri re retro se semi sub suc suf sug sum sup sur sus super supra
syn sym syl tele trans tri ultra un uni
""".split())

STOP = set("of or and the a an to in on relating pertaining denoting condition state process "
           "something with without from by for as being".split())
FAMILIAR = 3.0  # zipf: front-card words must be at least this common (general entries)
MEDICAL_FAMILIAR = 2.0  # medical vocabulary is rarer in general text


# --------------------------------------------------------------------------- fetch

def fetch(oldid):
    path = CACHE / f"{oldid}.html"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        q = urllib.parse.urlencode({"action": "parse", "oldid": oldid, "prop": "text",
                                    "format": "json", "formatversion": 2})
        req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req) as r:
            path.write_text(json.load(r)["parse"]["text"])
    return BeautifulSoup(path.read_text(), "html.parser")


# --------------------------------------------------------------------------- parse

def text(el):
    for sup in el.find_all("sup"):
        sup.decompose()
    s = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
    s = re.sub(r"\s+([,);:])", r"\1", s)
    return re.sub(r"\(\s+", "(", s).strip()


def bold_examples(cell):
    """Example words with their bold (morpheme) parts marked as [..]."""
    for sup in cell.find_all("sup"):
        sup.decompose()
    html = re.sub(r"<(?!/?b\b)[^>]+>", "", cell.decode_contents())  # keep only <b>
    out = []
    for part in html.split(","):
        marked = re.sub(r"\s+", "", re.sub(r"<b>(.*?)</b>", r"[\1]", part)).replace("][", "")
        plain = marked.replace("[", "").replace("]", "")
        if plain:
            out.append(marked)
    return out


def language(s):
    g, l = "Greek" in s, "Latin" in s
    return "Latin and Greek" if g and l else "Greek" if g else "Latin" if l else ""


def parse_roots():
    recs = []
    for letter, rev in ROOT_PAGES.items():
        for t in fetch(rev).find_all("table", class_="wikitable"):
            for tr in t.find_all("tr"):
                td = tr.find_all("td")
                if len(td) < 5:
                    continue
                forms = [b.get_text(strip=True) for b in td[0].find_all("b")] or text(td[0]).split(",")
                lang, forms = language(text(td[2])), clean_forms(forms)
                # only some pages bold the morpheme inside each example; mark the rest by spelling
                examples = [e if "[" in e else mark(e, forms) for e in bold_examples(td[4])]
                recs.append(dict(source="wikipedia-roots", forms=forms,
                                 meaning=text(td[1]), language=lang,
                                 origin=(lang + " " + text(td[3])).strip() if text(td[3]) else lang,
                                 examples=examples, medical=False))
    return recs


def parse_medical():
    recs = []
    for t in fetch(MEDICAL_PAGE).find_all("table", class_="wikitable"):
        for tr in t.find_all("tr"):
            td = tr.find_all(["th", "td"])
            if len(td) < 4 or not tr.find("td"):
                continue
            origin = text(td[2])
            forms = clean_forms(re.sub(r"\(see .*?\)|\(BrE\)|\(AmE\)", "", text(td[0])).split(","))
            words = [w.strip() for w in text(td[3]).split(",") if w.strip()]
            recs.append(dict(source="wikipedia-medical", forms=forms, meaning=text(td[1]),
                             language=language(origin), origin=origin,
                             examples=[mark(w, forms) for w in words], medical=True))
    return recs


def clean_forms(forms):
    return [re.sub(r"\s+", "", f).strip(",") for f in forms if f.strip(" ,")]


def variants(form):
    """'cardi(o)-' -> ['cardio', 'cardi']; '-itis' -> ['itis']"""
    core = form.strip("-")
    m = re.match(r"^(.*?)\((\w+)\)$", core)
    return [m.group(1) + m.group(2), m.group(1)] if m else [core.replace("(", "").replace(")", "")]


def mark(word, forms):
    """Mark the first form found in a word, preferring a match at the expected end."""
    low = word.lower()
    for f in forms:
        for v in variants(f):
            if not v:
                continue
            if f.startswith("-") and not f.endswith("-"):
                if low.endswith(v):
                    return word[:len(word) - len(v)] + f"[{word[len(word) - len(v):]}]"
            else:
                i = low.find(v)
                if i >= 0:
                    return f"{word[:i]}[{word[i:i + len(v)]}]{word[i + len(v):]}"
    return word


# --------------------------------------------------------------------------- select

def plain(marked):
    return marked.replace("[", "").replace("]", "")


def zipf(marked):
    w = plain(marked)
    if " " in w or w[:1].isupper():
        return 0.0
    return zipf_frequency(w, "en")


def kind(forms):
    f = forms[0] if forms else ""
    if f.startswith("-") and not f.endswith("-"):
        return "suffix"
    return "prefix" if all(norm(x) in PREFIXES for x in forms) else "root"


def content_words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP and len(w) > 2}


def norm(form):
    return re.sub(r"\(.*?\)|[^a-z]", "", form.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite the hand-reviewed CSV")
    args = ap.parse_args()
    if OUT.exists() and not args.force:
        sys.exit(f"{OUT} exists and has been hand-reviewed; pass --force to regenerate it")

    general, medical = parse_roots(), parse_medical()

    keep = []
    for rec in general:
        z = sorted((zipf(e) for e in rec["examples"] if "[" in e), reverse=True)
        if sum(x >= FAMILIAR for x in z) >= 2:
            rec["score"] = sum(z[:5])
            keep.append(rec)

    by_form = {}
    for rec in keep:
        for f in rec["forms"]:
            by_form.setdefault(norm(f), []).append(rec)
    for rec in medical:
        same = [g for f in rec["forms"] for g in by_form.get(norm(f), [])
                if content_words(g["meaning"]) & content_words(rec["meaning"])]
        if same:  # the same morpheme as a general entry: merge into it
            g = same[0]
            g["medical"] = True
            have = {plain(e).lower() for e in g["examples"]}
            g["examples"] += [e for e in rec["examples"] if plain(e).lower() not in have]
            continue
        z = sorted((zipf(e) for e in rec["examples"] if "[" in e), reverse=True)
        if sum(x >= MEDICAL_FAMILIAR for x in z) >= 1:
            rec["score"] = sum(z[:5])
            keep.append(rec)

    # study order: general by usefulness; medical-only entries woven in after the first 60
    gen = sorted((r for r in keep if r["source"] == "wikipedia-roots"), key=lambda r: -r["score"])
    med = sorted((r for r in keep if r["source"] != "wikipedia-roots"), key=lambda r: -r["score"])
    order = gen[:60]
    rest = gen[60:]
    while rest or med:
        order += rest[:3] + med[:1]
        rest, med = rest[3:], med[1:]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "kind", "forms", "meaning", "language", "origin", "front", "more",
                    "medical", "source"])
        for rec in order:
            ex = sorted({e for e in rec["examples"] if "[" in e}, key=lambda e: -zipf(e))
            familiar = [e for e in ex if zipf(e) >= (MEDICAL_FAMILIAR if rec["medical"] else FAMILIAR)]
            front, more = familiar[:3], [e for e in ex if e not in familiar[:3]][:6]
            base = re.sub(r"[^a-z]+", "-", (rec["forms"][0] + " " + rec["meaning"].split(",")[0]).lower())
            rid = base.strip("-")[:40]
            while rid in seen:
                rid += "-2"
            seen.add(rid)
            w.writerow([rid, kind(rec["forms"]), ", ".join(rec["forms"]), rec["meaning"],
                        rec["language"], rec["origin"], "; ".join(front), "; ".join(more),
                        "y" if rec["medical"] else "", rec["source"]])
    print(f"wrote {OUT} ({len(order)} entries: {len(gen)} general, "
          f"{len(order) - len(gen)} medical-only)")


if __name__ == "__main__":
    main()
