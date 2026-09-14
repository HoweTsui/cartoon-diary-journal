import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

SKILL = Path(__file__).resolve().parents[1]
PACKAGE = SKILL / "assets/diary-reader-v3"
spec = importlib.util.spec_from_file_location("reader_export", SKILL / "scripts/build_diary_reader.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReaderExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="diary-reader-tests-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "task-output/export"
        self.data = {
            "schemaVersion": 1, "book": {"id": "test", "title": "测试", "coverSrc": "cover.svg"},
            "periods": [{"id": "week", "title": "一周"}],
            "entries": [{"id": "one", "date": "2026-08-17", "title": "一天",
                         "periodId": "week", "posterSrc": "poster.svg", "characterIds": ["a"]}],
            "characters": [{"id": "a", "name": "阿纸", "avatarSrc": "avatar.svg"}]
        }
        for name in ("cover.svg", "poster.svg", "avatar.svg"):
            (self.source / name).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="40"/>')

    def tearDown(self):
        self.temp.cleanup()

    def write_index(self):
        path = self.source / "index.html"
        path.write_text("<script type='application/json' id='diary-book-data'>"
                        + json.dumps(self.data, ensure_ascii=False) + "</script>", encoding="utf-8")
        return path

    def test_export_and_original_bytes(self):
        index = self.write_index()
        before = {p.name: p.read_bytes() for p in self.source.iterdir()}
        result = reader.export_reader(index, self.output)
        self.assertEqual(result["entries"], 1)
        self.assertEqual(result["assets"], 3)
        self.assertTrue((self.output / "fonts/Yozai-Regular.ttf").is_file())
        self.assertTrue((self.output / "fonts/Yozai-Medium.ttf").is_file())
        self.assertTrue((self.output / "THIRD_PARTY_NOTICES.md").is_file())
        for name, value in before.items():
            self.assertEqual((self.source / name).read_bytes(), value)
            if name.endswith(".svg"):
                self.assertEqual((self.output / "data" / name).read_bytes(), value)

    def test_missing_dates_become_date_only_blank_entries(self):
        self.data["entries"].append({"id": "three", "date": "2026-08-19", "title": "第三天",
                                     "periodId": "week", "posterSrc": "poster.svg", "characterIds": []})
        result = reader.export_reader(self.write_index(), self.output)
        manifest = json.loads((self.output / "data/manifest.json").read_text())
        self.assertEqual(result["blankDays"], 1)
        self.assertEqual([entry["date"] for entry in manifest["entries"]],
                         ["2026-08-17", "2026-08-18", "2026-08-19"])
        blank = manifest["entries"][1]
        self.assertEqual(blank["id"], "blank-2026-08-18")
        self.assertTrue(blank["isBlank"])
        self.assertEqual(blank["posterSrc"], "")

    def test_duplicate_date_is_rejected(self):
        self.data["entries"].append({"id": "duplicate", "date": "2026-08-17", "title": "第二篇",
                                     "periodId": "week", "posterSrc": "poster.svg", "characterIds": []})
        with self.assertRaisesRegex(ValueError, "one diary"):
            reader.export_reader(self.write_index(), self.output)

    def test_missing_file_leaves_no_export(self):
        self.data["entries"][0]["posterSrc"] = "missing.png"
        with self.assertRaisesRegex(ValueError, "Missing asset"):
            reader.export_reader(self.write_index(), self.output)
        self.assertFalse(self.output.exists())

    def test_reject_escape_urls_and_symlink(self):
        outside = self.root / "outside.svg"
        outside.write_text("<svg/>")
        (self.source / "link.svg").symlink_to(outside)
        for path in ("../outside.svg", "%2e%2e/outside.svg", "..%5coutside.svg",
                     str(outside), "https://example.invalid/a.png", "//example.invalid/a.png",
                     "poster.svg?x=1", "poster.svg#id", "link.svg"):
            with self.subTest(path=path):
                self.data["entries"][0]["posterSrc"] = path
                with self.assertRaises(ValueError):
                    reader.export_reader(self.write_index(), self.output)
                self.assertFalse(self.output.exists())

    def test_output_cannot_overwrite_or_use_source(self):
        index = self.write_index()
        reader.export_reader(index, self.output)
        sentinel = self.output / "sentinel"
        sentinel.write_text("keep")
        with self.assertRaises(ValueError):
            reader.export_reader(index, self.output)
        self.assertEqual(sentinel.read_text(), "keep")
        with self.assertRaises(ValueError):
            reader.export_reader(index, self.source / "task-output/new")
        with self.assertRaises(ValueError):
            reader.export_reader(index, self.root / "not-task-output")

    def test_utf8_and_space_paths_are_url_encoded(self):
        (self.source / "一 页.svg").write_text("<svg/>")
        self.data["entries"][0]["posterSrc"] = "一 页.svg"
        reader.export_reader(self.write_index(), self.output)
        manifest = json.loads((self.output / "data/manifest.json").read_text())
        path = manifest["entries"][0]["posterSrc"]
        self.assertEqual(unquote(path), "一 页.svg")
        self.assertNotIn(" ", path)
        self.assertTrue((self.output / "data" / unquote(path)).exists())

    def test_invalid_schema_and_duplicate_script(self):
        self.data["entries"][0]["periodId"] = "unknown"
        with self.assertRaises(ValueError):
            reader.export_reader(self.write_index(), self.output)
        index = self.write_index()
        index.write_text(index.read_text() * 2)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            reader.export_reader(index, self.output)

    def check_existing(self, index, expected):
        if not index.exists():
            self.skipTest("Optional source book is not present in this checkout")
        original = reader.read_manifest(index)
        result = reader.export_reader(index, self.output)
        exported = json.loads((self.output / "data/manifest.json").read_text())
        actual_entries = [entry for entry in exported["entries"] if not entry.get("isBlank")]
        self.assertEqual(len(actual_entries), expected)
        self.assertEqual([e["id"] for e in original["entries"]],
                         [e["id"] for e in actual_entries])
        self.assertEqual(result["entries"], expected + result["blankDays"])
        for before, after in zip(original["entries"], actual_entries):
            self.assertEqual((index.parent / unquote(before["posterSrc"])).read_bytes(),
                             (self.output / "data" / unquote(after["posterSrc"])).read_bytes())

    def test_existing_eight_entry_demo(self):
        self.check_existing(SKILL / "assets/diary-book/demo/index.html", 8)

    def test_existing_three_imagegen_entries(self):
        self.check_existing(SKILL.parents[1] / "cartoon-diary-journal/task-output/simulated-imagegen-book/index.html", 3)

    def test_publish_runtime_has_no_content_or_dependencies(self):
        self.assertFalse((reader.RUNTIME / "data").exists())
        for path in PACKAGE.rglob("*"):
            if ".qa-" in str(path):
                continue
            self.assertNotIn(path.name, {"node_modules", "review", "manifest.json"})
        self.assertTrue((reader.RUNTIME / "index.html").is_file())

    def test_static_reader_fallback_remains_available_without_webgl(self):
        bootstrap = (PACKAGE / "source/src/bootstrap.js").read_text(encoding="utf-8")
        reader_source = (PACKAGE / "source/src/reader.js").read_text(encoding="utf-8")
        styles = (PACKAGE / "source/src/style.css").read_text(encoding="utf-8")
        self.assertIn("enableStaticReader", bootstrap)
        self.assertIn("static-reader", reader_source)
        self.assertIn("static-reader", styles)


if __name__ == "__main__":
    unittest.main()
