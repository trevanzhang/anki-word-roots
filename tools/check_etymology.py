"""Check every example word against its Wiktionary etymology.

    uv run python tools/check_etymology.py [--only ID_REGEX] [--report out.txt]

For each morpheme, the Latin/Greek source words in its `origin` (e.g. tribuere, tribus) are
compared with the Latin/Greek words that Wiktionary's English etymology of each example word
mentions. A word is flagged when none of them share a stem, and it isn't built with the
morpheme as a listed affix. Example: "tribulation" (from tribulum, a threshing sledge) is
flagged under tribu- "pay" (from tribuere).

This is a heuristic: it flags words for a person to check, and some flags will be fine (an
etymology that skips a step, or a word Wiktionary barely covers). Decode words are checked
part by part the same way. Wiktionary pages are cached in build/wiktionary/.

Only words are checked here, not which letters are highlighted: illum[in]ate passes, since
illuminate does come from in- + lumen. build.py checks the highlights' positions.
"""

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "word_roots" / "data"
CACHE = ROOT / "build" / "wiktionary"
API = "https://en.wiktionary.org/w/api.php"
UA = "anki-word-roots (https://github.com/jupsh/anki-word-roots)"

CLASSICAL = re.compile(r"^(la|grc|LL|ML|NL|VL|CL|la-[a-z]+|ecc)\.?$|^la-|^grc-")
DERIV = {"der", "inh", "bor", "lbor", "uder", "der+", "inh+", "bor+", "lbor+", "learned borrowing",
         "slbor", "obor", "calque", "clq", "cal", "sl", "semantic loan", "psm", "ubor", "dbt",
         "doublet", "m", "l", "mention", "link", "m+", "l-lite", "m-lite"}
# not evidence: a cognate shares an ancestor (English "ferry" and Latin "ferre"), and noncog
# says outright that two words are unrelated
AFFIX = {"af", "affix", "compound", "com", "prefix", "pre", "suffix", "suf", "confix", "con",
         "blend", "com+", "surf"}
STOP = {"latin", "greek", "ancient", "from", "and", "of", "to", "the", "see", "also", "via",
        "or", "new", "late", "medieval", "modern", "middle", "old", "french", "borrowed",
        "genitive", "hence", "related", "form", "short", "for", "abbr", "a", "in", "an"}


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("ϝ", "")


LATIN_END = re.compile(r"(ationem|atio|tionem|tio|ere|are|ire|eri|ari|iri|io|eo|or|us|um|is|es|os|as|em|ae|a|o|e|i)$")
GREEK_END = re.compile(r"(ειν|εσθαι|ομαι|ματος|μα|ευς|ικος|ος|ον|ης|ις|ας|η|α|ω|ου|ων)$")


def stem(word):
    w = norm(word).strip("-*")
    if re.search(r"[α-ω]", w):
        return GREEK_END.sub("", w)
    return LATIN_END.sub("", w.replace("j", "i").replace("v", "u"))


def etymons(origin):
    """Latin/Greek source words named in a morpheme's origin."""
    o = re.split(r",?\s+from\s+|\s*<\s*|;", origin)[0]  # the primary source, not what it came from
    o = re.sub(r'"[^"]*"|“[^”]*”|\([^)]*\)', " ", o)
    words = re.findall(r"[^\W\d_]+", o)
    return {stem(w) for w in words if norm(w) not in STOP and len(stem(w)) >= 2}


# --------------------------------------------------------------------------- wiktionary

