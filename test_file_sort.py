"""Unit tests for file-sort.py.

These tests build a fake iCloud Documents tree in a temp directory, patch
DOCUMENTS_BASE_PATH at the module level, and mock the `call_claude` wrapper
so no real `claude -p` invocation happens. Run with:

    python3 -m unittest test_file_sort.py -v
"""
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# The script's filename has a hyphen so we can't `import file-sort` directly.
_SPEC = importlib.util.spec_from_file_location(
    "file_sort", Path(__file__).parent / "file-sort.py"
)
file_sort = importlib.util.module_from_spec(_SPEC)
sys.modules["file_sort"] = file_sort
_SPEC.loader.exec_module(file_sort)


class TestDetectSubfolderPattern(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_all_years_returns_year(self):
        for y in ["2023", "2024", "2025"]:
            (self.tmp / y).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "year")

    def test_all_proper_names_returns_name(self):
        for n in ["Anthony", "Hannah", "Oliver", "Roman"]:
            (self.tmp / n).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "name")

    def test_mixed_children_returns_strict(self):
        for n in ["HOA", "Electric", "Gas", "Water"]:
            (self.tmp / n).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "strict")

    def test_single_child_returns_strict(self):
        # One sibling is not enough evidence to call it a pattern.
        (self.tmp / "Anthony").mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "strict")

    def test_empty_returns_strict(self):
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "strict")

    def test_ignores_hidden_folders(self):
        (self.tmp / ".DS_Store_dir").mkdir()
        for y in ["2023", "2024"]:
            (self.tmp / y).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "year")

    def test_all_caps_sibling_breaks_name_pattern(self):
        # Caveat: bill-type folders like ["Electric", "Gas", "Water"] all match
        # NAME_RE individually, so without a non-name-like sibling the detector
        # would call this 'name'. An all-caps abbreviation like "HOA" forces
        # 'strict' — this is the user's real-world disambiguator.
        for n in ["HOA", "Electric", "Gas", "Water"]:
            (self.tmp / n).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "strict")

    def test_without_disambiguator_bill_types_misread_as_names(self):
        # Documents the known limitation: pure single-cap-word siblings are
        # indistinguishable from person names. The detector will return 'name'.
        for n in ["Electric", "Gas", "Water"]:
            (self.tmp / n).mkdir()
        self.assertEqual(file_sort.detect_subfolder_pattern(self.tmp), "name")


