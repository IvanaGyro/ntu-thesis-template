from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fontTools.ttLib import TTCollection, TTFont


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import font_files  # noqa: E402


class FontFileTests(unittest.TestCase):
    def test_local_file_wins_and_explicit_index_travels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "fonts/english/Local.ttf"
            target.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "fonts/english/Tinos-Regular.ttf", target)
            resolved = font_files.resolve_font(root, "fonts/english", "Local.ttf", 0)
            self.assertEqual(resolved.path, target)
            self.assertEqual(resolved.index, 0)

    def test_collection_index_opens_the_requested_face(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            collection_path = Path(directory) / "pair.ttc"
            collection = TTCollection()
            collection.fonts = [
                TTFont(ROOT / "fonts/english/Tinos-Regular.ttf"),
                TTFont(ROOT / "fonts/english/Tinos-Bold.ttf"),
            ]
            try:
                collection.save(collection_path)
            finally:
                collection.close()
            names = font_files.font_names(font_files.FontFile(collection_path, 1))
            self.assertIn("Tinos Bold", names)

    def test_fontconfig_tab_and_two_line_formats(self) -> None:
        path = ROOT / "fonts/english/Tinos-Regular.ttf"
        self.assertEqual(
            font_files._parse_fc_match(f"{path}\t0\n"),
            font_files.FontFile(path, 0),
        )
        self.assertEqual(
            font_files._parse_fc_match(f"{path}\n1\n"),
            font_files.FontFile(path, 1),
        )

    def test_fontconfig_format_fallback(self) -> None:
        path = ROOT / "fonts/english/Tinos-Regular.ttf"
        results = [
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            SimpleNamespace(returncode=0, stdout=f"{path}\n0\n", stderr=""),
        ]
        with patch("font_files.subprocess.run", side_effect=results) as run:
            self.assertEqual(font_files.fontconfig_match("Tinos"), font_files.FontFile(path))
            self.assertEqual(run.call_count, 2)

    def test_fontconfig_relative_windows_path_preserves_its_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            font_dir = Path(directory)
            path = font_dir / "Tinos-Regular.ttf"
            shutil.copy2(ROOT / "fonts/english/Tinos-Regular.ttf", path)
            result = SimpleNamespace(
                returncode=0, stdout="Tinos-Regular.ttf\t0\n", stderr=""
            )
            with (
                patch("font_files.subprocess.run", return_value=result),
                patch(
                    "font_files.windows_font_directories", return_value=(font_dir,)
                ),
            ):
                self.assertEqual(
                    font_files.fontconfig_match("Tinos"), font_files.FontFile(path)
                )

    def test_relative_fontconfig_match_ignores_cwd_decoy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system_dir = root / "system"
            decoy_dir = root / "decoy"
            system_dir.mkdir()
            decoy_dir.mkdir()
            source = ROOT / "fonts/english/Tinos-Regular.ttf"
            system_font = system_dir / source.name
            shutil.copy2(source, system_font)
            shutil.copy2(ROOT / "fonts/english/Tinos-Bold.ttf", decoy_dir / source.name)
            original_cwd = Path.cwd()
            try:
                os.chdir(decoy_dir)
                self.assertEqual(
                    font_files._parse_fc_match(
                        f"{source.name}\t0\n", (system_dir,)
                    ),
                    font_files.FontFile(system_font),
                )
            finally:
                os.chdir(original_cwd)

    def test_fontconfig_substitution_is_rejected(self) -> None:
        tinos = font_files.FontFile(ROOT / "fonts/english/Tinos-Regular.ttf")
        with (
            patch("font_files.fontconfig_match", return_value=tinos),
            patch("font_files.windows_font_directories", return_value=()),
        ):
            self.assertIsNone(font_files.system_font("Definitely Missing Family"))

    def test_directory_scan_prefers_regular_face(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / "fonts/english/Tinos-Bold.ttf", root / "A-Bold.ttf")
            shutil.copy2(ROOT / "fonts/english/Tinos-Regular.ttf", root / "Z-Regular.ttf")
            match = font_files.directory_match("Tinos", (root,))
            self.assertIsNotNone(match)
            self.assertEqual(match.path.name, "Z-Regular.ttf")

    def test_directory_scan_prefers_weight_400_when_regular_bits_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ROOT / "fonts/english/Tinos-Regular.ttf"
            for filename, weight in (("A-Light.ttf", 300), ("Z-Regular.ttf", 400)):
                target = root / filename
                with TTFont(source) as font:
                    font["OS/2"].fsSelection = 0
                    font["OS/2"].usWeightClass = weight
                    font.save(target)
            match = font_files.directory_match("Tinos", (root,))
            self.assertIsNotNone(match)
            self.assertEqual(match.path.name, "Z-Regular.ttf")


if __name__ == "__main__":
    unittest.main()
