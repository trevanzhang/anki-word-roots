"""Build the Word Roots Anki deck.

    uv run python word_roots/build.py            # -> dist/Word_Roots.apkg
    uv run python word_roots/build.py --html X   # also write an HTML preview of every note

Content lives in word_roots/data/:
  morphemes.csv  one row per prefix, root or suffix, in study order
  stories.csv    optional etymology stories, by morpheme id
  decode.csv     words to break down into morphemes
"""

import argparse
import csv
import hashlib
import html
import re
from pathlib import Path

import genanki

HERE = Path(__file__).parent
DATA = HERE / "data"
ROOT = HERE.parent
DIST = ROOT / "dist"
DECK_NAME = "Word Roots"

ROOT_MODEL_ID = 1730581402
DECODE_MODEL_ID = 1730581403
DECODE_DELAY = 4  # a decode card comes this many morphemes after the last one it uses

CSS = r"""
.card {
  font-family: -apple-system, "Segoe UI", Inter, Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 20px; line-height: 1.5; color: #1f2937; background: #fafaf9;
  text-align: center; margin: 0; padding: 0;
}
.wrap { max-width: 640px; margin: 0 auto; padding: 22px 16px 28px; --accent: #7c3aed; }
.prefix { --accent: #2563eb; } .root { --accent: #7c3aed; } .suffix { --accent: #0d9488; }
.decode { --accent: #b45309; }
.label {
  font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  color: var(--accent); margin-bottom: 14px;
}
.label .med { color: #6b7280; }
.words { font-size: 1.45em; font-weight: 500; line-height: 1.7; }
span.w { display: inline-block; margin: 0 .45em; }
.m { color: var(--accent); font-weight: 700; text-decoration: underline; text-underline-offset: 4px; }
.prompt { color: #6b7280; font-size: .85em; margin-top: 14px; }
.meaning { font-size: 1.5em; font-weight: 650; margin: 4px 0 2px; }
.forms { color: var(--accent); font-weight: 600; }
.origin { color: #6b7280; font-size: .85em; margin-top: 4px; }
.more { margin-top: 12px; font-size: .95em; }
.story {
  margin: 16px auto 0; max-width: 560px; padding: 10px 14px; border-radius: 10px; font-size: .86em;
  background: #f3f4f6; color: #4b5563; text-align: left; border-left: 3px solid var(--accent);
}
hr#answer { border: none; border-top: 1px solid #e5e7eb; margin: 18px 0 14px; }
.word { font-size: 1.7em; font-weight: 650; letter-spacing: .01em; }
table.parts { margin: 6px auto 10px; border-collapse: collapse; font-size: .95em; }
table.parts td { padding: 3px 10px; text-align: left; }
table.parts td.seg { font-weight: 700; color: var(--accent); text-align: right; }
table.parts td.plain { color: #9ca3af; text-align: right; }
table.parts td.plain-gloss { color: #6b7280; font-style: italic; }
.rootm { font-size: .75em; color: #9ca3af; }
a.src { font-size: .8em; color: #9ca3af; }
.literal { font-style: italic; color: #4b5563; }
.definition { font-size: 1.1em; font-weight: 600; margin-top: 6px; }

/* night mode (desktop: .nightMode, AnkiDroid: .night_mode) */
.card.nightMode, .card.night_mode { background: #1c1c1e; color: #e5e7eb; }
.nightMode .prefix, .night_mode .prefix { --accent: #60a5fa; }
.nightMode .root, .night_mode .root { --accent: #a78bfa; }
.nightMode .suffix, .night_mode .suffix { --accent: #2dd4bf; }
.nightMode .decode, .night_mode .decode { --accent: #fbbf24; }
.nightMode .prompt, .night_mode .prompt, .nightMode .origin, .night_mode .origin,
.nightMode .label .med, .night_mode .label .med { color: #9ca3af; }
.nightMode .story, .night_mode .story { background: #27272a; color: #d4d4d8; }
.nightMode .literal, .night_mode .literal { color: #d4d4d8; }
.nightMode td.plain-gloss, .night_mode td.plain-gloss { color: #9ca3af; }
.nightMode hr#answer, .night_mode hr#answer { border-top-color: #3f3f46; }
"""

LABEL = '<div class="label">{{Language}} {{Kind}}{{#Medical}} <span class="med">· medical</span>{{/Medical}}</div>'

ROOT_MODEL = genanki.Model(
    ROOT_MODEL_ID, "Word Roots · Morpheme",
    fields=[{"name": n} for n in
            ("Morpheme", "Meaning", "Kind", "KindClass", "Language", "Origin", "Words", "More",
             "Story", "Medical")],
    templates=[{
        "name": "Words → Meaning",
        "qfmt": '<div class="wrap {{KindClass}}">' + LABEL +
                '<div class="words">{{Words}}</div>'
                '<div class="prompt">What does the highlighted part mean?</div></div>',
        "afmt": '<div class="wrap {{KindClass}}">' + LABEL +
                '<div class="words">{{Words}}</div><hr id="answer">'
                '<div class="meaning">{{Meaning}}</div><div class="forms">{{Morpheme}}</div>'
                '<div class="origin">{{Origin}}</div>'
                '{{#More}}<div class="more">{{More}}</div>{{/More}}'
                '{{#Story}}<div class="story">{{Story}}</div>{{/Story}}</div>',
    }],
    css=CSS,
)

