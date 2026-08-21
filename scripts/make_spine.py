#!/usr/bin/env python3
"""Write the spine of the bound thesis (書側) as ODT and PDF, in both bindings.

A bindery cannot letter a spine until it knows how thick the finished book
will be, and that follows from the thesis itself: how many pages `pixi run
build` produced, whether they are printed on one side of the sheet or both,
and how thick a sheet of the chosen paper is. This script reads the page count
straight out of `main.pdf`, turns it into a millimetre width, and writes the
artwork at exactly that width -- once for the 平裝 (paperback) copy and once
for the 精裝 (hardcover) copy, whose boards add a fixed 4 mm.

Four files come out, two per binding:

* the ODT, the editable master a print shop can open and adjust, with the
  thesis's own Chinese face embedded so it sets correctly on their machine;
* the PDF, drawn here rather than converted, so that producing it needs
  nothing beyond the packages `pixi run build` already installs.

Both are laid out from one table of measurements taken off NTU's official
spine form, so the two agree by construction. The text runs top to bottom in
真正直書 (true vertical setting), the way the form has it: the university and
the institute side by side at the head, then the degree, the title, the
author, and the ROC year and month at the foot.

Like `cover` and `protect`, this step is deliberately manual; `pixi run build`
never calls it.
"""

from __future__ import annotations

import argparse
import io
import logging
import math
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pymupdf
from fontTools import subset
from fontTools.ttLib import TTFont


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
DEFAULT_INPUT = PROJECT_ROOT / "main.pdf"

MM_PER_IN = 25.4
PT_PER_IN = 72.0
PAGE_HEIGHT_PT = 297.0 * PT_PER_IN / MM_PER_IN  # the A4 height of the thesis

def inch(value: float) -> float:
    return value * PT_PER_IN


def mm(value: float) -> float:
    return value * PT_PER_IN / MM_PER_IN


# --------------------------------------------------------------------------
# How thick the finished book is
# --------------------------------------------------------------------------
#
# 內頁紙材：80 磅道林紙。臺灣印刷業以「條」計厚度，1 條 = 0.01 mm，80 磅
# （80 g/m²）道林紙約 10 條。
#
# The trade measures paper in 條, hundredths of a millimetre. 80 磅道林紙 --
# the uncoated woodfree stock a thesis text block is normally printed on --
# is about 10 條, so a sheet of it is a tenth of a millimetre thick.
PAPER_THICKNESS_MM = 0.10

# 平裝（膠裝）的封面與書背膠層，約 1 mm。
# Perfect binding adds about a millimetre for the cover and the glue.
PAPERBACK_BINDING_MM = 1.00

# 精裝的紙板，兩面各 2 mm。官方範例的 8 mm 平裝與 12 mm 精裝正好差 4 mm。
# A hardcover adds 2 mm of board per side. That 4 mm is exactly the gap
# between the 8 mm paperback and the 12 mm hardcover of NTU's own sample pair.
BOARD_THICKNESS_MM = 4.00

# 少於 80 頁預設單面列印，80 面以上預設雙面列印。
# Below this page count a thesis is printed single-sided, one PDF page per
# sheet; at or above it, double-sided, two PDF pages per sheet.
DUPLEX_THRESHOLD_PAGES = 80


@dataclass(frozen=True)
class Binding:
    key: str
    name_zh: str
    board_mm: float


BINDINGS = (
    Binding("paperback", "平裝", 0.0),
    Binding("hardcover", "精裝", BOARD_THICKNESS_MM),
)


# --------------------------------------------------------------------------
# The layout of the official form
# --------------------------------------------------------------------------
#
# Row heights in inches, measured off NTU's spine form. The form is one
# single-column table down the length of an A4 page; the named rows carry
# text and the unnamed ones are the spacing between them.
#
# The form places the two heading columns with absolutely positioned drawing
# frames rather than in the table. Their offset and height are written out
# here as ordinary rows -- 0.3942 + 0.9450 + 0.3143 is the 1.6535 in row they
# sit inside -- so that one table drives the whole page.
LAYOUT: tuple[tuple[str, float], ...] = (
    ("", 0.9451),
    ("", 0.3942),
    ("heading", 0.9450),
    ("", 0.3143),
    ("", 0.3153),
    ("degree", 1.1021),
    ("", 0.3153),
    ("title", 3.9368),
    ("", 0.2361),
    ("author", 1.1021),
    ("", 0.2757),
    ("date", 0.9451),
    ("", 0.3938),
)

# The form's rows stop 33.98 pt short of the foot of the page and nothing is
# lettered there. Overrunning the sheet would push the last block off it.
if inch(sum(height for _, height in LAYOUT)) > PAGE_HEIGHT_PT:
    raise SystemExit("The spine layout is taller than the page it is drawn on.")

