from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_line_spacing as spacing  # noqa: E402
from font_files import FontFile  # noqa: E402
from thesis_metadata import (  # noqa: E402
    CollectionError,
    parse_keyval_command,
    parse_keyval_command_raw,
)


LATIN = spacing.FontTableMetrics(
    units_per_em=1000,
    win_ascent=800,
    win_descent=200,
    typo_ascender=700,
    typo_descender=-200,
    typo_line_gap=50,
    hhea_ascender=850,
    hhea_descender=-200,
    hhea_line_gap=50,
    fs_selection=0,
    code_page_range1=0,
    unicode_ranges=(0, 0, 0, 0),
)

SHIPPED_ENGLISH_FONTS = (
    "Tinos-Bold.ttf",
    "Tinos-BoldItalic.ttf",
    "Tinos-Italic.ttf",
    "Tinos-Regular.ttf",
)
SHIPPED_CHINESE_FONTS = ("TW-Kai-98_1.ttf", "TW-Sung-98_1.ttf")


class FormulaTests(unittest.TestCase):
    def test_east_asian_code_page_branch(self) -> None:
        metrics = replace(LATIN, code_page_range1=1 << 20)
        self.assertTrue(spacing.is_east_asian(metrics))
        self.assertEqual(
            spacing.single_line_height(metrics),
            (Fraction(13, 10), "east-asian"),
        )

    def test_east_asian_branch_scales_non_em_win_height(self) -> None:
        metrics = replace(
            LATIN,
            win_ascent=900,
            win_descent=300,
            code_page_range1=1 << 20,
        )
        self.assertEqual(
            spacing.single_line_height(metrics),
            (Fraction(39, 25), "east-asian"),
        )

    def test_east_asian_unicode_fallback(self) -> None:
        # OS/2 Unicode-range bit 59 is bit 27 of ulUnicodeRange2.
        metrics = replace(LATIN, unicode_ranges=(0, 1 << (59 - 32), 0, 0))
        self.assertTrue(spacing.is_east_asian(metrics))
        self.assertEqual(spacing.single_line_height(metrics)[1], "east-asian")

    def test_latin_has_no_east_asian_signal(self) -> None:
        self.assertFalse(spacing.is_east_asian(LATIN))

    def test_east_asian_precedes_use_typo_metrics(self) -> None:
        metrics = replace(
            LATIN,
            code_page_range1=1 << 17,
            fs_selection=spacing.USE_TYPO_METRICS,
            typo_ascender=400,
            typo_descender=-100,
            typo_line_gap=0,
        )
        self.assertEqual(
            spacing.single_line_height(metrics),
            (Fraction(13, 10), "east-asian"),
        )

    def test_use_typo_metrics_branch(self) -> None:
        metrics = replace(LATIN, fs_selection=spacing.USE_TYPO_METRICS)
        self.assertEqual(
            spacing.single_line_height(metrics),
            (Fraction(19, 20), "use-typo-metrics"),
        )

    def test_legacy_branch_takes_hhea_when_larger(self) -> None:
        self.assertEqual(
            spacing.single_line_height(LATIN),
            (Fraction(11, 10), "legacy-max"),
        )

    def test_legacy_branch_takes_win_when_larger(self) -> None:
        metrics = replace(
            LATIN,
            win_ascent=900,
            win_descent=300,
            hhea_ascender=700,
            hhea_descender=-200,
            hhea_line_gap=0,
        )
        self.assertEqual(
            spacing.single_line_height(metrics),
            (Fraction(6, 5), "legacy-max"),
        )

    def test_exact_12_point_baseline_conversions(self) -> None:
        self.assertEqual(
            spacing.baseline_skip(Fraction(13, 10), "cjkfont"),
            Fraction(117, 5),
        )
        self.assertEqual(
            spacing.baseline_skip(Fraction(2355, 2048), "engfont"),
            Fraction(7065, 256),
        )
        self.assertEqual(spacing.decimal_points(Fraction(117, 5)), "23.400000000000")
        self.assertEqual(
            spacing.decimal_points(Fraction(7065, 256)), "27.597656250000"
        )