DECODE_MODEL = genanki.Model(
    DECODE_MODEL_ID, "Word Roots · Decode",
    fields=[{"name": n} for n in ("Word", "Parts", "Literal", "Definition", "Medical")],
    templates=[{
        "name": "Decode",
        "qfmt": '<div class="wrap decode"><div class="label">Decode'
                '{{#Medical}} <span class="med">· medical</span>{{/Medical}}</div>'
                '<div class="word">{{Word}}</div>'
                '<div class="prompt">Break it into parts. What does it literally mean?</div></div>',
        "afmt": '<div class="wrap decode"><div class="label">Decode'
                '{{#Medical}} <span class="med">· medical</span>{{/Medical}}</div>'
                '<div class="word">{{Word}}</div><hr id="answer">'
                '<table class="parts">{{Parts}}</table>'
                '<div class="literal">“{{Literal}}”</div>'
                '<div class="definition">{{Definition}}</div></div>',
    }],
    css=CSS,
)

DECK_DESCRIPTION = (
    "The Greek and Latin prefixes, roots and suffixes that build English words, including the "
    "medical ones: a core of the most useful morphemes first, then the rest by usefulness. Each "
    "morpheme is taught through familiar words, and Decode cards practise taking words apart. "
    "<b>Grading:</b> count an answer as right if you recall the essential meaning; exact wording "
    "and the stories are extras. <b>Settings:</b> to keep the intended order, set New card gather "
    "order to <i>Ascending position</i> and New card sort order to <i>Order gathered</i>. "
    "Skip specialist medical vocabulary with <code>-tag:WR::Medical</code>. Root data adapted "
    "from Wikipedia's <i>List of Greek and Latin roots in English</i> and <i>List of medical "
    "roots, suffixes and prefixes</i> (CC BY-SA 4.0); this deck is shared under the same license."
)


# --------------------------------------------------------------------------- helpers

def read(name):
    with (DATA / name).open(newline="") as fh:
        return list(csv.DictReader(fh))


def mark(word):
    """'[aud]ience' -> HTML with the morpheme highlighted."""
    if not re.search(r"\[[^\]]+\]", word):
        raise SystemExit(f"no marked morpheme in {word!r}")
    out = html.escape(word)
    return re.sub(r"\[([^\]]+)\]", r'<span class="m">\1</span>', out)


def word_list(s):
    return "".join(f'<span class="w">{mark(w.strip())}</span>' for w in s.split(";") if w.strip())


def deck_id(name):
    return 1_700_000_000 + int(hashlib.sha1(name.encode()).hexdigest()[:7], 16)


# --------------------------------------------------------------------------- build

def parse_parts(d, index):
    """'peri=peri-around + card=cardi-heart:heart + tonsill=:tonsils' ->
    [(segment, morpheme id or "", gloss or "")]; checks the parts against the word."""
    parts = []
    for part in d["parts"].split(" + "):
        seg, _, rest = part.partition("=")
        mid, _, gloss = rest.partition(":")
        if mid and mid not in index:
            raise SystemExit(f"decode {d['word']}: unknown morpheme {mid}")
        if not mid and not gloss:
            raise SystemExit(f"decode {d['word']}: segment {seg!r} has neither a morpheme nor a gloss")
        parts.append((seg, mid, gloss))
    if "".join(seg for seg, _, _ in parts) != d["word"]:
        raise SystemExit(f"decode {d['word']}: segments spell {''.join(s for s, _, _ in parts)!r}")
    return parts


def story_html(row):
    link = f' <a class="src" href="{html.escape(row["source"])}">source</a>' if row.get("source") else ""
    return row["story"] + link


def decode_fields(d, morphemes, index):
    """A decode note's fields, and the study position of the last morpheme it uses."""
    rows, last = [], 0
    for seg, mid, gloss in parse_parts(d, index):
        if mid:
            last = max(last, index[mid])
            meaning = morphemes[index[mid]]["meaning"]
            root = (f'<div class="rootm">{html.escape(morphemes[index[mid]]["forms"])} '
                    f'{html.escape(meaning)}</div>') if gloss and gloss != meaning else ""
            rows.append(f'<tr><td class="seg">{html.escape(seg)}</td>'
                        f'<td>{html.escape(gloss or meaning)}{root}</td></tr>')
        else:
            rows.append(f'<tr><td class="plain">{html.escape(seg)}</td>'
                        f'<td class="plain-gloss">{html.escape(gloss)}</td></tr>')
    fields = [d["word"], "".join(rows), html.escape(d["literal"]), html.escape(d["definition"]),
              "y" if d["medical"] else ""]
    return fields, last