# Point size each block is set at on the form, before any shrinking to fit.
NOMINAL_SIZE_PT = {
    "heading": 10.0,
    "degree": 12.0,
    "title": 14.0,
    "author": 14.0,
    "date": 14.0,
}

# The form sets the two heading columns 1.01 em apart, near enough to solid,
# so that the university and the institute read as one block rather than as
# two separate lines. Pinning the pitch also keeps a face whose natural line
# height exceeds one em from pushing the second column off a narrow spine.
HEADING_COLUMN_PITCH = 1.01

# The date is the one horizontal block on the spine; the form leads it at
# 15 pt on a 14 pt body.
DATE_LINE_PITCH = 15.0 / 14.0

# 「撰」 follows the author's name after an ideographic space, as on the form.
AUTHOR_SUFFIX = "　撰"

# How close to the edge of the spine a character may set. The official 8 mm
# sample leaves about 0.3 mm beside its widest line, the year; a quarter of a
# millimetre is a shade tighter than that, so a spine as wide as the sample
# still sets at the form's own sizes, and a narrower one shrinks rather than
# running its characters off the fold.
SIDE_CLEARANCE_MM = 0.25


# --------------------------------------------------------------------------
# Reading the thesis
# --------------------------------------------------------------------------
#
# ntusetup.tex and main.tex are the same two files generate_tdr_upload_script.py
# reads, and its parser is imported rather than repeated so that the spine can
# never disagree with the TDR submission about who wrote what.
sys.path.insert(0, str(PROJECT_ROOT))
from generate_tdr_upload_script import (  # noqa: E402
    CollectionError,
    parse_ntusetup,
    strip_comments,
)


DEGREE_NAMES = {"master": "碩士論文", "doctor": "博士論文"}


def parse_degree(path: Path) -> str:
    """Read the ntuthesis `degree` option, which names the kind of thesis."""
    text = strip_comments(path.read_text(encoding="utf-8"))
    options = re.search(r"\\documentclass\s*\[(.*?)\]\s*\{ntuthesis\}", text, re.DOTALL)
    if not options:
        raise CollectionError(f"Could not find ntuthesis options in {path}")
    degree = re.search(r"\bdegree\s*=\s*(master|doctor)\b", options.group(1))
    # The class defaults to master when the option is left out entirely.
    return DEGREE_NAMES[degree.group(1) if degree else "master"]


@dataclass(frozen=True)
class SpineText:
    university: str
    institute: str
    degree: str
    title: str
    author: str
    roc_year: int
    month: int

    @property
    def heading(self) -> tuple[str, str]:
        """The two heading columns, rightmost first; vertical text reads that way."""
        return (self.university, self.institute)

    @property
    def byline(self) -> str:
        return f"{self.author}{AUTHOR_SUFFIX}"

    @property
    def date_lines(self) -> tuple[str, str]:
        return (str(self.roc_year), str(self.month))

    def block(self, name: str) -> tuple[str, ...]:
        return {
            "heading": self.heading,
            "degree": (self.degree,),
            "title": (self.title,),
            "author": (self.byline,),
            "date": self.date_lines,
        }[name]

    def characters(self) -> str:
        joined = "".join("".join(self.block(name)) for name in NOMINAL_SIZE_PT)
        return "".join(sorted(set(joined)))


def read_thesis_text(root: Path) -> SpineText:
    setup = parse_ntusetup(root / "ntusetup.tex")
    missing = [key for key in ("university", "institute", "title", "author") if not setup.get(key)]
    if missing:
        raise CollectionError(
            f"ntusetup.tex has no {', '.join(missing)}; the spine cannot be lettered without it."
        )
    # The class defaults `date` to the day of the build, exactly as the cover does.
    try:
        written = date.fromisoformat(setup["date"]) if setup.get("date") else date.today()
    except ValueError as error:
        raise CollectionError(
            f"ntusetup.tex has date = {{{setup['date']}}}, which is not a YYYY-MM-DD date."
        ) from error
    return SpineText(
        university=setup["university"],
        institute=setup["institute"],
        degree=parse_degree(root / "main.tex"),
        title=setup["title"],
        author=setup["author"],
        roc_year=written.year - 1911,
        month=written.month,
    )


# --------------------------------------------------------------------------
# The thesis's own Chinese face
# --------------------------------------------------------------------------


def cover_cjk_font_name(document: pymupdf.Document) -> str:
    """Name the font the built PDF sets Chinese in, as used on the cover.

    Page one is the cover, and the cover is the one page guaranteed to carry
    the university, institute, title and author in the thesis's Chinese face
    -- the very words the spine repeats.
    """
    page = document[0]
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if any(ord(char["c"]) > 0x2E80 for char in span["chars"]):
                    return re.sub(r"^[A-Z]{6}\+", "", span["font"])
    raise CollectionError(
        "Page 1 of the built PDF prints no Chinese, so its Chinese font cannot "
        "be identified. Build the cover before writing the spine."
    )


