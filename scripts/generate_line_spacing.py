#!/usr/bin/env python3
"""Generate font-specific baseline skips loaded by ntuthesis.cls."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

from font_files import (
    FontFile,
    FontResolutionError,
    font_names,
    font_source,
    resolve_font,
)
from thesis_metadata import (
    CollectionError,
    collapse_spaces,
    key_values,
    parse_keyval_command,
    parse_keyval_command_raw,
)


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
DEFAULT_REGISTRY_NAME = "ntu-line-spacing-default.tex"
OUTPUT_NAME = "ntu-line-spacing.tex"

FONT_DIRECTORIES = {
    "engfont": Path("fonts/english"),
    "cjkfont": Path("fonts/chinese"),
}
FONT_OPTION_KEYS = {
    "engfont": "engfontoptions",
    "cjkfont": "cjkfontoptions",
}

FONT_SIZE = Fraction(12)
SPACING_MULTIPLIERS = {
    "engfont": Fraction(2),
    "cjkfont": Fraction(3, 2),
}

USE_TYPO_METRICS = 1 << 7
EAST_ASIAN_CODEPAGE_MASK = sum(1 << bit for bit in range(17, 22))
# Hiragana, Katakana, Bopomofo, Hangul compatibility/syllables, Han and CJK strokes.
EAST_ASIAN_UNICODE_BITS = (49, 50, 51, 52, 56, 59, 61)
EAST_ASIAN_UNICODE_MASK = sum(1 << bit for bit in EAST_ASIAN_UNICODE_BITS)
METRIC_AFFECTING_OPTIONS = {
    "Extension",
    "FontFace",
    "Instance",
    "KpseOnly",
    "OpticalSize",
    "Path",
    "RawAxis",
    "RawFeature",
    "Scale",
    "ScaleAgain",
    "SizeFeatures",
    "Slant",
    "UprightFont",
    "UprightFeatures",
    "Weight",
    "Width",
}


class LineSpacingError(ValueError):
    """The configured font cannot provide a safe line-spacing value."""


@dataclass(frozen=True)
class FontTableMetrics:
    """The OpenType fields used by Word's three line-height branches."""

    units_per_em: int
    win_ascent: int
    win_descent: int
    typo_ascender: int
    typo_descender: int
    typo_line_gap: int
    hhea_ascender: int
    hhea_descender: int
    hhea_line_gap: int
    fs_selection: int
    code_page_range1: int
    unicode_ranges: tuple[int, int, int, int]


@dataclass(frozen=True)
class SpacingRecord:
    """One declaration that TeX can match against its configured token list."""

    slot: str
    source: str
    tex_name: str
    index: str
    baseline: Fraction

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.slot, self.source, self.tex_name, self.index)


def is_east_asian(metrics: FontTableMetrics) -> bool:
    """Whether OpenType metadata identifies the face as Chinese/Japanese/Korean."""
    if metrics.code_page_range1 & EAST_ASIAN_CODEPAGE_MASK:
        return True
    ranges = sum(value << (32 * index) for index, value in enumerate(metrics.unicode_ranges))
    return bool(ranges & EAST_ASIAN_UNICODE_MASK)


def single_line_height(metrics: FontTableMetrics) -> tuple[Fraction, str]:
    """The face's Word-compatible single-line height in em and its branch."""
    if metrics.units_per_em <= 0:
        raise LineSpacingError("head.unitsPerEm must be positive")
    upm = metrics.units_per_em
    win = Fraction(metrics.win_ascent + metrics.win_descent, upm)
    typo = Fraction(
        metrics.typo_ascender - metrics.typo_descender + metrics.typo_line_gap,
        upm,
    )
    hhea = Fraction(
        metrics.hhea_ascender - metrics.hhea_descender + metrics.hhea_line_gap,
        upm,
    )

    # A CJK face keeps this branch even when it sets an ASCII run.  It also
    # precedes USE_TYPO_METRICS when both properties occur.
    if is_east_asian(metrics):
        height, branch = Fraction(13, 10) * win, "east-asian"
    elif metrics.fs_selection & USE_TYPO_METRICS:
        height, branch = typo, "use-typo-metrics"
    else:
        height, branch = max(hhea, win), "legacy-max"
    if height <= 0:
        raise LineSpacingError(f"the {branch} line height must be positive")
    return height, branch


def baseline_skip(single_height: Fraction, slot: str) -> Fraction:
    """Convert an em line height into the 12 pt font's baseline skip."""
    try:
        multiple = SPACING_MULTIPLIERS[slot]
    except KeyError as error:
        raise LineSpacingError(f"Unknown font slot: {slot}") from error
    return single_height * FONT_SIZE * multiple