class ShippedFontTests(unittest.TestCase):
    def test_class_fallbacks_match_the_default_fonts(self) -> None:
        records = {record.key: record for record in spacing.precomputed_records()}
        english = spacing.decimal_points(
            records[("engfont", "family", "Times New Roman", "default")].baseline
        )
        chinese = spacing.decimal_points(
            records[("cjkfont", "file", "TW-Kai-98_1.ttf", "default")].baseline
        )
        class_text = (ROOT / "ntuthesis.cls").read_text(encoding="utf-8")
        self.assertIn(rf"\newcommand{{\ntu@baseline@en}}{{{english}}}", class_text)
        self.assertIn(rf"\newcommand{{\ntu@baseline@zh}}{{{chinese}}}", class_text)
        self.assertIn(rf"\def\ntu@baseline@en{{{english}}}%", class_text)
        self.assertIn(rf"\def\ntu@baseline@zh{{{chinese}}}%", class_text)

    def test_tinos_faces_have_times_new_roman_metrics(self) -> None:
        for name in SHIPPED_ENGLISH_FONTS:
            path = ROOT / "fonts/english" / name
            with self.subTest(path=path.name):
                height, branch = spacing.single_line_height(
                    spacing.read_font_metrics(FontFile(path))
                )
                self.assertEqual(height, Fraction(2355, 2048))
                self.assertEqual(branch, "legacy-max")

    def test_tw_faces_have_east_asian_metrics(self) -> None:
        for name in SHIPPED_CHINESE_FONTS:
            path = ROOT / "fonts/chinese" / name
            with self.subTest(path=path.name):
                metrics = spacing.read_font_metrics(FontFile(path))
                self.assertTrue(spacing.is_east_asian(metrics))
                self.assertEqual(
                    spacing.single_line_height(metrics),
                    (Fraction(13, 10), "east-asian"),
                )

    def test_precomputed_registry_covers_every_tracked_ttf(self) -> None:
        keys = {record.key for record in spacing.precomputed_records()}
        shipped = (
            ("engfont", SHIPPED_ENGLISH_FONTS),
            ("cjkfont", SHIPPED_CHINESE_FONTS),
        )
        for slot, names in shipped:
            for name in names:
                with self.subTest(path=name):
                    self.assertIn((slot, "file", name, "default"), keys)

    def test_proprietary_aliases_are_precomputed(self) -> None:
        keys = {record.key for record in spacing.precomputed_records()}
        for name in ("Times New Roman", "TimesNewRomanPSMT"):
            self.assertIn(("engfont", "family", name, "default"), keys)
        for name in ("標楷體", "BiauKai", "DFKai-SB"):
            self.assertIn(("cjkfont", "family", name, "default"), keys)