def font_names(path: Path) -> tuple[str, ...]:
    """The family, full and PostScript names a font file answers to.

    Users drop their own files into fonts/ for fontset=template, so anything
    that will not open as a font is simply not the font being looked for.
    """
    try:
        with TTFont(path, lazy=True, fontNumber=0) as font:
            table = font["name"]
            return tuple(name for name in (table.getDebugName(i) for i in (1, 4, 6)) if name)
    except Exception:  # noqa: BLE001 - fontTools raises a different type per defect
        logging.debug("Not a readable font: %s", path)
        return ()


def reduced(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def same_font(name: str, candidate: str) -> bool:
    return reduced(name) == reduced(candidate)


def locate_font(name: str, root: Path) -> Path:
    """Find the file behind a PDF font name: shipped with the template, or installed.

    fontconfig answers a request for a face it does not have with a
    metric-compatible stand-in, so an fc-match hit is only accepted once the
    file it points at says it really is the font that was asked for.
    """
    for path in sorted(root.glob("fonts/**/*")):
        if path.suffix.lower() in (".ttf", ".otf", ".ttc") and any(
            same_font(name, candidate) for candidate in font_names(path)
        ):
            return path
    matched = subprocess.run(
        ["fc-match", "--format=%{file}", name],
        capture_output=True,
        text=True,
    )
    candidate = Path(matched.stdout.strip()) if matched.returncode == 0 else None
    if candidate and candidate.is_file() and any(
        same_font(name, found) for found in font_names(candidate)
    ):
        return candidate
    raise CollectionError(
        f"The built PDF sets Chinese in {name}, but no file for it was found in "
        f"{root / 'fonts'} or on this system. Install it, or build with a "
        "fontset whose Chinese face ships with the template."
    )


# OS/2 fsType, the font's own statement of what may be embedded where.
FSTYPE_RESTRICTED = 0x0002  # embedding forbidden without the vendor's leave
FSTYPE_EDITABLE = 0x0008  # embedding allowed in a document that can be edited
FSTYPE_NO_SUBSETTING = 0x0100  # embed the whole face or none of it


def embeddable_font(path: Path, characters: str) -> bytes:
    """Cut the face down to the glyphs the spine prints, ready to embed.

    The shipped 全字庫 faces are tens of megabytes; a spine sets a few dozen
    characters. Every name record is kept so that the family name in the ODT
    still resolves to the embedded file.
    """
    with TTFont(path, lazy=True, fontNumber=0) as probe:
        rights = probe["OS/2"].fsType
    if rights & FSTYPE_RESTRICTED:
        raise CollectionError(
            f"{path.name} forbids embedding, so it cannot travel inside the spine "
            "files. Build the thesis with a fontset whose Chinese face ships with "
            "the template."
        )

    options = subset.Options()
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.recalc_bounds = True
    font = subset.load_font(str(path), options)
    if rights & FSTYPE_NO_SUBSETTING:
        logging.warning("%s asks not to be subset; embedding it whole.", path.name)
    else:
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=characters)
        subsetter.subset(font)
    if rights and not rights & FSTYPE_EDITABLE:
        # A face marked preview-and-print is licensed for exactly what a spine
        # is, but an office suite opens an ODT for editing and substitutes
        # anything not marked installable -- silently, so the print shop would
        # letter the spine in whatever it happened to fall back to. The subset
        # is therefore written installable. The faces this template ships allow
        # that: 全字庫 is 政府資料開放授權條款-1.0 or OFL-1.1 and Tinos is
        # OFL-1.1, and all three permit modified versions. Check your own
        # licence before embedding a font of your own.
        logging.warning(
            "%s marks itself print-only; the embedded subset is written installable "
            "so that readers honour it rather than substituting another face.",
            path.name,
        )
        font["OS/2"].fsType = 0
    written = io.BytesIO()
    font.save(written)
    font.close()
    return written.getvalue()


def missing_characters(path: Path, characters: str) -> str:
    with TTFont(path, lazy=True, fontNumber=0) as font:
        table = font.getBestCmap()
    return "".join(char for char in characters if ord(char) not in table)


# --------------------------------------------------------------------------
# How wide the spine has to be
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Thickness:
    pages: int
    duplex: bool
    sheets: int
    paper_mm: float
    binding_mm: float
    board_mm: float
    measured_mm: float | None

    @property
    def text_block_mm(self) -> float:
        return self.sheets * self.paper_mm

    @property
    def raw_mm(self) -> float:
        return self.text_block_mm + self.binding_mm + self.board_mm

    @property
    def computed_mm(self) -> int:
        # A bindery works in whole millimetres, and a spine that is a shade
        # too wide still binds while one a shade too narrow does not.
        return math.ceil(self.raw_mm - 1e-9)

    @property
    def width_mm(self) -> float:
        """What the spine is actually drawn at: a measured book beats the sum."""
        if self.measured_mm is None:
            return self.computed_mm
        return self.measured_mm + self.board_mm


