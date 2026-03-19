import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(__file__))

from path_utils import looks_like_sequence_path, normalize_sequence_load_path


class PathUtilsTest(unittest.TestCase):
    def test_unc_hash_sequence_normalizes_to_brace(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file.####.exr=1001-1010"),
            "//server/share/my_file.{:04d}.exr=1001-1010",
        )

    def test_unc_percent_sequence_normalizes_to_brace(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file_%04d.exr=1001-1010"),
            "//server/share/my_file_{:04d}.exr=1001-1010",
        )

    def test_prefix_range_sequence_normalizes_to_brace(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file.1001-1010#.exr"),
            "//server/share/my_file.{:04d}.exr=1001-1010",
        )

    def test_prefix_range_brace_sequence_moves_range_to_suffix(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file.1001-1010{:04d}.exr"),
            "//server/share/my_file.{:04d}.exr=1001-1010",
        )

    def test_existing_brace_sequence_is_left_alone(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file.{:04d}.exr=1001-1010"),
            "//server/share/my_file.{:04d}.exr=1001-1010",
        )

    def test_plain_file_is_not_treated_as_sequence(self):
        self.assertIsNone(normalize_sequence_load_path("//server/share/my_file_v001.exr"))
        self.assertFalse(looks_like_sequence_path("//server/share/my_file_v001.exr"))

    def test_sequence_without_range_still_normalizes(self):
        self.assertEqual(
            normalize_sequence_load_path("//server/share/my_file_%04d.exr"),
            "//server/share/my_file_{:04d}.exr",
        )


if __name__ == "__main__":
    unittest.main()