def validate(morphemes, stories, decode, index):
    if len(index) != len(morphemes):
        raise SystemExit("duplicate morpheme ids")
    story_ids = [r["id"] for r in stories]
    if len(set(story_ids)) != len(story_ids):
        raise SystemExit("duplicate story ids")
    if unknown := set(story_ids) - set(index):
        raise SystemExit(f"stories for unknown ids: {sorted(unknown)}")
    words = [d["word"] for d in decode]
    if len(set(words)) != len(words):
        raise SystemExit("duplicate decode words")
    for m in morphemes:
        if m["medical"] not in ("", "related", "y"):
            raise SystemExit(f"{m['id']}: medical must be empty, 'related' or 'y'")
    specialist = {m["id"] for m in morphemes if m["medical"] == "y"}
    for d in decode:
        used = {mid for _, mid, _ in parse_parts(d, index) if mid}
        # skipping specialist vocabulary (-tag:WR::Medical) must not strand an everyday decode card
        if not d["medical"] and used & specialist:
            raise SystemExit(f"decode {d['word']}: everyday word uses specialist morphemes "
                             f"{sorted(used & specialist)}")


def build(html_out=None, only=None):
    morphemes = read("morphemes.csv")
    story_rows = read("stories.csv")
    stories = {r["id"]: story_html(r) for r in story_rows}
    decode = read("decode.csv")
    index = {m["id"]: i for i, m in enumerate(morphemes)}
    validate(morphemes, story_rows, decode, index)

    deck = genanki.Deck(deck_id(DECK_NAME), DECK_NAME, description=DECK_DESCRIPTION)
    notes, preview = [], []

    for i, m in enumerate(morphemes):
        if only and not re.search(only, m["forms"] + " " + m["meaning"], re.I):
            continue
        kind = m["kind"].capitalize()
        lang = m["language"] or "Latin/Greek"
        fields = [html.escape(m["forms"]), html.escape(m["meaning"]), m["kind"], m["kind"], lang,
                  html.escape(m["origin"]), word_list(m["front"]),
                  word_list(m["more"]) if m["more"] else "", stories.get(m["id"], ""),
                  "y" if m["medical"] == "y" else ""]
        tags = [f"WR::{kind}", f"WR::{lang.replace(' ', '_').replace('/', '_')}"]
        if m["core"]:
            tags.append("WR::Core")
        if m["medical"] == "y":
            tags.append("WR::Medical")
        elif m["medical"] == "related":
            tags.append("WR::Medical_Related")
        if m["id"] in stories:
            tags.append("WR::Story")
        notes.append((i * 10, genanki.Note(model=ROOT_MODEL, fields=fields, tags=tags,
                                           guid=genanki.guid_for("wr", m["id"]))))
        preview.append(("root", fields))

    for d in decode:
        if only and not re.search(only, d["word"], re.I):
            continue
        fields, last = decode_fields(d, morphemes, index)
        tags = ["WR::Decode"] + (["WR::Medical"] if d["medical"] else [])
        notes.append(((last + DECODE_DELAY) * 10 + 5,
                      genanki.Note(model=DECODE_MODEL, fields=fields, tags=tags,
                                   guid=genanki.guid_for("wr-decode", d["word"]))))
        preview.append(("decode", fields))

    for due, (_, note) in enumerate(sorted(notes, key=lambda x: x[0]), 1):
        note.due = due
        deck.add_note(note)

    out = (ROOT / "build" if only else DIST) / "Word_Roots.apkg"  # partial builds stay out of dist/
    out.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(out)
    n_root = sum(1 for k, _ in preview if k == "root")
    print(f"wrote {out}  ({n_root} morphemes, {len(preview) - n_root} decode words, "
          f"{sum(1 for k, f in preview if k == 'root' and f[8])} stories)")
    if html_out:
        write_preview(Path(html_out), preview)


def write_preview(path, preview):
    """Static HTML of every note's back, for proofreading."""
    blocks = []
    for kind, f in preview:
        if kind == "root":
            morpheme, meaning, kname, kclass, lang, origin, words, more, story, med = f
            blocks.append(
                f'<div class="wrap {kclass}" style="border-bottom:6px solid #ddd">'
                f'<div class="label">{lang} {kname}{" · medical" if med else ""}</div>'
                f'<div class="words">{words}</div><hr id="answer"><div class="meaning">{meaning}</div>'
                f'<div class="forms">{morpheme}</div><div class="origin">{origin}</div>'
                + (f'<div class="more">{more}</div>' if more else "")
                + (f'<div class="story">{story}</div>' if story else "") + "</div>")
        else:
            word, parts, literal, definition, med = f
            blocks.append(
                f'<div class="wrap decode" style="border-bottom:6px solid #ddd">'
                f'<div class="label">Decode{" · medical" if med else ""}</div>'
                f'<div class="word">{word}</div><hr id="answer"><table class="parts">{parts}</table>'
                f'<div class="literal">“{literal}”</div><div class="definition">{definition}</div></div>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<!doctype html><html><head><meta charset='utf-8'>"
                    f"<style>{CSS}</style></head><body class='card'>" + "".join(blocks) + "</body></html>")
    print(f"preview: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="write an HTML preview to this path")
    ap.add_argument("--only", help="only build entries matching this regex (for testing)")
    args = ap.parse_args()
    build(args.html, args.only)