def measure(
    pages: int,
    binding: Binding,
    *,
    duplex: bool,
    paper_mm: float,
    binding_mm: float,
    measured_mm: float | None,
) -> Thickness:
    return Thickness(
        pages=pages,
        duplex=duplex,
        sheets=math.ceil(pages / 2) if duplex else pages,
        paper_mm=paper_mm,
        binding_mm=binding_mm,
        board_mm=binding.board_mm,
        measured_mm=measured_mm,
    )


# --------------------------------------------------------------------------
# Placing the text
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Block:
    """One lettered row of the form, sized and positioned on the page."""

    name: str
    top_pt: float
    height_pt: float
    lines: tuple[str, ...]
    size_pt: float
    pitch_pt: float
    ascent: float
    vertical: bool
    justified: bool

    @property
    def shrunk(self) -> bool:
        return self.size_pt < NOMINAL_SIZE_PT[self.name] - 1e-6

    def baselines(self, index: int) -> list[float]:
        """Baseline of every character of line `index`, top of the page down.

        A vertical CJK line hands each character a slot one em deep and hangs
        it from the top of that slot, so the first baseline sits one ascent
        below where the line begins and the block's ink ends up filling its
        row. Both outputs work from these numbers, so the ODT and the PDF
        letter the spine identically.
        """
        if not self.vertical:
            return []
        count = len(self.lines[index])
        if self.justified:
            step = (self.height_pt - self.size_pt) / (count - 1) if count > 1 else 0.0
            start = self.top_pt if count > 1 else self.top_pt + (self.height_pt - self.size_pt) / 2
        else:
            step = self.size_pt
            start = self.top_pt + (self.height_pt - count * self.size_pt) / 2
        start += self.ascent * self.size_pt
        return [start + step * position for position in range(count)]

    def centre_pt(self, index: int, width_pt: float) -> float:
        """Where line `index` sits across the spine.

        Vertical lines stack right to left, so the first line of a block is
        its rightmost column.
        """
        offset = (len(self.lines) - 1) / 2 - index
        return width_pt / 2 + offset * self.pitch_pt


def capped(name: str, *limits: float) -> float:
    """The form's point size, or the largest tenth of a point that still fits.

    Rounding a shrunk size down leaves a sliver of slack in the row, so that a
    block sized to exactly its limit cannot spill into a second column on a
    reader whose metrics round the other way.
    """
    nominal = NOMINAL_SIZE_PT[name]
    limit = min(limits)
    if limit >= nominal:
        return nominal
    if limit <= 0:
        raise CollectionError(f"The spine is too narrow to letter its {name}.")
    return math.floor(limit * 10) / 10


def fit_size(
    name: str,
    lines: tuple[str, ...],
    height_pt: float,
    width_pt: float,
    ruler: pymupdf.Font,
) -> tuple[float, float]:
    """Return the point size and line pitch that keep a block inside its row.

    The form's sizes suit the titles it was drawn with. A longer institute
    name, a longer title or a narrower spine has to give, and it gives by
    setting smaller rather than by running over the edge of the artwork.
    """
    across = width_pt - 2 * mm(SIDE_CLEARANCE_MM)
    if name == "date":
        widest = max(ruler.text_length(line, fontsize=1.0) for line in lines)
        size = capped(name, across / widest, height_pt / (len(lines) * DATE_LINE_PITCH))
        return size, size * DATE_LINE_PITCH
    pitch_factor = HEADING_COLUMN_PITCH if name == "heading" else 1.0
    longest = max(len(line) for line in lines)
    # One em per character down the column, one pitch per column across it.
    size = capped(name, height_pt / longest, across / (pitch_factor * len(lines)))
    return size, size * pitch_factor


def lay_out(text: SpineText, width_pt: float, ruler: pymupdf.Font) -> tuple[Block, ...]:
    blocks: list[Block] = []
    top = 0.0
    for name, height_in in LAYOUT:
        height = inch(height_in)
        if name:
            lines = text.block(name)
            size, pitch = fit_size(name, lines, height, width_pt, ruler)
            blocks.append(
                Block(
                    name=name,
                    top_pt=top,
                    height_pt=height,
                    lines=lines,
                    size_pt=size,
                    pitch_pt=pitch,
                    ascent=ruler.ascender,
                    vertical=name != "date",
                    justified=name == "heading",
                )
            )
        top += height
    return tuple(blocks)


# --------------------------------------------------------------------------
# The PDF
# --------------------------------------------------------------------------