def read_font_metrics(font: FontFile) -> FontTableMetrics:
    """Read the three required OpenType metric tables from one selected face."""
    try:
        with font.open(lazy=True) as opened:
            head = opened["head"]
            os2 = opened["OS/2"]
            hhea = opened["hhea"]
            return FontTableMetrics(
                units_per_em=int(head.unitsPerEm),
                win_ascent=int(os2.usWinAscent),
                win_descent=int(os2.usWinDescent),
                typo_ascender=int(os2.sTypoAscender),
                typo_descender=int(os2.sTypoDescender),
                typo_line_gap=int(os2.sTypoLineGap),
                hhea_ascender=int(hhea.ascent),
                hhea_descender=int(hhea.descent),
                hhea_line_gap=int(hhea.lineGap),
                fs_selection=int(os2.fsSelection),
                code_page_range1=int(getattr(os2, "ulCodePageRange1", 0)),
                unicode_ranges=tuple(
                    int(getattr(os2, f"ulUnicodeRange{index}", 0))
                    for index in range(1, 5)
                ),
            )
    except Exception as error:  # noqa: BLE001 - fontTools has table-specific errors
        raise LineSpacingError(
            f"Cannot read head, OS/2 and hhea metrics from {font.name}: {error}"
        ) from error


def decimal_points(value: Fraction) -> str:
    """A stable decimal precise well beyond TeX's scaled-point resolution."""
    with localcontext() as context:
        context.prec = 40
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return f"{decimal:.12f}"


def _precomputed_record(
    slot: str,
    source: str,
    tex_name: str,
    single_height: Fraction,
) -> SpacingRecord:
    return SpacingRecord(
        slot,
        source,
        tex_name,
        "default",
        baseline_skip(single_height, slot),
    )


def precomputed_records() -> tuple[SpacingRecord, ...]:
    """Known proprietary defaults and every TTF distributed by the template."""
    times_height = Fraction(2355, 2048)
    cjk_height = Fraction(13, 10)
    records: list[SpacingRecord] = []

    for family in ("Times New Roman", "TimesNewRomanPSMT"):
        records.append(_precomputed_record("engfont", "family", family, times_height))
    for filename in ("Times New Roman.ttf", "times.ttf"):
        records.append(_precomputed_record("engfont", "file", filename, times_height))
    for filename in (
        "Tinos-Bold.ttf",
        "Tinos-BoldItalic.ttf",
        "Tinos-Italic.ttf",
        "Tinos-Regular.ttf",
    ):
        records.append(_precomputed_record("engfont", "file", filename, times_height))

    for family in ("BiauKai", "DFKai-SB", "DFKaiShu-SB-Estd-BF", "標楷體"):
        records.append(_precomputed_record("cjkfont", "family", family, cjk_height))
    for filename in ("BiauKai.ttf", "DFKai-SB.ttf", "kaiu.ttf", "標楷體.ttf"):
        records.append(_precomputed_record("cjkfont", "file", filename, cjk_height))
    for filename in ("TW-Kai-98_1.ttf", "TW-Sung-98_1.ttf"):
        records.append(_precomputed_record("cjkfont", "file", filename, cjk_height))
    return tuple(records)


def configured_index(raw_options: str, option_name: str) -> tuple[str, int | None]:
    """The declaration key and numeric collection index in fontspec options."""
    options = key_values(raw_options)
    unsupported = sorted(METRIC_AFFECTING_OPTIONS.intersection(options))
    if unsupported:
        raise LineSpacingError(
            f"main.tex sets metric-affecting {option_name} "
            f"{', '.join(unsupported)}; the line-spacing generator cannot "
            "precalculate a face changed by those options"
        )
    written = options.get("FontIndex")
    if written is None:
        return "default", None
    written = written.strip()
    if not re.fullmatch(r"\d+", written):
        raise LineSpacingError(
            f"main.tex sets {option_name} FontIndex to {written!r}, "
            "which is not a non-negative integer"
        )
    index = int(written)
    return str(index), index


def _font_hash(font: FontFile) -> str:
    digest = hashlib.sha256()
    with font.path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _comment_text(value: str) -> str:
    return " ".join(value.replace("%", "percent").split())


def font_provenance(font: FontFile, branch: str) -> str:
    """A portable audit comment; never expose the machine's absolute path."""
    version = ""
    try:
        with font.open(lazy=True) as opened:
            version = opened["name"].getDebugName(5) or ""
    except Exception:  # noqa: BLE001 - metrics already supplied the useful error
        pass
    family = font_names(font)
    parts = [font.name]
    if family:
        parts.append(family[0])
    if version:
        parts.append(version)
    parts.extend((branch, f"sha256={_font_hash(font)}"))
    return _comment_text("; ".join(parts))