def fetch(titles):
    """Return {title: wikitext} for up to 50 titles, cached per title."""
    out, todo = {}, []
    for t in titles:
        p = CACHE / (urllib.parse.quote(t, safe="") + ".txt")
        if p.exists():
            out[t] = p.read_text()
        else:
            todo.append(t)
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content",
                                    "rvslots": "main", "format": "json", "formatversion": 2,
                                    "redirects": 1, "titles": "|".join(batch)})
        req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req) as r:
            data = json.load(r).get("query", {})  # empty for batches of invalid titles
        alias = {n["to"]: n["from"] for n in data.get("normalized", []) + data.get("redirects", [])}
        CACHE.mkdir(parents=True, exist_ok=True)
        got = {}
        for page in data.get("pages", []):
            text = page["revisions"][0]["slots"]["main"]["content"] if "revisions" in page else ""
            title = page["title"]
            while title in alias:
                title = alias[title]
            got[title] = text
        for t in batch:
            text = got.get(t, "")
            (CACHE / (urllib.parse.quote(t, safe="") + ".txt")).write_text(text)
            out[t] = text
        time.sleep(0.5)
    return out


def english_etymology(text):
    m = re.search(r"^==English==\s*$(.*?)(?=^==[^=]|\Z)", text, re.M | re.S)
    if not m:
        return ""
    sec = m.group(1)
    parts = re.findall(r"^===+\s*Etymology[^=]*===+\s*$(.*?)(?=^===|\Z)", sec, re.M | re.S)
    return "\n".join(parts)


def classical_etymology(text, lang):
    head = "Ancient Greek" if lang.startswith("grc") else "Latin"
    m = re.search(rf"^=={head}==\s*$(.*?)(?=^==[^=]|\Z)", text, re.M | re.S)
    if not m:
        return ""
    return "\n".join(re.findall(r"^===+\s*Etymology[^=]*===+\s*$(.*?)(?=^===|\Z)", m.group(1),
                                 re.M | re.S))


def page_title(lang, term):
    """Wiktionary titles drop Latin macrons and breves but keep Greek accents."""
    if lang.startswith("grc"):
        return term
    t = unicodedata.normalize("NFD", term)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def templates(text):
    for m in re.finditer(r"\{\{([^{}]*)\}\}", text):
        args = [re.sub(r"<[^>]*>|\[\[|\]\]", "", a).strip() for a in m.group(1).split("|")]
        yield args[0], [a for a in args[1:] if "=" not in a]


def sources(ety):
    """(classical term stems, raw classical terms, English affix parts) in an etymology."""
    terms, affixes, raw = set(), set(), set()
    for name, args in templates(ety):
        if name in ("ety", "etymon"):  # newer format: {{ety|en|:bor|la:attributus}}
            for a in args[1:]:
                if a.startswith(":"):
                    continue
                if ":" in a:
                    lang, term = a.split(":", 1)
                    if CLASSICAL.match(lang):
                        terms.add(stem(term))
                        raw.add((lang, term))
                else:
                    affixes.add(norm(a).strip("-"))
        elif name in DERIV:
            # der/inh/bor: target lang, source lang, term; m/l/cog: lang, term
            mention = name in {"m", "l", "mention", "link", "m+", "l-lite", "m-lite"}
            lang, term = (args + ["", "", ""])[0:2] if mention else (args + ["", "", ""])[1:3]
            if lang and term and CLASSICAL.match(lang):
                terms.add(stem(term))
                raw.add((lang, term))
        elif name in AFFIX and args:
            lang = args[0]
            for part in args[1:]:
                if CLASSICAL.match(lang):
                    terms.add(stem(part))
                    raw.add((lang, part))
                affixes.add(norm(part).strip("-"))
    for w in re.findall(r"\b(?:Latin|Greek)\s+''+([^']+)''+", ety):  # plain-text mentions
        terms.add(stem(w))
    return terms, raw, affixes


def related(root, term):
    """Does a source word (term) contain the morpheme's source stem (root)?

    Exact match, or the root inside the term followed by the end, a vowel, t or s: so
    supportō contains portāre and audītōrium contains audīre, but tribulum (a threshing sledge)
    does not contain tribuere."""
    if root == term:
        return True
    if len(root) < 3:
        return False
    for i in range(len(term) - len(root) + 1):
        if term[i:i + len(root)] == root:
            nxt = term[i + len(root):i + len(root) + 1]
            if nxt == "" or nxt in "aeiouyts" or re.match(r"[α-ω]", root):
                return True
    return False