def write_pdf(
    blocks: tuple[Block, ...],
    width_pt: float,
    font: pymupdf.Font,
    metadata: dict[str, str],
    target: Path,
) -> None:
    """Draw the spine directly, one character at a time.

    Converting the ODT would mean an office suite in the toolchain; the
    placement is already computed, so the characters are simply set where the
    layout puts them.
    """
    with pymupdf.open() as document:
        page = document.new_page(width=width_pt, height=PAGE_HEIGHT_PT)
        writer = pymupdf.TextWriter(page.rect)
        for block in blocks:
            if block.vertical:
                for index, line in enumerate(block.lines):
                    centre = block.centre_pt(index, width_pt)
                    for character, baseline in zip(line, block.baselines(index)):
                        advance = font.glyph_advance(ord(character)) * block.size_pt
                        writer.append(
                            pymupdf.Point(centre - advance / 2, baseline),
                            character,
                            font=font,
                            fontsize=block.size_pt,
                        )
                continue
            # Half leading above and below, the way a line box is built.
            leading = block.pitch_pt - block.size_pt * (font.ascender - font.descender)
            top = block.top_pt + (block.height_pt - len(block.lines) * block.pitch_pt) / 2
            for index, line in enumerate(block.lines):
                baseline = (
                    top + index * block.pitch_pt + leading / 2 + font.ascender * block.size_pt
                )
                length = font.text_length(line, fontsize=block.size_pt)
                writer.append(
                    pymupdf.Point((width_pt - length) / 2, baseline),
                    line,
                    font=font,
                    fontsize=block.size_pt,
                )
        writer.write_text(page)
        document.set_metadata(metadata)
        document.subset_fonts()
        document.save(target, garbage=4, deflate=True)
    logging.info("Wrote %s", target)


# --------------------------------------------------------------------------
# The ODT
# --------------------------------------------------------------------------

ODF_NAMESPACES = " ".join(
    f'xmlns:{prefix}="{uri}"'
    for prefix, uri in (
        ("office", "urn:oasis:names:tc:opendocument:xmlns:office:1.0"),
        ("style", "urn:oasis:names:tc:opendocument:xmlns:style:1.0"),
        ("text", "urn:oasis:names:tc:opendocument:xmlns:text:1.0"),
        ("table", "urn:oasis:names:tc:opendocument:xmlns:table:1.0"),
        ("fo", "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"),
        ("svg", "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"),
        ("xlink", "http://www.w3.org/1999/xlink"),
        ("loext", "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"),
    )
)


def pt(value: float) -> str:
    return f"{value:.4f}pt"


def font_declaration(family: str, embedded: str) -> str:
    """Declare the face and point it at the copy stored inside the ODT.

    Both content.xml and styles.xml carry this; a reader consults whichever it
    reaches first.
    """
    return (
        f"<office:font-face-decls><style:font-face style:name={quoteattr(family)} "
        f"""svg:font-family={quoteattr(f"'{family}'")} """
        'style:font-family-generic="system" style:font-pitch="variable">'
        f"<svg:font-face-src><svg:font-face-uri xlink:href={quoteattr(embedded)} "
        'xlink:type="simple" loext:font-style="normal" loext:font-weight="normal">'
        '<svg:font-face-format svg:string="truetype"/>'
        "</svg:font-face-uri></svg:font-face-src>"
        "</style:font-face></office:font-face-decls>"
    )


def text_properties(family: str, size_pt: float) -> str:
    """Set one size in one family, for Western, Asian and complex scripts alike.

    The spine is Chinese throughout, including the ROC year and month, which
    the form also sets in the Chinese face rather than in a Western one.
    """
    name, size = quoteattr(family), quoteattr(pt(size_pt))
    return (
        f"<style:text-properties style:font-name={name} fo:font-family={name} "
        f"fo:font-size={size} "
        f"style:font-name-asian={name} style:font-family-asian={name} "
        f"style:font-size-asian={size} "
        f"style:font-name-complex={name} style:font-family-complex={name} "
        f"style:font-size-complex={size} "
        'fo:font-weight="normal" style:font-weight-asian="normal" '
        'style:font-weight-complex="normal"/>'
    )