def current_records(root: Path) -> tuple[tuple[SpacingRecord, str], ...]:
    """Calculate entries for configured selections that are not precomputed."""
    main_tex = root / "main.tex"
    raw = parse_keyval_command_raw(main_tex, "ntufontsetup")
    plain = parse_keyval_command(main_tex, "ntufontsetup")
    builtins = {record.key for record in precomputed_records()}
    records: list[tuple[SpacingRecord, str]] = []

    for slot in ("engfont", "cjkfont"):
        tex_name = raw.get(slot, "").strip()
        lookup_name = collapse_spaces(plain.get(slot, ""))
        if not tex_name or not lookup_name:
            raise LineSpacingError(f"main.tex leaves {slot} empty in \\ntufontsetup")
        option_key = FONT_OPTION_KEYS[slot]
        index_key, font_index = configured_index(raw.get(option_key, ""), option_key)
        directory = FONT_DIRECTORIES[slot]
        source = font_source(root, directory, lookup_name)
        key = (slot, source, tex_name, index_key)
        if key in builtins:
            continue
        try:
            font = resolve_font(root, directory, lookup_name, font_index)
        except FontResolutionError as error:
            raise LineSpacingError(
                f"Cannot precalculate {slot} = {lookup_name!r}: {error}"
            ) from error
        single, branch = single_line_height(read_font_metrics(font))
        record = SpacingRecord(
            slot,
            source,
            tex_name,
            index_key,
            baseline_skip(single, slot),
        )
        records.append((record, font_provenance(font, branch)))
    return tuple(records)


def _render_registry(
    records: dict[tuple[str, str, str, str], SpacingRecord],
    provenance: dict[tuple[str, str, str, str], str],
    header: list[str],
) -> str:
    """Render one deterministic TeX registry."""
    lines = [
        *header,
        "",
    ]
    for key in sorted(records):
        record = records[key]
        if comment := provenance.get(key):
            lines.append(f"% {comment}")
        lines.append(
            "\\nturegisterfontspacing"
            f"{{{record.slot}}}{{{record.source}}}{{{record.tex_name}}}"
            f"{{{record.index}}}{{{decimal_points(record.baseline)}}}"
        )
    return "\n".join(lines) + "\n"


def render_default_registry() -> str:
    """The committed registry for named defaults and distributed font files."""
    records = {record.key: record for record in precomputed_records()}
    return _render_registry(
        records,
        {},
        [
            "% Precalculated defaults; do not edit by hand.",
            "% Values are 12 pt baseline skips generated from font metrics.",
        ],
    )


def _render_user_registry(
    generated: tuple[tuple[SpacingRecord, str], ...],
) -> str:
    """Render the ignored registry from already calculated custom records."""
    records = {record.key: record for record, _ in generated}
    provenance = {record.key: comment for record, comment in generated}
    return _render_registry(
        records,
        provenance,
        [
            "% Generated by scripts/generate_line_spacing.py; do not edit by hand.",
            "% This user-specific file is ignored by Git.",
        ],
    )


def render_registry(root: Path) -> str:
    """The ignored user registry for currently selected custom fonts."""
    return _render_user_registry(current_records(root))


def atomic_write(path: Path, contents: str) -> None:
    """Replace a generated file without exposing a half-written registry."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            output.write(contents)
            temporary = Path(output.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def generate(root: Path, output: Path, check: bool = False) -> bool:
    """Write or check the registry; return whether it was already current."""
    generated = current_records(root)
    expected = _render_user_registry(generated)
    existing = output.read_text(encoding="utf-8") if output.is_file() else None
    # A fresh checkout using only precomputed fonts intentionally has no ignored
    # user registry.  An existing file must still match: it may contain stale
    # declarations that override the committed defaults.
    if existing is None and not generated:
        return True
    if existing == expected:
        return True
    if check:
        return False
    atomic_write(output, expected)
    return False


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting when ntu-line-spacing.tex is stale",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = argument_parser().parse_args(argv)
    root = arguments.root.resolve()
    output = arguments.output or root / OUTPUT_NAME
    try:
        current = generate(root, output, arguments.check)
    except (CollectionError, LineSpacingError, OSError) as error:
        print(f"line-spacing: {error}", file=sys.stderr)
        return 1
    if arguments.check and not current:
        print(
            f"{output.name} is out of date; run `pixi run line-spacing`",
            file=sys.stderr,
        )
        return 1
    if not arguments.check and not current:
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