# --------------------------------------------------------------------------- check

def plain(marked):
    return marked.replace("[", "").replace("]", "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="only check morpheme ids matching this regex")
    ap.add_argument("--report", help="write the flagged words to this file")
    args = ap.parse_args()

    morphemes = list(csv.DictReader((DATA / "morphemes.csv").open()))
    decode = list(csv.DictReader((DATA / "decode.csv").open()))
    by_id = {m["id"]: m for m in morphemes}
    if args.only:
        morphemes = [m for m in morphemes if re.search(args.only, m["id"])]

    jobs = []  # (label, word, morpheme)
    for m in morphemes:
        for field in ("front", "more"):
            for w in m[field].split(";"):
                if w.strip():
                    jobs.append((f"{m['id']} [{field}]", plain(w), m))
    if not args.only:
        for d in decode:
            for part in d["parts"].split(" + "):
                seg, rest = part.split("=", 1)
                mid = rest.split(":")[0]
                if mid:
                    jobs.append((f"decode {d['word']} ({seg})", d["word"], by_id[mid]))

    words = sorted({w for _, w, _ in jobs})
    pages = {}
    for i in range(0, len(words), 50):
        pages.update(fetch(words[i:i + 50]))
        print(f"\rfetched {min(i + 50, len(words))}/{len(words)}", end="", flush=True)
    print()

    def ok(m, terms, affixes):
        forms = {norm(re.sub(r"\(.*?\)", "", f)).strip(" -") for f in m["forms"].split(",")}
        roots = etymons(m["origin"]) | {stem(f) for f in forms if len(f) >= 3}
        return (forms & affixes or any(len(f) >= 3 and a.startswith(f) for f in forms for a in affixes)
                or any(related(r, t) for r in roots for t in terms))

    def evidence(word, english_hops=1):
        """Classical terms and affixes for a word: its own etymology, the etymologies of the
        English words it's built from, and one hop into each Latin/Greek source entry."""
        ety = english_etymology(pages.get(word, ""))
        terms, raw, affixes = sources(ety)
        if english_hops:
            bases = sorted(a for a in affixes if len(a) >= 4 and a != norm(word))
            pages.update(fetch([b for b in bases if b not in pages]))
            for b in bases:
                t2, r2, a2 = evidence(b, english_hops - 1)
                terms |= t2
                raw |= r2
                affixes |= a2
        titles = sorted({page_title(l, t) for l, t in raw} - set(hop))
        for i in range(0, len(titles), 50):
            hop.update(fetch(titles[i:i + 50]))
        for lang, t in raw:
            t2, _, _ = sources(classical_etymology(hop.get(page_title(lang, t), ""), lang))
            terms |= t2
        return terms, raw, affixes

    hop, flagged, missing = {}, [], []
    for label, word, m in jobs:
        if not english_etymology(pages.get(word, "")):
            missing.append((label, word))
            continue
        terms, raw, affixes = sources(english_etymology(pages[word]))
        if ok(m, terms, affixes):
            continue
        terms, raw, affixes = evidence(word)
        if not ok(m, terms, affixes):
            flagged.append((label, word, m["origin"], sorted(terms)[:8]))

    lines = [f"{len(flagged)} flagged, {len(missing)} without an English etymology on Wiktionary", ""]
    lines += [f"{lab:42} {w:22} origin: {o[:50]:50} wiktionary: {', '.join(t)}"
              for lab, w, o, t in flagged]
    lines += ["", "no etymology found:"] + [f"{lab:42} {w}" for lab, w in missing]
    text = "\n".join(lines)
    if args.report:
        Path(args.report).write_text(text + "\n")
        print(lines[0], f"-> {args.report}")
    else:
        print(text)


if __name__ == "__main__":
    main()