def automatic_styles(blocks: tuple[Block, ...], width_pt: float, family: str) -> str:
    """Every style content.xml needs: the table, its rows and cells, the text."""
    pieces = [
        '<style:style style:name="Spine" style:family="table">'
        f'<style:table-properties style:width={quoteattr(pt(width_pt))} '
        'table:align="center" fo:margin-top="0pt" fo:margin-bottom="0pt" '
        'style:writing-mode="page"/></style:style>',
        '<style:style style:name="SpineColumn" style:family="table-column">'
        f'<style:table-column-properties style:column-width={quoteattr(pt(width_pt))}/>'
        "</style:style>",
        '<style:style style:name="Plain" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none"/></style:style>',
        '<style:style style:name="Upright" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none" '
        'style:vertical-align="middle"/></style:style>',
        '<style:style style:name="Sideways" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none" '
        'style:vertical-align="middle" style:writing-mode="tb-rl"/></style:style>',
        '<style:style style:name="Blank" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt"/>'
        "</style:style>",
    ]
    for index, (_, height_in) in enumerate(LAYOUT):
        pieces.append(
            f'<style:style style:name="Row{index}" style:family="table-row">'
            f"<style:table-row-properties style:row-height={quoteattr(pt(inch(height_in)))} "
            'fo:keep-together="auto"/></style:style>'
        )
    for block in blocks:
        alignment = (
            'fo:text-align="justify" fo:text-align-last="justify" '
            'style:justify-single-word="false"'
            if block.justified
            else 'fo:text-align="center" style:justify-single-word="false"'
        )
        writing = ' style:writing-mode="tb-rl"' if block.vertical else ""
        pieces.append(
            f'<style:style style:name="P{block.name}" style:family="paragraph">'
            '<style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt" '
            'style:contextual-spacing="false" '
            f"fo:line-height={quoteattr(pt(block.pitch_pt))} {alignment}{writing}/>"
            "</style:style>"
        )
        pieces.append(
            f'<style:style style:name="T{block.name}" style:family="text">'
            f"{text_properties(family, block.size_pt)}</style:style>"
        )
    return f"<office:automatic-styles>{''.join(pieces)}</office:automatic-styles>"


def table_rows(blocks: tuple[Block, ...]) -> str:
    lettered = {block.name: block for block in blocks}
    rows = []
    for index, (name, _) in enumerate(LAYOUT):
        block = lettered.get(name)
        if block is None:
            cell = (
                '<table:table-cell table:style-name="Plain" office:value-type="string">'
                '<text:p text:style-name="Blank"/></table:table-cell>'
            )
        else:
            paragraphs = "".join(
                f'<text:p text:style-name="P{block.name}">'
                f'<text:span text:style-name="T{block.name}">{escape(line)}</text:span>'
                "</text:p>"
                for line in block.lines
            )
            style = "Sideways" if block.vertical else "Upright"
            cell = (
                f'<table:table-cell table:style-name="{style}" office:value-type="string">'
                f"{paragraphs}</table:table-cell>"
            )
        rows.append(
            f'<table:table-row table:style-name="Row{index}">{cell}</table:table-row>'
        )
    return "".join(rows)


def content_xml(blocks: tuple[Block, ...], width_pt: float, family: str, font_path: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-content {ODF_NAMESPACES} office:version="1.3">'
        f"{font_declaration(family, font_path)}"
        f"{automatic_styles(blocks, width_pt, family)}"
        "<office:body><office:text>"
        '<table:table table:name="Spine" table:style-name="Spine">'
        '<table:table-column table:style-name="SpineColumn"/>'
        f"{table_rows(blocks)}"
        "</table:table>"
        "</office:text></office:body></office:document-content>"
    )


def styles_xml(width_pt: float, family: str, font_path: str) -> str:
    """The page itself: as tall as the thesis, as wide as the spine, no margins."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-styles {ODF_NAMESPACES} office:version="1.3">'
        f"{font_declaration(family, font_path)}"
        "<office:styles>"
        '<style:style style:name="Standard" style:family="paragraph" style:class="text">'
        '<style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt" '
        'fo:text-align="start" style:writing-mode="lr-tb"/></style:style>'
        "</office:styles>"
        "<office:automatic-styles>"
        '<style:page-layout style:name="Spine">'
        f"<style:page-layout-properties fo:page-width={quoteattr(pt(width_pt))} "
        f"fo:page-height={quoteattr(pt(PAGE_HEIGHT_PT))} "
        'style:print-orientation="portrait" fo:margin-top="0pt" fo:margin-bottom="0pt" '
        'fo:margin-left="0pt" fo:margin-right="0pt" style:writing-mode="lr-tb" '
        'style:footnote-max-height="0pt"/>'
        "<style:header-style/><style:footer-style/></style:page-layout>"
        "</office:automatic-styles>"
        "<office:master-styles>"
        '<style:master-page style:name="Standard" style:page-layout-name="Spine"/>'
        "</office:master-styles></office:document-styles>"
    )


def meta_xml(metadata: dict[str, str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" office:version="1.3"><office:meta>'
        f"<dc:title>{escape(metadata['title'])}</dc:title>"
        f"<dc:subject>{escape(metadata['subject'])}</dc:subject>"
        f"<dc:description>{escape(metadata['keywords'])}</dc:description>"
        f"<meta:generator>{escape(metadata['producer'])}</meta:generator>"
        "</office:meta></office:document-meta>"
    )


def settings_xml() -> str:
    """Keep the embedded font with the document when a print shop re-saves it."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:config="urn:oasis:names:tc:opendocument:xmlns:config:1.0" office:version="1.3">'
        '<office:settings><config:config-item-set config:name="ooo:configuration-settings">'
        '<config:config-item config:name="EmbedFonts" config:type="boolean">true</config:config-item>'
        '<config:config-item config:name="EmbedOnlyUsedFonts" config:type="boolean">true</config:config-item>'
        "</config:config-item-set></office:settings></office:document-settings>"
    )


