"""Chinese translations are an overlay; upstream CSVs stay unchanged."""

import copy
import html
import json
import re
from pathlib import Path

LOCALES = Path(__file__).parent / "locales"


def bilingual(zh, en, *, rich=False):
    """Only curated story HTML is rich text; ordinary translations are escaped."""
    if not rich:
        zh, en = html.escape(zh), html.escape(en)
    return (f'<span class="zh" lang="zh-Hans">{zh}</span>'
            f'<span class="en" lang="en">{en}</span>')


class Locale:
    def __init__(self, language="en"):
        if language not in ("en", "zh-CN"):
            raise ValueError(f"unsupported language: {language}")
        self.chinese = language == "zh-CN"
        self.language = language
        self.data = (json.loads((LOCALES / "zh-CN.json").read_text(encoding="utf-8"))
                     if self.chinese else {})

    def validate(self, morphemes, stories, decode):
        if not self.chinese:
            return
        errors = []
        for section, rows, key, fields in (
            ("morphemes", morphemes, "id", ("meaning",)),
            ("stories", stories, "id", ("story",)),
            ("decode", decode, "word", ("literal", "definition")),
        ):
            translations = self.data[section]
            expected = {r[key] for r in rows}
            for missing in sorted(expected - translations.keys()):
                errors.append(f"{section}: missing {missing}")
            for extra in sorted(translations.keys() - expected):
                errors.append(f"{section}: unknown {extra}")
            for row in rows:
                entry = translations.get(row[key])
                if not entry:
                    continue
                for field in fields:
                    if entry.get(field) != row[field]:
                        errors.append(f"{section}/{row[key]}/{field}: English source changed; review translation")
                    target = field + "_zh" if section == "decode" else "zh"
                    if not re.search(r"[\u3400-\u9fff]", entry.get(target, "")):
                        errors.append(f"{section}/{row[key]}/{target}: Chinese translation missing")
        glosses = {p.partition(":")[2] for d in decode for p in d["parts"].split(" + ") if ":" in p}
        if glosses != self.data["glosses"].keys():
            errors.append("decode glosses changed; review Chinese gloss translations")
        for source, target in self.data["glosses"].items():
            if not re.search(r"[\u3400-\u9fff]", target):
                errors.append(f"Chinese gloss missing: {source}")
        if errors:
            raise SystemExit("zh-CN translations:\n  " + "\n  ".join(errors))

    def meaning(self, morpheme):
        if not self.chinese:
            return html.escape(morpheme["meaning"])
        return bilingual(self.data["morphemes"][morpheme["id"]]["zh"], morpheme["meaning"])

    def gloss(self, english):
        return (bilingual(self.data["glosses"][english], english) if self.chinese
                else html.escape(english))

    def story(self, row):
        return (bilingual(self.data["stories"][row["id"]]["zh"], row["story"], rich=True)
                if self.chinese else row["story"])

    def decode_text(self, row, field):
        return (bilingual(self.data["decode"][row["word"]][field + "_zh"], row[field])
                if self.chinese else html.escape(row[field]))

    def models(self, root, decode):
        if not self.chinese:
            return root, decode
        # Distinct model IDs and note GUID namespaces let both editions coexist.
        root, decode = copy.deepcopy(root), copy.deepcopy(decode)
        root.model_id, decode.model_id = 1730581412, 1730581413
        root.name, decode.name = "Word Roots 中文 · 词根词缀", "Word Roots 中文 · 拆词练习"
        replacements = {
            "· medical": "· 医学词汇",
            "What does the highlighted part mean?": "突出显示的部分是什么意思？",
            "Break it into parts. What does it literally mean?": "把单词拆成几个部分，试着说出各部分的含义。",
            '<div class="label">Decode': '<div class="label">拆词练习',
            '<div class="literal">“{{Literal}}”</div>':
                '<div class="section-label">按构词成分直译 · 不等于现代词义</div>'
                '<div class="literal">{{Literal}}</div>',
            '<div class="definition">{{Definition}}</div>':
                '<div class="section-label">现代词义</div><div class="definition">{{Definition}}</div>',
        }
        for model in (root, decode):
            for template in model.templates:
                template["name"] = "例词 → 含义" if model is root else "拆词练习"
                for side in ("qfmt", "afmt"):
                    for source, target in replacements.items():
                        template[side] = template[side].replace(source, target)
            model.css += """
.card { font-family: -apple-system, 'Segoe UI', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif; }
.label { text-transform: none; letter-spacing: .02em; }
.zh { display: block; }
.en { display: block; font-size: .78em; font-weight: 400; color: #6b7280; margin-top: 2px; }
.story .en { margin-top: 10px; font-size: .92em; }
.origin { overflow-wrap: anywhere; }
.section-label { font-size: .7em; color: #6b7280; margin-top: 12px; }
.nightMode .en, .night_mode .en, .nightMode .section-label, .night_mode .section-label { color: #9ca3af; }
"""
        return root, decode