class TestValidateDestination(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_existing_path_is_valid(self):
        (self.tmp / "Existing").mkdir()
        self.assertTrue(file_sort.validate_destination(self.tmp / "Existing"))

    def test_new_year_under_year_pattern_is_valid(self):
        receipts = self.tmp / "Receipts"
        receipts.mkdir()
        for y in ["2023", "2024", "2025"]:
            (receipts / y).mkdir()
        self.assertTrue(file_sort.validate_destination(receipts / "2026"))

    def test_new_name_under_name_pattern_is_valid(self):
        medical = self.tmp / "Medical"
        medical.mkdir()
        for n in ["Anthony", "Hannah", "Oliver"]:
            (medical / n).mkdir()
        self.assertTrue(file_sort.validate_destination(medical / "Sophia"))

    def test_new_arbitrary_under_strict_is_invalid(self):
        bills = self.tmp / "Bills"
        bills.mkdir()
        for n in ["HOA", "Electric", "Gas"]:
            (bills / n).mkdir()
        self.assertFalse(file_sort.validate_destination(bills / "Sewage"))

    def test_missing_parent_is_invalid(self):
        self.assertFalse(file_sort.validate_destination(self.tmp / "NoParent" / "Leaf"))

    def test_random_string_under_year_pattern_is_invalid(self):
        receipts = self.tmp / "Receipts"
        receipts.mkdir()
        for y in ["2023", "2024", "2025"]:
            (receipts / y).mkdir()
        self.assertFalse(file_sort.validate_destination(receipts / "NotAYear"))


class TestResponseParsing(unittest.TestCase):
    def test_root_exact_match(self):
        self.assertEqual(
            file_sort.parse_root_response("Financial", ["Financial", "Medical", "Misc."]),
            "Financial",
        )

    def test_root_strips_quotes_and_slash(self):
        self.assertEqual(
            file_sort.parse_root_response('"Financial/"\n', ["Financial", "Medical"]),
            "Financial",
        )

    def test_root_case_insensitive_fallback(self):
        self.assertEqual(
            file_sort.parse_root_response("financial\n", ["Financial", "Medical"]),
            "Financial",
        )

    def test_root_no_match_returns_none(self):
        self.assertIsNone(
            file_sort.parse_root_response("I don't know", ["Financial", "Medical"])
        )

    def test_path_with_root_prefix(self):
        self.assertEqual(
            file_sort.parse_path_response("Financial/Receipts/2026\n", "Financial"),
            "Financial/Receipts/2026",
        )

    def test_path_just_root(self):
        self.assertEqual(
            file_sort.parse_path_response("Financial\n", "Financial"),
            "Financial",
        )

    def test_path_wrong_root_returns_none(self):
        self.assertIsNone(
            file_sort.parse_path_response("Medical/Anthony\n", "Financial")
        )


class TestBuildAnnotatedTree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_year_pattern_annotation_appears(self):
        receipts = self.tmp / "Receipts"
        receipts.mkdir()
        for y in ["2023", "2024", "2025"]:
            (receipts / y).mkdir()
        tree = file_sort.build_annotated_tree(receipts)
        self.assertIn("[year-pattern", tree)
        self.assertIn("2023/", tree)

    def test_name_pattern_annotation_appears(self):
        medical = self.tmp / "Medical"
        medical.mkdir()
        for n in ["Anthony", "Hannah", "Oliver", "Roman"]:
            (medical / n).mkdir()
        tree = file_sort.build_annotated_tree(medical)
        self.assertIn("[name-pattern", tree)

    def test_strict_parent_has_no_annotation(self):
        bills = self.tmp / "Bills"
        bills.mkdir()
        for n in ["HOA", "Electric", "Gas"]:
            (bills / n).mkdir()
        tree = file_sort.build_annotated_tree(bills)
        self.assertNotIn("pattern", tree)


class TestClassifyEndToEnd(unittest.TestCase):
    """End-to-end test of classify_file_category with call_claude mocked."""

    def setUp(self):
        # Fake iCloud Documents tree.
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "00 - Scan Inbox").mkdir()
        (self.tmp / "Misc.").mkdir()

        medical = self.tmp / "Medical"
        medical.mkdir()
        for n in ["Anthony", "Hannah", "Oliver", "Roman"]:
            (medical / n).mkdir()

        financial = self.tmp / "Financial"
        financial.mkdir()
        receipts = financial / "Receipts"
        receipts.mkdir()
        for y in ["2023", "2024", "2025"]:
            (receipts / y).mkdir()
        bills = financial / "Bills"
        bills.mkdir()
        # NOTE: HOA (all-caps abbreviation) is the disambiguator — without it,
        # ["Electric", "Gas", "Water"] would all match NAME_RE and the detector
        # would (incorrectly) treat Bills as a name-pattern parent that accepts
        # new single-word folders. This mirrors the user's real iCloud layout.
        for b in ["HOA", "Electric", "Gas", "Water"]:
            (bills / b).mkdir()

        # Patch the module's path constant and silence logging chatter.
        self.path_patch = patch.object(file_sort, "DOCUMENTS_BASE_PATH", self.tmp)
        self.path_patch.start()
        self.log_patch = patch.object(file_sort, "log_print")
        self.log_patch.start()

    def tearDown(self):
        self.log_patch.stop()
        self.path_patch.stop()
        shutil.rmtree(self.tmp)

    def _mock_claude(self, *responses):
        responses = list(responses)
        return lambda prompt: responses.pop(0)

    def test_existing_subfolder_pick(self):
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude("Medical", "Medical/Oliver"),
        ):
            dest = file_sort.classify_file_category(
                "Lab results for Oliver", created_date="2025-06-01"
            )
        self.assertEqual(dest, self.tmp / "Medical" / "Oliver")

    def test_new_year_auto_create(self):
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude("Financial", "Financial/Receipts/2026"),
        ):
            dest = file_sort.classify_file_category(
                "Receipt for purchase", created_date="2026-02-14"
            )
        self.assertEqual(dest, self.tmp / "Financial" / "Receipts" / "2026")

    def test_new_person_auto_create(self):
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude("Medical", "Medical/Sophia"),
        ):
            dest = file_sort.classify_file_category(
                "Lab results for Sophia", created_date="2025-06-01"
            )
        self.assertEqual(dest, self.tmp / "Medical" / "Sophia")

    def test_invalid_strict_folder_falls_back_to_misc(self):
        # Bills children are typed (Electric/Gas/Water) → strict.
        # Sewage is not in the tree, so should fall back to Misc.
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude("Financial", "Financial/Bills/Sewage"),
        ):
            dest = file_sort.classify_file_category(
                "Some random doc", created_date="2025-06-01"
            )
        self.assertEqual(dest, self.tmp / "Misc.")

    def test_stage_one_failure_falls_back(self):
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude(None),
        ):
            dest = file_sort.classify_file_category(
                "Document", created_date="2025-06-01"
            )
        self.assertEqual(dest, self.tmp / "Misc.")

    def test_stage_one_garbage_falls_back(self):
        with patch.object(
            file_sort, "call_claude",
            side_effect=self._mock_claude("not a real folder name at all"),
        ):
            dest = file_sort.classify_file_category(
                "Document", created_date="2025-06-01"
            )
        self.assertEqual(dest, self.tmp / "Misc.")


if __name__ == "__main__":
    unittest.main()