def manifest_xml(font_path: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.3">'
        '<manifest:file-entry manifest:full-path="/" manifest:version="1.3" '
        'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>'
        f"<manifest:file-entry manifest:full-path={quoteattr(font_path)} "
        'manifest:media-type="application/x-font-ttf"/>'
        "</manifest:manifest>"
    )


def write_odt(
    blocks: tuple[Block, ...],
    width_pt: float,
    family: str,
    font_bytes: bytes,
    metadata: dict[str, str],
    target: Path,
) -> None:
    font_path = f"Fonts/{re.sub(r'[^A-Za-z0-9._-]', '-', family)}.ttf"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        # The mimetype has to come first and unstored, so that a reader can
        # identify the file from its first bytes without inflating anything.
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/manifest.xml", manifest_xml(font_path))
        archive.writestr("content.xml", content_xml(blocks, width_pt, family, font_path))
        archive.writestr("styles.xml", styles_xml(width_pt, family, font_path))
        archive.writestr("meta.xml", meta_xml(metadata))
        archive.writestr("settings.xml", settings_xml())
        archive.writestr(font_path, font_bytes)
    logging.info("Wrote %s", target)


# --------------------------------------------------------------------------
# Driving the two bindings
# --------------------------------------------------------------------------


def spine_metadata(text: SpineText, binding: Binding, thickness: Thickness) -> dict[str, str]:
    return {
        "title": f"{text.university}{text.degree}書側（{binding.name_zh}）",
        "author": text.author,
        "subject": f"{text.university}{text.institute}{text.degree}書側",
        "keywords": f"{binding.name_zh}書背寬 {thickness.width_mm:g} mm",
        "creator": "scripts/make_spine.py",
        "producer": "scripts/make_spine.py",
    }


def verify(
    odt: Path,
    pdf: Path,
    blocks: tuple[Block, ...],
    width_pt: float,
    family: str,
) -> None:
    """Refuse to report success until both files hold what was asked for."""
    expected = "".join(line for block in blocks for line in block.lines)
    with pymupdf.open(pdf) as document:
        if document.page_count != 1:
            raise CollectionError(f"{pdf.name} holds {document.page_count} pages, not one.")
        page = document[0]
        if abs(page.rect.width - width_pt) > 0.01:
            raise CollectionError(
                f"{pdf.name} is {page.rect.width:.2f}pt wide, not {width_pt:.2f}pt."
            )
        if abs(page.rect.height - PAGE_HEIGHT_PT) > 0.01:
            raise CollectionError(f"{pdf.name} is not as tall as the thesis page.")
        fonts = page.get_fonts(full=True)
        # PDF writers name an embedded face by its full name, style included,
        # so the family has to be found inside that rather than equal to it.
        embedded = reduced(re.sub(r"^[A-Z]{6}\+", "", fonts[0][3])) if fonts else ""
        if len(fonts) != 1 or reduced(family) not in embedded:
            raise CollectionError(f"{pdf.name} does not set the spine in {family} alone.")
        if not document.extract_font(fonts[0][0])[3]:
            raise CollectionError(f"{pdf.name} does not embed {family}.")
        printed = re.sub(r"\s", "", page.get_text())
        if sorted(printed) != sorted(re.sub(r"\s", "", expected)):
            raise CollectionError(f"{pdf.name} does not print the spine text.")

    with zipfile.ZipFile(odt) as archive:
        names = archive.namelist()
        if names[0] != "mimetype" or archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            raise CollectionError(f"{odt.name} does not open with an unstored mimetype.")
        font_entries = [name for name in names if name.startswith("Fonts/")]
        if len(font_entries) != 1 or not archive.read(font_entries[0]):
            raise CollectionError(f"{odt.name} does not embed {family}.")
        content = archive.read("content.xml").decode("utf-8")
        if font_entries[0] not in content:
            raise CollectionError(f"{odt.name} does not point its styles at the embedded font.")
        for character in set(expected) - set(" 　"):
            if escape(character) not in content:
                raise CollectionError(f"{odt.name} is missing {character!r}.")


