"""Build the Word Roots Anki deck.

    uv run python word_roots/build.py              # -> dist/Word_Roots_zh-CN.apkg
    uv run python word_roots/build.py --lang en    # -> dist/Word_Roots.apkg
    uv run python word_roots/build.py --html X     # preview every question and answer

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

try:  # supports both direct execution and imports in tests
    from .localize import Locale
except ImportError:
    from localize import Locale

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

ZH_DESCRIPTION = (
    "希腊语和拉丁语词根、前缀与后缀的简体中文对照版。先学 123 个核心词素，再逐步扩展；"
    "通过熟悉的英文例词回忆含义，再用拆词卡练习。<b>评分：</b>记住核心含义即可，"
    "无需逐字复述或背诵词源故事。<b>顺序：</b>新卡片收集顺序选择“位置升序”"
    "（Ascending position），排序选择“按收集顺序”（Order gathered）。"
    "可暂停 <code>tag:WR::Medical</code> 下的专业医学词汇。"
    "<b>说明：</b>构词直译仅解释历史构词关系，不替代现代词义，也不表示所有词都能按字面猜出。"
    "中文是对英文学习材料的翻译，不是独立的词源考证或医学审定。"
    "原版：jupsh/anki-word-roots；中文分支：trevanzhang/anki-word-roots。"
    "原始数据改编自 Wikipedia 的希腊语、拉丁语及医学词根列表；本译作继续使用 CC BY-SA 4.0。"
)


# --------------------------------------------------------------------------- helpers

def read(name):
    with (DATA / name).open(encoding="utf-8", newline="") as fh:
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


def story_html(row, locale=None):
    locale = locale or Locale()
    label = "来源" if locale.chinese else "source"
    link = f' <a class="src" href="{html.escape(row["source"], quote=True)}">{label}</a>' if row.get("source") else ""
    return locale.story(row) + link


def decode_fields(d, morphemes, index, locale=None):
    """A decode note's fields, and the study position of the last morpheme it uses."""
    locale = locale or Locale()
    rows, last = [], 0
    for seg, mid, gloss in parse_parts(d, index):
        if mid:
            last = max(last, index[mid])
            meaning = morphemes[index[mid]]["meaning"]
            root = (f'<div class="rootm">{html.escape(morphemes[index[mid]]["forms"])} '
                    f'{locale.meaning(morphemes[index[mid]])}</div>') if gloss and gloss != meaning else ""
            explanation = locale.gloss(gloss) if gloss else locale.meaning(morphemes[index[mid]])
            rows.append(f'<tr><td class="seg">{html.escape(seg)}</td>'
                        f'<td>{explanation}{root}</td></tr>')
        else:
            rows.append(f'<tr><td class="plain">{html.escape(seg)}</td>'
                        f'<td class="plain-gloss">{locale.gloss(gloss)}</td></tr>')
    fields = [d["word"], "".join(rows), locale.decode_text(d, "literal"), locale.decode_text(d, "definition"),
              "y" if d["medical"] else ""]
    return fields, last


def bare_forms(m):
    """'scler(o)-, -sclerosis' -> {'scler', 'sclero', 'sclerosis'}"""
    out = set()
    for f in m["forms"].split(","):
        f = f.strip(" -").lower()
        out |= {re.sub(r"\((\w+)\)", "", f), re.sub(r"\((\w+)\)", r"\1", f)}
    return out


INFLECTIONS = {"s", "es", "ed", "ing", "ly", "ally"}


def check_highlights(morphemes, decode, index):
    """The etymology check looks at whole words, so check where the highlight sits.

    A prefix's highlight must start the word, after nothing but another morpheme (in[trans]igent);
    a suffix's must end it, before nothing but another suffix or an inflection. And two
    morphemes may not claim the same letters of one word: illum[in]ate under in- clashes
    with il[lumin]ate. Nesting is fine (dia[gno]sis inside dia[gnosis])."""
    known = set().union(*(bare_forms(m) for m in morphemes))
    known |= {f + "o" for f in known}
    errors, spans = [], {}
    for m in morphemes:
        for field in ("front", "more"):
            for w in filter(None, (x.strip() for x in m[field].split(";"))):
                found = re.fullmatch(r"([^\[\]]*)\[([^\[\]]+)\]([^\[\]]*)", w)
                if not found:
                    errors.append(f"{m['id']}: {w!r} needs exactly one [highlight]")
                    continue
                pre, seg, post = found.groups()
                if m["kind"] == "prefix" and pre and pre.lower() not in known:
                    errors.append(f"{m['id']}: prefix highlighted mid-word in {w!r}")
                if m["kind"] == "suffix" and post and post.lower() not in known | INFLECTIONS:
                    errors.append(f"{m['id']}: suffix highlighted mid-word in {w!r}")
                spans.setdefault((pre + seg + post).lower(), []).append(
                    (len(pre), len(pre) + len(seg), m["id"], w))
    for d in decode:
        at = 0
        for seg, mid, _ in parse_parts(d, index):
            if mid:
                spans.setdefault(d["word"].lower(), []).append((at, at + len(seg), mid, "decode"))
            at += len(seg)
    for word, ss in spans.items():
        for i, (a0, a1, aid, aw) in enumerate(ss):
            for b0, b1, bid, bw in ss[i + 1:]:
                overlap = min(a1, b1) - max(a0, b0)
                nested = (a0 <= b0 and b1 <= a1) or (b0 <= a0 and a1 <= b1)
                # one shared letter is a connecting vowel or elision: [deca]thlon, dec[athl]on
                if aid != bid and ((a0, a1) == (b0, b1) or (overlap > 1 and not nested)):
                    errors.append(f"{word}: {aid} ({aw}) and {bid} ({bw}) highlight the same letters")
    if errors:
        raise SystemExit("highlighting:\n  " + "\n  ".join(errors))


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
    check_highlights(morphemes, decode, index)


