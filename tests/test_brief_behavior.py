"""Behavior contracts; no generated images and no task-output writes."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_diary_prompt import SKILL_ROOT, build_prompt, geometry, validate_brief
from build_diary_text_layer import build as build_text_layer
from build_diary_book import load_manifest, normalize_manifest

class BriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # Real packaged image; temporary test data only.
        (self.base / "identity.png").write_bytes((SKILL_ROOT / "assets/style-reference/character-lineup-demo.png").read_bytes())
        self.data = {
            "schemaVersion": 2, "kind": "diary", "protagonistId": "p",
            "identity": {"status": "draft", "version": "v1"},
            "characters": [{"id": "p", "name": "示例", "species": "human", "anchors": ["短发", "白衣"]}],
            "references": [{"path": "identity.png", "role": "identity-draft"}],
            "date": "2026-09-09", "title": "雨中借伞", "sourceText": "出门下雨，借到一把伞。",
            "events": [{"scene": "一人借到伞后开心地挥手", "caption": "借伞真及时", "characters": ["p"], "emotion": "happy", "intensity": "medium", "eye_state": "closed_arc", "eyebrows": "none"}]
        }
    def valid(self, preview=True):
        return validate_brief(self.data, self.base, preview)
    def test_unconfirmed_production_blocked(self):
        with self.assertRaisesRegex(ValueError, "unconfirmed"):
            self.valid(False)
    def test_preview_never_approves(self):
        before = copy.deepcopy(self.data)
        self.assertEqual(self.valid()["role"], "draft-preview")
        self.assertEqual(self.data, before)
    def test_fixed_reference_pack_is_auto_attached(self):
        value = self.valid()
        bundled = [item for item in value["references"] if item.get("origin") == "bundled"]
        self.assertEqual(len(bundled), 4)
        self.assertEqual({item["role"] for item in bundled}, {"style", "layout"})
        prompt = build_prompt(value)
        self.assertIn("Mandatory bundled reference pack", prompt)
        self.assertIn("approved-diary-layout-3x4.png", prompt)
    def test_user_photo_requires_archived_compressed_copy(self):
        self.data["references"][0]["origin"] = "user-photo"
        with self.assertRaisesRegex(ValueError, "photoArchive"):
            self.valid()
        archive = self.base / "archive"
        archive.mkdir()
        self.data["references"][0]["path"] = "archive/reference/identity.jpg"
        reference = archive / "reference"
        reference.mkdir()
        (reference / "identity.jpg").write_bytes((SKILL_ROOT / "assets/style-reference/character-lineup-demo.png").read_bytes())
        (archive / "archive-manifest.json").write_text(json.dumps({"schemaVersion": 1, "photos": [{"compressedPath": "reference/identity.jpg"}]}), encoding="utf-8")
        self.data["photoArchive"] = {"manifest": "archive/archive-manifest.json"}
        self.assertEqual(self.valid()["references"][0]["origin"], "user-photo")
    def test_text_layer_uses_local_yozai_and_reserves_caption_lane(self):
        output = self.base / "poster-layer"
        (self.base / "brief.json").write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        anchors = self.base / "anchors.json"
        anchors.write_text(json.dumps({"sceneCenters": [.5]}))
        with self.assertRaisesRegex(ValueError, "--anchors"):
            build_text_layer(self.base / "brief.json", self.base / "identity.png", output, True)
        self.assertFalse(output.exists())
        result = build_text_layer(self.base / "brief.json", self.base / "identity.png", output, True, anchors)
        content = result.read_text(encoding="utf-8")
        self.assertIn('font-family:Yozai', content)
        self.assertIn('id="captions"', content)
        self.assertIn('top:50.00%', content)
        self.assertNotIn('border-left', content)
        self.assertTrue((output / "fonts/Yozai-Regular.ttf").is_file())
    def test_confirmed_version_required(self):
        self.data["identity"] = {"status": "confirmed", "version": "v2", "approvedVersion": "v1", "approvedBy": "user"}
        with self.assertRaisesRegex(ValueError, "approvedVersion"):
            self.valid(False)
    def test_confirmed_production_allowed(self):
        self.data["identity"] = {"status": "confirmed", "version": "v1", "approvedVersion": "v1", "approvedBy": "user"}
        self.data["references"][0]["role"] = "identity-approved"
        self.assertEqual(self.valid(False)["role"], "production")
    def test_onboarding_without_graph(self):
        self.data["kind"] = "onboarding"
        self.data["references"][0]["role"] = "identity-source"
        for field in ("sourceText", "events", "date", "title"):
            del self.data[field]
        self.assertEqual(self.valid()["kind"], "onboarding")
    def test_long_source_preserved_but_not_rendered(self):
        raw = " \n原文独有标记：" + "完整日记内容。" * 1000 + "\n "
        self.data["sourceText"] = raw
        validated = self.valid()
        self.assertEqual(validated["sourceText"], raw)
        prompt = build_prompt(validated)
        self.assertNotIn("原文独有标记", prompt)
        self.assertIn("借伞真及时", prompt)
    def test_missing_authored_fields_blocked(self):
        for key in ("caption", "emotion", "intensity", "eye_state", "eyebrows"):
            with self.subTest(key=key):
                saved = self.data["events"][0].pop(key)
                with self.assertRaises(ValueError):
                    self.valid()
                self.data["events"][0][key] = saved
        del self.data["title"]
        with self.assertRaises(ValueError):
            self.valid()
    def test_text_not_truncated(self):
        for key, text in (("caption", "很" * 11), ("bubble", "很" * 7), ("scene", "很" * 181)):
            with self.subTest(key=key):
                original = copy.deepcopy(self.data)
                self.data["events"][0][key] = text
                with self.assertRaises(ValueError):
                    self.valid()
                self.data = original
    def test_scene_count(self):
        self.data["events"] *= 5
        self.assertEqual(len(self.valid()["events"]), 5)
        self.data["events"].append(copy.deepcopy(self.data["events"][0]))
        with self.assertRaisesRegex(ValueError, "1-5"):
            self.valid()
    def test_identity_and_species(self):
        self.data["protagonistId"] = "absent"
        with self.assertRaisesRegex(ValueError, "protagonistId"):
            self.valid()
        self.data["protagonistId"] = "p"
        self.data["characters"][0]["species"] = "unknown"
        with self.assertRaisesRegex(ValueError, "species"):
            self.valid()
    def test_all_declared_references_checked(self):
        self.data["references"].append({"path": "absent.png", "role": "scene"})
        with self.assertRaisesRegex(ValueError, "missing"):
            self.valid()
    def test_legacy_declared_images_not_ignored(self):
        self.data["events"][0]["sourceImages"] = ["absent.png"]
        with self.assertRaisesRegex(ValueError, "references"):
            self.valid()
    def test_malformed_enum_rejected(self):
        self.data["kind"] = []
        with self.assertRaises(ValueError):
            self.valid()
    def test_relative_path_contract(self):
        for path in ("../identity.png", "/identity.png", "https://example.com/a.png"):
            with self.subTest(path=path):
                self.data["references"][0]["path"] = path
                with self.assertRaises(ValueError):
                    self.valid()
    def test_expression_overrides(self):
        self.data["kind"] = "expression"
        self.data["events"][0].update(eye_state="wide_round", eyebrows="furrowed", emotion="surprise", intensity="strong")
        prompt = build_prompt(self.valid())
        self.assertIn('"eye_state": "wide_round"', prompt)
        self.assertIn('"eyebrows": "furrowed"', prompt)
        self.data["events"][0]["eye_state"] = "heart"
        with self.assertRaises(ValueError):
            self.valid()
    def test_brows_rejected_for_mild_and_medium(self):
        event = self.data["events"][0]
        for intensity in ("mild", "medium"):
            for brows in ("raised", "furrowed"):
                with self.subTest(intensity=intensity, brows=brows):
                    event.update(intensity=intensity, eyebrows=brows)
                    with self.assertRaisesRegex(ValueError, "eyebrows require"):
                        self.valid()

    def test_strong_expression_does_not_require_brows(self):
        event = self.data["events"][0]
        event.update(intensity="strong", eyebrows="none")
        self.assertEqual(self.valid()["events"][0]["eyebrows"], "none")
        event["eyebrows"] = "raised"
        self.assertEqual(self.valid()["events"][0]["eyebrows"], "raised")

    def test_brow_gate_uses_effective_character_expression(self):
        event = self.data["events"][0]
        event["expressions"] = {"p": {"emotion": "surprise", "intensity": "medium", "eye_state": "wide_round", "eyebrows": "raised"}}
        with self.assertRaisesRegex(ValueError, "eyebrows require"):
            self.valid()
        event["expressions"]["p"]["intensity"] = "strong"
        self.assertEqual(self.valid()["events"][0]["expressions"]["p"]["eyebrows"], "raised")
        event.update(intensity="medium", eyebrows="raised")
        event["expressions"]["p"].update(intensity="mild", eyebrows="none")
        self.assertEqual(self.valid()["events"][0]["expressions"]["p"]["eyebrows"], "none")

    def test_feasible_geometry(self):
        g = geometry({})
        self.assertAlmostEqual(g["outerWidth"], 2*g["stroke"]+g["innerGap"])
        self.assertGreater(g["innerGap"], 0)
        self.assertNotEqual(g["cat"], g["dog"])
        with self.assertRaises(ValueError):
            geometry({"geometry": {"outerWidth": .03125}})
        with self.assertRaises(ValueError):
            geometry({"geometry": {"armWidth": .046, "legWidth": .038}})
        with self.assertRaises(ValueError):
            geometry({"geometry": {"stroke": float("nan")}})
    def test_no_iterative_shrink(self):
        first = geometry({})
        self.assertEqual(geometry({"geometry": first}), first)
    def test_cli_preview_and_production_exit_codes(self):
        path = self.base / "brief.json"
        path.write_text(json.dumps(self.data), encoding="utf-8")
        cmd = [sys.executable, str(SKILL_ROOT / "scripts/build_diary_prompt.py"), str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        result = subprocess.run(cmd + ["--preview"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("draft-preview", result.stdout)
    def test_legacy_book_compatibility(self):
        base = SKILL_ROOT / "assets/diary-book/demo"
        book = normalize_manifest(load_manifest(base / "diary-book-data.json"), base / "character-graph.html", base / "index.html")
        self.assertEqual(len(book["entries"]), 8)

    def test_per_character_expression(self):
        self.data["characters"].append({"id": "cat", "name": "猫", "species": "cat", "anchors": ["白猫", "尖耳"]})
        event = self.data["events"][0]
        event["characters"].append("cat")
        event["expressions"] = {"cat": {"emotion": "calm", "intensity": "mild", "eye_state": "neutral_dot", "eyebrows": "none"}}
        value = self.valid()
        self.assertEqual(value["events"][0]["eye_state"], "closed_arc")
        self.assertEqual(value["events"][0]["expressions"]["cat"]["eye_state"], "neutral_dot")
        event["expressions"]["absent"] = event["expressions"]["cat"]
        with self.assertRaises(ValueError):
            self.valid()

if __name__ == "__main__":
    unittest.main()