def describe(
    binding: Binding, thickness: Thickness, blocks: tuple[Block, ...], odt: Path, pdf: Path
) -> None:
    sides = "雙面 (double-sided)" if thickness.duplex else "單面 (single-sided)"
    print(f"{binding.name_zh} ({binding.key}): {thickness.width_mm:g} mm wide")
    if thickness.measured_mm is None:
        print(
            f"  thickness   {thickness.pages} pages, {sides}, {thickness.sheets} sheets"
            f" x {thickness.paper_mm:g} mm = {thickness.text_block_mm:.2f} mm"
        )
        added = f"{thickness.binding_mm:g} mm cover and glue"
        if thickness.board_mm:
            added += f" + {thickness.board_mm:g} mm board"
        print(f"              + {added} = {thickness.raw_mm:.2f} mm, rounded up")
    else:
        given = f"  thickness   {thickness.measured_mm:g} mm given"
        if thickness.board_mm:
            given += f" + {thickness.board_mm:g} mm board"
        print(f"{given} (the {thickness.pages}-page count says {thickness.computed_mm} mm)")
    for block in blocks:
        note = " (shrunk to fit)" if block.shrunk else ""
        print(f"  {block.name:<9} {block.size_pt:g} pt{note}  {' / '.join(block.lines)}")
    for path in (odt, pdf):
        print(f"  {path.name:<28} {path.stat().st_size:,} bytes")


def build(args: argparse.Namespace) -> None:
    source = args.input.resolve()
    if not source.is_file():
        raise CollectionError(f"No such PDF: {source}. Run `pixi run build` first.")
    with pymupdf.open(source) as document:
        if document.needs_pass:
            raise CollectionError(
                f"{source.name} cannot be opened without a password. Write the spine "
                "from the PDF that `pixi run build` produced."
            )
        pages = args.pages or document.page_count
        cjk = cover_cjk_font_name(document)

    text = read_thesis_text(PROJECT_ROOT)
    font_file = locate_font(cjk, PROJECT_ROOT)
    logging.info("The thesis sets Chinese in %s (%s)", cjk, font_file)
    absent = missing_characters(font_file, text.characters())
    if absent:
        raise CollectionError(f"{font_file.name} has no glyph for {absent!r}.")

    font_bytes = embeddable_font(font_file, text.characters())
    family = font_names(font_file)[0]
    ruler = pymupdf.Font(fontbuffer=font_bytes)

    duplex = pages >= DUPLEX_THRESHOLD_PAGES if args.sides == "auto" else args.sides == "double"
    for binding in BINDINGS:
        if args.binding not in ("both", binding.key):
            continue
        thickness = measure(
            pages,
            binding,
            duplex=duplex,
            paper_mm=args.paper_thickness,
            binding_mm=args.binding_allowance,
            measured_mm=args.spine_width,
        )
        width_pt = mm(thickness.width_mm)
        blocks = lay_out(text, width_pt, ruler)
        metadata = spine_metadata(text, binding, thickness)
        stem = args.output_dir / f"{source.stem}-spine-{binding.key}"
        odt, pdf = stem.with_suffix(".odt"), stem.with_suffix(".pdf")
        write_odt(blocks, width_pt, family, font_bytes, metadata, odt)
        write_pdf(blocks, width_pt, ruler, metadata, pdf)
        verify(odt, pdf, blocks, width_pt, family)
        describe(binding, thickness, blocks, odt, pdf)


def arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "input", nargs="?", type=Path, default=DEFAULT_INPUT,
        help="built thesis PDF (default: main.pdf)",
    )
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=PROJECT_ROOT,
        help="where to write the four files (default: the project root)",
    )
    parser.add_argument(
        "--binding", choices=("both", "paperback", "hardcover"), default="both",
        help="which binding to write (default: both)",
    )
    parser.add_argument(
        "--pages", type=int,
        help="page count to bind, when it differs from the PDF's own",
    )
    parser.add_argument(
        "--sides", choices=("auto", "single", "double"), default="auto",
        help=(
            "how the text pages are printed (default: auto, single-sided below "
            f"{DUPLEX_THRESHOLD_PAGES} pages and double-sided from there up)"
        ),
    )
    parser.add_argument(
        "--paper-thickness", type=float, default=PAPER_THICKNESS_MM, metavar="MM",
        help=f"thickness of one text sheet (default: {PAPER_THICKNESS_MM} mm, 80 磅道林紙)",
    )
    parser.add_argument(
        "--binding-allowance", type=float, default=PAPERBACK_BINDING_MM, metavar="MM",
        help=(
            "what the paperback's cover and glue add to the text block "
            f"(default: {PAPERBACK_BINDING_MM} mm)"
        ),
    )
    parser.add_argument(
        "--spine-width", type=float, metavar="MM",
        help=(
            "measured thickness of the paperback text block and cover, used "
            "instead of the computed one; the hardcover adds its boards on top"
        ),
    )
    return parser


def main() -> int:
    args = arguments().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # fontTools narrates every table it touches; only its complaints matter here.
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    if args.pages is not None and args.pages < 1:
        logging.error("--pages must be positive.")
        return 1
    if args.paper_thickness <= 0 or args.binding_allowance < 0:
        logging.error("Paper thickness must be positive and the binding allowance non-negative.")
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        build(args)
    except (CollectionError, ValueError, pymupdf.FileDataError, OSError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