class ParserAndGeneratorTests(unittest.TestCase):
    def test_raw_parser_preserves_tex_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text(
                r"""\ntufontsetup{
  engfont = {Name \& Company},
  engfontoptions = {Ligatures = TeX, FontIndex = {01}},
  cjkfont = {標楷體},
  cjkfontoptions = {},
}
""",
                encoding="utf-8",
            )
            raw = parse_keyval_command_raw(source, "ntufontsetup")
            plain = parse_keyval_command(source, "ntufontsetup")
            self.assertEqual(raw["engfont"], r"Name \& Company")
            self.assertEqual(plain["engfont"], "Name & Company")
            self.assertEqual(
                spacing.configured_index(raw["engfontoptions"], "engfontoptions"),
                ("1", 1),
            )

    def test_metric_affecting_font_options_are_rejected(self) -> None:
        for option in sorted(spacing.METRIC_AFFECTING_OPTIONS):
            with self.subTest(option=option):
                with self.assertRaisesRegex(spacing.LineSpacingError, option):
                    spacing.configured_index(f"{option} = {{value}}", "engfontoptions")

    def test_nested_upright_scale_route_is_rejected(self) -> None:
        with self.assertRaisesRegex(spacing.LineSpacingError, "UprightFeatures"):
            spacing.configured_index(
                "UprightFeatures = {Scale = 2}", "engfontoptions"
            )

    def test_checked_in_default_registry_is_current(self) -> None:
        self.assertEqual(
            (ROOT / spacing.DEFAULT_REGISTRY_NAME).read_text(encoding="utf-8"),
            spacing.render_default_registry(),
        )

    def test_default_config_needs_no_user_records(self) -> None:
        self.assertEqual(spacing.current_records(ROOT), ())

    def test_multiple_active_font_setup_commands_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text(
                "\\ntufontsetup{engfont={One}}\n"
                "% \\ntufontsetup{engfont={Commented}}\n"
                "\\ntufontsetup{engfont={Two}}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CollectionError, r"2 active \\ntufontsetup"):
                parse_keyval_command_raw(source, "ntufontsetup")

    def _project(self, directory: Path, english_name: str = "Custom Font.ttf") -> Path:
        (directory / "fonts/english").mkdir(parents=True)
        shutil.copy2(ROOT / "fonts/english/Tinos-Regular.ttf", directory / "fonts/english" / english_name)
        (directory / "main.tex").write_text(
            "\\ntufontsetup{\n"
            f"  engfont = {{{english_name}}}, engfontoptions = {{}},\n"
            "  cjkfont = {BiauKai}, cjkfontoptions = {},\n"
            "}\n",
            encoding="utf-8",
        )
        return directory

    def test_custom_generation_is_deterministic_and_portable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory))
            first = spacing.render_registry(root)
            second = spacing.render_registry(root)
            self.assertEqual(first, second)
            self.assertIn(
                r"\nturegisterfontspacing{engfont}{file}{Custom Font.ttf}{default}{27.597656250000}",
                first,
            )
            self.assertNotIn("Times New Roman", first)
            self.assertNotIn("TW-Kai-98_1.ttf", first)
            self.assertIn("sha256=", first)
            self.assertNotIn(str(root), first)

    def test_generate_and_check_detect_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory))
            output = root / spacing.OUTPUT_NAME
            self.assertFalse(spacing.generate(root, output, check=True))
            self.assertFalse(output.exists())
            self.assertFalse(spacing.generate(root, output))
            self.assertTrue(spacing.generate(root, output))
            output.write_text("stale\n", encoding="utf-8")
            self.assertFalse(spacing.generate(root, output, check=True))
            self.assertEqual(output.read_text(encoding="utf-8"), "stale\n")

    def test_check_allows_missing_registry_for_precomputed_fonts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / spacing.OUTPUT_NAME
            self.assertTrue(spacing.generate(ROOT, output, check=True))
            self.assertFalse(output.exists())

    def test_check_rejects_old_user_registry_for_precomputed_fonts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / spacing.OUTPUT_NAME
            output.write_text("stale\n", encoding="utf-8")
            self.assertFalse(spacing.generate(ROOT, output, check=True))
            self.assertEqual(output.read_text(encoding="utf-8"), "stale\n")

    def test_check_detects_font_replaced_under_the_same_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory))
            output = root / spacing.OUTPUT_NAME
            spacing.generate(root, output)
            original = output.read_text(encoding="utf-8")

            shutil.copy2(
                ROOT / "fonts/chinese/TW-Kai-98_1.ttf",
                root / "fonts/english/Custom Font.ttf",
            )

            self.assertFalse(spacing.generate(root, output, check=True))
            self.assertEqual(output.read_text(encoding="utf-8"), original)
            self.assertNotEqual(spacing.render_registry(root), original)

    def test_changed_config_replaces_the_custom_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._project(Path(directory))
            old = spacing.render_registry(root)
            shutil.copy2(
                ROOT / "fonts/english/Tinos-Regular.ttf",
                root / "fonts/english/Renamed.ttf",
            )
            text = (root / "main.tex").read_text(encoding="utf-8")
            (root / "main.tex").write_text(
                text.replace("Custom Font.ttf", "Renamed.ttf"), encoding="utf-8"
            )
            new = spacing.render_registry(root)
            self.assertIn("{Custom Font.ttf}", old)
            self.assertNotIn("{Custom Font.ttf}", new)
            self.assertIn("{Renamed.ttf}", new)


if __name__ == "__main__":
    unittest.main()