def build(html_out=None, only=None, language="zh-CN"):
    locale = Locale(language)
    morphemes = read("morphemes.csv")
    story_rows = read("stories.csv")
    decode = read("decode.csv")
    index = {m["id"]: i for i, m in enumerate(morphemes)}
    validate(morphemes, story_rows, decode, index)
    locale.validate(morphemes, story_rows, decode)
    stories = {r["id"]: story_html(r, locale) for r in story_rows}
    root_model, decode_model = locale.models(ROOT_MODEL, DECODE_MODEL)
    name = "Word Roots 中文" if locale.chinese else DECK_NAME
    description = ZH_DESCRIPTION if locale.chinese else DECK_DESCRIPTION
    filename = "Word_Roots_zh-CN.apkg" if locale.chinese else "Word_Roots.apkg"
    guid_root, guid_decode = (("wr-zh-CN", "wr-decode-zh-CN") if locale.chinese
                             else ("wr", "wr-decode"))

    deck = genanki.Deck(deck_id(name), name, description=description)
    notes, preview = [], []

    for i, m in enumerate(morphemes):
        if only and not re.search(only, m["forms"] + " " + m["meaning"], re.I):
            continue
        kind = m["kind"].capitalize()
        lang = m["language"] or "Latin/Greek"
        display_kind = {"root": "词根", "prefix": "前缀", "suffix": "后缀"}[m["kind"]] if locale.chinese else m["kind"]
        display_lang = {"Latin": "拉丁语", "Greek": "希腊语", "English": "英语", "Latin/Greek": "拉丁语／希腊语", "Latin and Greek": "拉丁语与希腊语"}.get(lang, lang) if locale.chinese else lang
        origin = ("词源原文：" if locale.chinese else "") + m["origin"]
        fields = [html.escape(m["forms"]), locale.meaning(m), display_kind, m["kind"], display_lang,
                  html.escape(origin), word_list(m["front"]),
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
        notes.append((i * 10, genanki.Note(model=root_model, fields=fields, tags=tags,
                                           guid=genanki.guid_for(guid_root, m["id"]))))
        preview.append(("root", fields))

    for d in decode:
        if only and not re.search(only, d["word"], re.I):
            continue
        fields, last = decode_fields(d, morphemes, index, locale)
        tags = ["WR::Decode"] + (["WR::Medical"] if d["medical"] else [])
        notes.append(((last + DECODE_DELAY) * 10 + 5,
                      genanki.Note(model=decode_model, fields=fields, tags=tags,
                                   guid=genanki.guid_for(guid_decode, d["word"]))))
        preview.append(("decode", fields))

    for due, (_, note) in enumerate(sorted(notes, key=lambda x: x[0]), 1):
        note.due = due
        deck.add_note(note)

    out = (ROOT / "build" if only else DIST) / filename  # partial builds stay out of dist/
    out.parent.mkdir(parents=True, exist_ok=True)
    genanki.Package(deck).write_to_file(out)
    n_root = sum(1 for k, _ in preview if k == "root")
    print(f"wrote {out}  ({n_root} morphemes, {len(preview) - n_root} decode words, "
          f"{sum(1 for k, f in preview if k == 'root' and f[8])} stories)")
    if html_out:
        write_preview(Path(html_out), preview, root_model, decode_model, language)
    return out


def render_template(template, fields):
    """Render the simple Anki fields/conditionals used by these models for preview."""
    template = re.sub(r"{{#(\w+)}}(.*?){{/\1}}",
                      lambda m: m[2] if fields.get(m[1]) else "", template, flags=re.S)
    return re.sub(r"{{(\w+)}}", lambda m: fields[m[1]], template)


def write_preview(path, preview, root_model, decode_model, language):
    """Preview the actual model templates, including both question and answer."""
    chinese = language == "zh-CN"
    title = "Word Roots 中文 · 卡片预览" if chinese else "Word Roots · Card preview"
    front, back = ("正面", "背面") if chinese else ("Front", "Back")
    blocks = []
    for number, (kind, values) in enumerate(preview, 1):
        model = root_model if kind == "root" else decode_model
        fields = dict(zip((f["name"] for f in model.fields), values))
        template = model.templates[0]
        question = render_template(template["qfmt"], fields)
        answer = render_template(template["afmt"], fields)
        blocks.append(f'<article class="preview-note" id="note-{number}">'
                      f'<section><h2>{number} · {front}</h2>{question}</section>'
                      f'<section><h2>{back}</h2>{answer}</section></article>')
    preview_css = """
.preview-note { max-width: 1300px; margin: 20px auto; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.preview-note section { min-width: 0; border: 1px solid #d1d5db; border-radius: 8px; }
.preview-note h2 { font-size: 14px; color: #6b7280; text-align: left; margin: 12px 16px 0; }
h1 { font-size: 24px; margin: 24px 16px; }
@media (max-width: 720px) { .preview-note { grid-template-columns: 1fr; margin: 16px 8px; } }
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<!doctype html><html lang="{"zh-Hans" if chinese else "en"}"><head>'
                    '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                    f'<title>{title}</title><style>{root_model.css}{preview_css}</style></head>'
                    f'<body class="card"><h1>{title}</h1>' + "".join(blocks) + "</body></html>",
                    encoding="utf-8")
    print(f"preview: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="write an HTML preview to this path")
    ap.add_argument("--only", help="only build entries matching this regex (for testing)")
    ap.add_argument("--lang", choices=("en", "zh-CN"), default="zh-CN", help="deck language (default: zh-CN)")
    args = ap.parse_args()
    build(args.html, args.only, args.lang)
