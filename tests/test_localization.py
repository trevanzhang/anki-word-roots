"""Check translation coverage and the generated package, not just display strings."""

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from word_roots import build
from word_roots.localize import Locale, bilingual


class LocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.morphemes = build.read("morphemes.csv")
        cls.stories = build.read("stories.csv")
        cls.decode = build.read("decode.csv")

    def test_complete_translation_coverage(self):
        Locale("zh-CN").validate(self.morphemes, self.stories, self.decode)

    def test_changed_source_requires_review(self):
        changed = [dict(row) for row in self.morphemes]
        changed[0]["meaning"] = "new sense"
        with self.assertRaisesRegex(SystemExit, "English source changed"):
            Locale("zh-CN").validate(changed, self.stories, self.decode)

    def test_missing_translation_fails_instead_of_silent_fallback(self):
        locale = Locale("zh-CN")
        del locale.data["decode"][self.decode[0]["word"]]
        with self.assertRaisesRegex(SystemExit, "missing incredible"):
            locale.validate(self.morphemes, self.stories, self.decode)

    def test_missing_segment_translation_fails(self):
        locale = Locale("zh-CN")
        del locale.data["glosses"]["not"]
        with self.assertRaisesRegex(SystemExit, "glosses changed"):
            locale.validate(self.morphemes, self.stories, self.decode)

    def test_plain_translations_are_html_escaped(self):
        self.assertIn("&lt;script&gt;", bilingual("中文<script>", "a & b"))
        self.assertNotIn("<script>", bilingual("中文<script>", "a & b"))

    def test_packages_coexist_and_previews_match_templates(self):
        snapshots = {}
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            with patch.object(build, "DIST", folder), contextlib.redirect_stdout(io.StringIO()):
                for lang in ("en", "zh-CN"):
                    preview = folder / f"{lang}.html"
                    package = build.build(preview, language=lang)
                    with zipfile.ZipFile(package) as archive:
                        db = folder / f"{lang}.anki2"
                        db.write_bytes(archive.read("collection.anki2"))
                    with contextlib.closing(sqlite3.connect(db)) as conn:
                        models, decks = conn.execute("select models, decks from col").fetchone()
                        models, decks = json.loads(models), json.loads(decks)
                        notes = conn.execute("select guid, mid, flds, tags from notes").fetchall()
                        cards = conn.execute("select nid, due from cards").fetchall()
                    self.assertEqual(len(notes), 922)
                    self.assertEqual(len(cards), 922)
                    self.assertEqual(len({r[0] for r in notes}), 922)
                    self.assertEqual(sorted(r[1] for r in cards), list(range(1, 923)))
                    self.assertEqual(sum("WR::Core" in r[3] for r in notes), 123)
                    self.assertEqual(sum("WR::Story" in r[3] for r in notes), 77)
                    self.assertEqual(sum("WR::Decode" in r[3] for r in notes), 222)
                    self.assertEqual(sum("WR::Medical " in r[3] for r in notes), 204)
                    text = preview.read_text(encoding="utf-8")
                    self.assertEqual(text.count('<article class="preview-note"'), 922)
                    self.assertNotIn("{{", text)
                    if lang == "zh-CN":
                        self.assertIn("突出显示的部分是什么意思", text)
                        self.assertIn("不等于现代词义", text)
                        self.assertIn("拉丁语与希腊语", text)
                        self.assertTrue(all("lang=\"zh-Hans\"" in row[2] for row in notes))
                        self.assertTrue(all("· 医学词汇" in m["tmpls"][0]["qfmt"] for m in models.values()))
                    snapshots[lang] = (models, decks, notes)
            english, chinese = snapshots["en"], snapshots["zh-CN"]
            self.assertTrue(set(english[0]).isdisjoint(chinese[0]))
            self.assertTrue({r[0] for r in english[2]}.isdisjoint(r[0] for r in chinese[2]))
            en_decks = {v["name"] for v in english[1].values()}
            zh_decks = {v["name"] for v in chinese[1].values()}
            self.assertIn("Word Roots", en_decks)
            self.assertIn("Word Roots 中文", zh_decks)
            # English note GUIDs remain compatible with upstream.
            self.assertIn(build.genanki.guid_for("wr", self.morphemes[0]["id"]),
                          {row[0] for row in english[2]})
            root, decode = Locale("zh-CN").models(build.ROOT_MODEL, build.DECODE_MODEL)
            self.assertEqual(root.model_id, 1730581412)
            self.assertEqual(decode.model_id, 1730581413)
            self.assertEqual(build.ROOT_MODEL.model_id, 1730581402)
            self.assertEqual(build.DECODE_MODEL.model_id, 1730581403)


if __name__ == "__main__":
    unittest.main()
