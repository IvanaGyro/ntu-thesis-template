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
* the PDF, drawn here rather than converted, so that writing a spine needs
  nothing on the machine beyond the packages `pixi` installs.

Both are laid out from one table of measurements taken off NTU's official
spine form, and both set every character on the glyph HarfBuzz chooses for a
vertical line, so the two agree by construction. The text runs top to bottom
in 真正直書 (true vertical setting), the way the form has it: the university
and the institute side by side at the head, then the degree, the title, the
author, and the ROC year and month at the foot.

What it says comes from main.tex and ntusetup.tex -- the thesis's own source,
read with the same parser the TDR upload filler uses. The built PDF is opened
only to be counted.

Like `cover` and `protect`, this step is deliberately manual; `pixi run build`
never calls it.
"""

from __future__ import annotations

import argparse
import bisect
import io
import logging
import math
import os
import re
import subprocess
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pymupdf
import uharfbuzz as hb
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
# Below this many pages of the built PDF a thesis is printed single-sided, one
# page per sheet; at or above it, double-sided, two pages per sheet. Every
# page of the built PDF is an interior page -- the card cover is printed from
# `pixi run cover`, which reproduces page one rather than replacing it -- so
# the count is simply the PDF's own.
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

# One character's worth of room left at the foot of every vertical line. An
# exact fit is not a safe one: the layout puts each line in a column of its
# own, and a reader whose metrics make it a hair longer -- a Latin space
# inside a CJK line is enough -- would break it into a second column and lay
# the whole block out differently. LibreOffice ignores fo:wrap-option on a
# Writer cell, so the room has to be left rather than the wrap forbidden.
LINE_SLACK_EM = 1.0

# 封面第一行的頂端與最後一行的底端，寫死，因為類別也是寫死的。
# Where the cover's text starts and ends. \\makecover sets the cover inside a
# 3 cm margin on a fixed A4 page and spreads it with \\vfill, so its first line
# begins and its last line ends in the same two places in every thesis: these
# are those places, measured off a build, and the spine is stretched between
# them. A change to \\ntu@geometry@cover or to the cover's 18 pt on 27 pt body
# is a change to these two numbers.
COVER_TOP_PT = 83.9
COVER_BOTTOM_PT = 748.2
COVER_TEXT_HEIGHT_PT = COVER_BOTTOM_PT - COVER_TOP_PT

# How close to the edge of the spine a character may set. The official 8 mm
# sample leaves about 0.3 mm beside its widest line, the year; a quarter of a
# millimetre is a shade tighter than that, so a spine as wide as the sample
# still sets at the form's own sizes, and a narrower one shrinks rather than
# running its characters off the fold.
SIDE_CLEARANCE_MM = 0.25


# --------------------------------------------------------------------------
# What the spine says
# --------------------------------------------------------------------------
#
# main.tex and ntusetup.tex, read with the same parser the TDR filler uses.
# The source rather than the built cover: \ntusetup holds one value per key,
# so a title arrives whole instead of broken across the lines typesetting put
# it on, and the university, the college and the institute arrive apart
# instead of run together into one line that would have to be divided again.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from thesis_metadata import (  # noqa: E402
    CollectionError,
    class_options,
    collapse_spaces,
    parse_ntusetup,
)

# 「撰」 follows the author's name after an ideographic space, as on the form.
AUTHOR_SUFFIX = "　撰"

# 書名頁上的學位論文名稱，由 degree 類別選項決定。
DEGREE_NAMES = {"master": "碩士論文", "doctor": "博士論文"}

# ntusetup.tex 的 date 是 YYYY-MM-DD；留白時類別用今天，這裡也是。
ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
ROC_EPOCH = 1911


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


def value(setup: dict[str, str], key: str) -> str:
    """One \\ntusetup value, as the class would set it.

    TeX turns any run of whitespace into a single space, so the spine reads a
    wrapped source value the way the cover prints it. Composed, because a
    vertical line gives every character a slot of its own and a decomposed
    accent or kana mark would take a second one.
    """
    return unicodedata.normalize("NFC", collapse_spaces(setup.get(key, "")))


def roc_date(given: str) -> tuple[int, int]:
    """民國年與月份。The class dates an undated thesis today, and so does this."""
    if not given:
        today = date.today()
        return today.year - ROC_EPOCH, today.month
    written = ISO_DATE.fullmatch(given)
    if not written:
        raise CollectionError(
            f"ntusetup.tex dates the thesis {given!r}, which is not the YYYY-MM-DD "
            "the class expects, so the spine cannot letter its year and month."
        )
    return int(written.group(1)) - ROC_EPOCH, int(written.group(2))


def read_spine_text(root: Path) -> SpineText:
    """Collect what the spine letters, in the thesis's own words.

    The form gives the head two columns: the university in the right-hand one
    and the institute in the left. \\ntusetup names them separately, and the
    college it prints between them on the cover is on neither column of the
    form, so nothing has to be taken apart to letter it.
    """
    options = class_options(root / "main.tex")
    setup = parse_ntusetup(root / "ntusetup.tex")
    degree = DEGREE_NAMES.get(options.get("degree", "master"))
    if degree is None:
        raise CollectionError(
            f"main.tex sets degree = {options['degree']}, which is neither master "
            "nor doctor, so the spine cannot name the thesis."
        )
    absent = [key for key in ("university", "institute", "title", "author") if not value(setup, key)]
    if absent:
        raise CollectionError(
            f"ntusetup.tex leaves {', '.join(absent)} empty, so the spine has "
            "nothing to letter there."
        )
    year, month = roc_date(value(setup, "date"))
    return SpineText(
        university=value(setup, "university"),
        institute=value(setup, "institute"),
        degree=degree,
        title=value(setup, "title"),
        author=value(setup, "author"),
        roc_year=year,
        month=month,
    )


def reduced(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def same_font(name: str, candidate: str) -> bool:
    return reduced(name) == reduced(candidate)


@dataclass(frozen=True)
class FontFile:
    """A face on disk. A .ttc holds several, so the index travels with the path."""

    path: Path
    index: int = 0

    @property
    def name(self) -> str:
        return self.path.name if not self.index else f"{self.path.name}#{self.index}"

    def open(self, **kwargs) -> TTFont:
        return TTFont(self.path, fontNumber=self.index, **kwargs)


def font_names(font: FontFile) -> tuple[str, ...]:
    """The family, full and PostScript names a face answers to.

    Users drop their own files into fonts/ for fontset=template, so anything
    that will not open as a font is simply not the font being looked for.
    """
    try:
        with font.open(lazy=True) as opened:
            table = opened["name"]
            return tuple(name for name in (table.getDebugName(i) for i in (1, 4, 6)) if name)
    except Exception:  # noqa: BLE001 - fontTools raises a different type per defect
        logging.debug("Not a readable font: %s", font.name)
        return ()


def installed_fonts() -> list[FontFile]:
    """Every face fontconfig knows about, collections expanded.

    A machine without fontconfig has nothing to answer with, which is not an
    error: the shipped faces are found without it.
    """
    try:
        listed = subprocess.run(
            ["fc-list", "--format=%{file}\t%{index}\n"],
            capture_output=True,
            text=True,
        )
    except OSError:
        logging.debug("No fc-list on this machine, so only the shipped faces are known.")
        return []
    if listed.returncode != 0:
        return []
    found = []
    for row in listed.stdout.splitlines():
        path, _, index = row.partition("\t")
        if path:
            found.append(FontFile(Path(path), int(index) if index.isdigit() else 0))
    return found


# 中文字型的來源，抄自 ntuthesis.cls 的 fontset 與 cjkfont 分支。
# Where the class loads its Chinese face from, per fontset:
#   default, tinos, (unset)  the shipped file cjkfont names, by path
#   template                 the user's own BiauKai.ttf, by path
#   system, overleaf         a family name, resolved by the machine
CJK_DIRECTORY = "fonts/chinese"
CJK_SHIPPED = {"kai": "TW-Kai-98_1.ttf", "sung": "TW-Sung-98_1.ttf"}
CJK_TEMPLATE_FILE = "BiauKai.ttf"
CJK_FAMILIES = {"system": "BiauKai", "overleaf": "AR PL KaitiM Big5"}


def locate_font(options: dict[str, str], root: Path) -> FontFile:
    """The file the class sets Chinese in, found the way the class finds it.

    Two of the fontsets name a family and leave the machine to resolve it, so
    fontconfig is asked for what it has rather than asked to match: it answers
    a request for a face it does not have with a metric-compatible stand-in,
    and a spine lettered in the stand-in would look nothing like the cover.
    Each candidate is opened and made to say for itself that it is the face
    asked for; a .ttc is several faces in one file, and only one is the answer.
    """
    fontset = options.get("fontset", "default")
    if fontset in CJK_FAMILIES:
        family = CJK_FAMILIES[fontset]
        for candidate in installed_fonts():
            if any(same_font(family, found) for found in font_names(candidate)):
                return candidate
        raise CollectionError(
            f"main.tex builds with fontset = {fontset}, which sets Chinese in "
            f"{family}, and no such face is installed on this machine. Install "
            "it, or build with a fontset whose Chinese face ships with the template."
        )
    if fontset == "template":
        path = root / CJK_DIRECTORY / CJK_TEMPLATE_FILE
    else:
        path = root / CJK_DIRECTORY / CJK_SHIPPED.get(options.get("cjkfont", "kai"), "")
    if not path.is_file():
        raise CollectionError(
            f"main.tex builds with fontset = {fontset}, which sets Chinese in "
            f"{path}, and that file is not there. See fonts/README.md."
        )
    return FontFile(path)


# The Chinese faces this template redistributes, named by the files they are.
# One thing is true of these and of no others: their licences (政府資料開放授權
# 條款-1.0 or OFL-1.1) permit a modified version, so a subset of them may be
# written with its embedding rights relaxed and travel inside the ODT.
SHIPPED_FILES = ("fonts/chinese/TW-Kai-98_1.ttf", "fonts/chinese/TW-Sung-98_1.ttf")


def redistributed(font: FontFile, root: Path) -> bool:
    """Whether a file is one of the two faces this repository ships.

    The question a name cannot answer: what those licences cover is these
    files, and one of the user's own that merely answers to their names is not
    covered -- relabelling its embedding rights would hand out a permission
    nobody gave. Only the fontsets that load a face by path can reach these,
    so comparing the path is the whole test.
    """
    return any(
        font.path.resolve() == (root / relative).resolve() for relative in SHIPPED_FILES
    )


# OS/2 fsType, the font's own statement of what may be embedded where.
# The permission itself is the low four bits, and it is a level rather than a
# set of flags: zero is installable, the most permissive of all. The bits above
# it are separate restrictions and say nothing about that level.
FSTYPE_LEVEL = 0x000F
FSTYPE_RESTRICTED = 0x0002  # embedding forbidden without the vendor's leave
FSTYPE_EDITABLE = 0x0008  # embedding allowed in a document that can be edited
FSTYPE_NO_SUBSETTING = 0x0100  # embed the whole face or none of it
FSTYPE_BITMAP_ONLY = 0x0200  # only the bitmaps inside it, never the outlines


@dataclass(frozen=True)
class Embedding:
    """A face cut to size, with what its own terms allow done to it."""

    face: bytes
    editable: bool  # may travel inside a document that can be edited
    subsettable: bool  # may be cut down further


def embeddable_font(font: FontFile, characters: str, relabel: bool) -> Embedding:
    """Cut the face down to the glyphs the spine prints, and say where it may go.

    The shipped 全字庫 faces are tens of megabytes; a spine sets a few dozen
    characters. Every name record is kept so that the family name in the ODT
    still resolves to the embedded file.

    Whether the ODT may carry the subset is the second answer. An ODT is a
    document that can be edited, which `fsType` level 4 does not allow, and an
    office suite honours only a face marked installable -- it substitutes
    something else, silently, for one that is not. The template's own faces
    may simply be marked installable, their licences permitting a modified
    version; a face belonging to the user may not be relabelled on their
    behalf, so the ODT names it and LibreOffice sets it from the copy this
    machine has installed.
    """
    with font.open(lazy=True) as probe:
        rights = probe["OS/2"].fsType
    level = rights & FSTYPE_LEVEL
    if level & FSTYPE_RESTRICTED:
        raise CollectionError(
            f"{font.name} forbids embedding, so it cannot travel inside the spine "
            "files. Build the thesis with a fontset whose Chinese face ships with "
            "the template."
        )
    if rights & FSTYPE_BITMAP_ONLY:
        # A spine is lettered at whatever size it takes, and what would travel
        # inside the ODT is the outlines; a face that allows only its bitmaps
        # to go cannot go, whatever else its rights permit.
        raise CollectionError(
            f"{font.name} allows only its bitmaps to be embedded, not its outlines, "
            "which is what the spine files carry. Build the thesis with a fontset "
            "whose Chinese face ships with the template."
        )

    options = subset.Options()
    # `vert` has to survive the cut, along with the glyphs it substitutes in:
    # an office suite applies it to the ODT itself, and the PDF's copy of the
    # face is this one with those glyphs already put in place.
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.recalc_bounds = True
    options.font_number = font.index
    face = subset.load_font(str(font.path), options)
    if rights & FSTYPE_NO_SUBSETTING:
        logging.warning("%s asks not to be subset; embedding it whole.", font.name)
    else:
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=characters)
        subsetter.subset(face)

    editable = not level or bool(level & FSTYPE_EDITABLE)
    if not editable and relabel:
        face["OS/2"].fsType = 0
        editable = True
    elif not editable:
        logging.warning(
            "%s allows embedding for print but not for editing, and is not one of "
            "the faces this template may relabel. The PDF carries it, which is "
            "what a print permission covers; the ODT names it instead, so open "
            "that on a machine which has the face installed.",
            font.name,
        )
    written = io.BytesIO()
    face.save(written)
    face.close()
    return Embedding(written.getvalue(), editable, not rights & FSTYPE_NO_SUBSETTING)


def missing_characters(font: FontFile, characters: str) -> str:
    with font.open(lazy=True) as opened:
        table = opened.getBestCmap()
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


def measure(pages: int, binding: Binding, measured_mm: float | None = None) -> Thickness:
    duplex = pages >= DUPLEX_THRESHOLD_PAGES
    return Thickness(
        pages=pages,
        duplex=duplex,
        sheets=math.ceil(pages / 2) if duplex else pages,
        paper_mm=PAPER_THICKNESS_MM,
        binding_mm=PAPERBACK_BINDING_MM,
        board_mm=binding.board_mm,
        measured_mm=measured_mm,
    )


# --------------------------------------------------------------------------
# Placing the text
# --------------------------------------------------------------------------
#
# Vertical CJK setting is not simply horizontal text turned on its side. Every
# wide character keeps its upright shape and takes a slot one em deep, while a
# run of Latin -- letters, digits, anything narrow -- turns a quarter turn and
# runs down the column at its own width. Punctuation gets a different shape
# again, which the font's own `vert` feature supplies.


# Which characters a vertical line stands upright and which it turns on its
# side is the Vertical_Orientation property of UTR#50 (Unicode Vertical Text
# Layout), and East Asian width is not a usable stand-in for it: × and ± stand
# up where ° and → turn, though all four are ambiguous-width symbols. These
# are the ranges that stand upright, from `VerticalOrientation-17.txt` at
# <https://www.unicode.org/Public/vertical/revision-17/>, taking the U and Tu
# values; Tr -- transformed, falling back to rotated -- where the character is
# wide, since a CJK face gives those a vertical form and LibreOffice draws
# that upright; and the wide letters added to Unicode since that file's
# repertoire, which its default would otherwise turn. Sorted and merged, so
# the lookup can bisect.
UPRIGHT_RANGES = (
    (0x00A7, 0x00A7), (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x00B1, 0x00B1),
    (0x00BC, 0x00BE), (0x00D7, 0x00D7), (0x00F7, 0x00F7), (0x02EA, 0x02EB),
    (0x1100, 0x11FF), (0x1401, 0x167F), (0x18B0, 0x18FF), (0x2016, 0x2016),
    (0x2020, 0x2021), (0x2030, 0x2031), (0x203B, 0x203C), (0x2042, 0x2042),
    (0x2047, 0x2049), (0x2051, 0x2051), (0x2065, 0x2065), (0x20DD, 0x20E0),
    (0x20E2, 0x20E4), (0x2100, 0x2101), (0x2103, 0x2109), (0x210F, 0x210F),
    (0x2113, 0x2114), (0x2116, 0x2117), (0x211E, 0x2123), (0x2125, 0x2125),
    (0x2127, 0x2127), (0x2129, 0x2129), (0x212E, 0x212E), (0x2135, 0x213F),
    (0x2145, 0x214A), (0x214C, 0x214D), (0x214F, 0x2189), (0x218C, 0x218F),
    (0x221E, 0x221E), (0x2234, 0x2235), (0x2300, 0x2307), (0x230C, 0x231F),
    (0x2324, 0x232B), (0x237D, 0x239A), (0x23BE, 0x23CD), (0x23CF, 0x23CF),
    (0x23D1, 0x23DB), (0x23E2, 0x2422), (0x2424, 0x24FF), (0x25A0, 0x2619),
    (0x2620, 0x2767), (0x2776, 0x2793), (0x2B12, 0x2B2F), (0x2B50, 0x2B59),
    (0x2BB8, 0x2BEB), (0x2BF0, 0x2BFF), (0x2E80, 0xA4CF), (0xA960, 0xA97F),
    (0xAC00, 0xD7FF), (0xE000, 0xFAFF), (0xFE10, 0xFE1F), (0xFE30, 0xFE48),
    (0xFE50, 0xFE57), (0xFE59, 0xFE62), (0xFE67, 0xFE6F), (0xFF01, 0xFF0C),
    (0xFF0E, 0xFF1B), (0xFF1F, 0xFF60), (0xFFE0, 0xFFE7), (0xFFF0, 0xFFF8),
    (0xFFFC, 0xFFFD), (0x10980, 0x1099F), (0x11580, 0x115FF), (0x13000, 0x1342F),
    (0x14400, 0x1467F), (0x16FE0, 0x18CD5), (0x18D00, 0x18D08), (0x1B000, 0x1B122),
    (0x1B132, 0x1B132), (0x1B150, 0x1B152), (0x1B155, 0x1B155), (0x1B164, 0x1B167),
    (0x1B170, 0x1B2FB), (0x1D000, 0x1D1FF), (0x1D300, 0x1D37F), (0x1D800, 0x1DAAF),
    (0x1F000, 0x1F7FF), (0x1F900, 0x1F9FF), (0x20000, 0x2FFFD), (0x30000, 0x3FFFD),
    (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD),
)
UPRIGHT_STARTS = tuple(start for start, _ in UPRIGHT_RANGES)


def upright(character: str) -> bool:
    """Whether a character stands up in a vertical line or turns on its side.

    The Latin alphabet turns, and its accents turn with it, so a `Café` that
    reaches us decomposed does not part company with its accent. CJK stands
    up, and so do the marks a CJK line sets upright -- ×, ±, §, ※ -- while
    the ones it does not, ° and the arrows and the relations among them,
    turn with the run around them.
    """
    place = bisect.bisect_right(UPRIGHT_STARTS, ord(character)) - 1
    return place >= 0 and ord(character) <= UPRIGHT_RANGES[place][1]


@dataclass(frozen=True)
class Run:
    """A stretch of one line that shares an orientation."""

    text: str
    turned: bool
    advance: float  # in em, so that a point size scales it


def split_runs(line: str, ruler: pymupdf.Font) -> tuple[Run, ...]:
    """Break a line into upright characters and turned Latin runs.

    Each upright character is its own run so that justification can open the
    gaps between them, the way a vertical CJK line stretches.
    """
    runs: list[Run] = []
    for character in line:
        if upright(character):
            runs.append(Run(character, False, 1.0))
            continue
        if runs and runs[-1].turned:
            grown = runs[-1].text + character
            runs[-1] = Run(grown, True, ruler.text_length(grown, fontsize=1.0))
        else:
            runs.append(Run(character, True, ruler.text_length(character, fontsize=1.0)))
    return tuple(runs)


@dataclass(frozen=True)
class Line:
    """One column of a block, already broken into runs."""

    runs: tuple[Run, ...]

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)

    @property
    def advance(self) -> float:
        """How deep the line sets, in em."""
        return sum(run.advance for run in self.runs)


@dataclass(frozen=True)
class Block:
    """One lettered row of the form, sized and positioned on the page."""

    name: str
    top_pt: float
    height_pt: float
    lines: tuple[Line, ...]
    size_pt: float
    pitch_pt: float
    ascent: float
    extent: float  # a line box's depth in em: the ascent less the descent
    vertical: bool
    justified: bool

    @property
    def shrunk(self) -> bool:
        return self.size_pt < NOMINAL_SIZE_PT[self.name] - 1e-6

    @property
    def texts(self) -> tuple[str, ...]:
        return tuple(line.text for line in self.lines)

    def placed(self, index: int) -> list[tuple[Run, float]]:
        """Every run of line `index` with the page offset of its slot's top.

        A vertical line hands each run a slot as deep as its advance and hangs
        the run from the top of it; justification widens the gaps between the
        slots without changing what any of them holds.
        """
        if not self.vertical:
            return []
        line = self.lines[index]
        deep = line.advance * self.size_pt
        if self.justified and len(line.runs) > 1:
            gap = (self.height_pt - deep) / (len(line.runs) - 1)
            start = self.top_pt
        else:
            gap = 0.0
            start = self.top_pt + (self.height_pt - deep) / 2
        placement, offset = [], start
        for run in line.runs:
            placement.append((run, offset))
            offset += run.advance * self.size_pt + gap
        return placement

    def centre_pt(self, index: int, width_pt: float) -> float:
        """Where line `index` sits across the spine.

        Vertical lines stack right to left, so the first line of a block is
        its rightmost column.
        """
        offset = (len(self.lines) - 1) / 2 - index
        return width_pt / 2 + offset * self.pitch_pt

    @property
    def ink_top_pt(self) -> float:
        """The top of the block's first line box, leading excluded.

        Measured the same way the cover is, so that aligning one against the
        other compares like with like.
        """
        if not self.vertical:
            leading = self.pitch_pt - self.size_pt * self.extent
            return self.top_pt + (self.height_pt - len(self.lines) * self.pitch_pt + leading) / 2
        return min(self.placed(index)[0][1] for index in range(len(self.lines)))

    @property
    def ink_bottom_pt(self) -> float:
        if not self.vertical:
            return (
                self.ink_top_pt
                + (len(self.lines) - 1) * self.pitch_pt
                + self.size_pt * self.extent
            )
        ends = []
        for index in range(len(self.lines)):
            run, offset = self.placed(index)[-1]
            ends.append(offset + run.advance * self.size_pt)
        return max(ends)


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
    lines: tuple[Line, ...],
    height_pt: float,
    width_pt: float,
) -> tuple[float, float]:
    """Return the point size and line pitch that keep a block inside its row.

    The form's sizes suit the titles it was drawn with. A longer institute
    name, a longer title or a narrower spine has to give, and it gives by
    setting smaller rather than by running over the edge of the artwork.
    """
    across = width_pt - 2 * mm(SIDE_CLEARANCE_MM)
    deepest = max(line.advance for line in lines)
    if name == "date":
        # The date is the one horizontal block: it runs across the spine, and
        # its lines stack down the row rather than beside each other.
        size = capped(name, across / deepest, height_pt / (len(lines) * DATE_LINE_PITCH))
        return size, size * DATE_LINE_PITCH
    pitch_factor = HEADING_COLUMN_PITCH if name == "heading" else 1.0
    size = capped(
        name, height_pt / (deepest + LINE_SLACK_EM), across / (pitch_factor * len(lines))
    )
    return size, size * pitch_factor


@dataclass(frozen=True)
class Spine:
    """The whole page: every row in order, and the blocks among them."""

    width_pt: float
    rows: tuple[tuple[float, Block | None], ...]

    @property
    def blocks(self) -> tuple[Block, ...]:
        return tuple(block for _, block in self.rows if block is not None)

    @property
    def ink_top_pt(self) -> float:
        return min(block.ink_top_pt for block in self.blocks)

    @property
    def ink_bottom_pt(self) -> float:
        return max(block.ink_bottom_pt for block in self.blocks)


def form_heights() -> list[float]:
    """The row heights of NTU's form, as drawn."""
    return [inch(height_in) for _, height_in in LAYOUT]


def form_foot_pt() -> float:
    """How far down the sheet the form's own table reaches."""
    return sum(form_heights())


def build_rows(
    text: SpineText, width_pt: float, ruler: pymupdf.Font, heights: list[float]
) -> Spine:
    """Fill the rows, each block sized to whatever room its own row leaves."""
    rows: list[tuple[float, Block | None]] = []
    top = 0.0
    for (name, _), height in zip(LAYOUT, heights):
        block = None
        if name:
            lines = tuple(Line(split_runs(line, ruler)) for line in text.block(name))
            size, pitch = fit_size(name, lines, height, width_pt)
            block = Block(
                name=name,
                top_pt=top,
                height_pt=height,
                lines=lines,
                size_pt=size,
                pitch_pt=pitch,
                ascent=ruler.ascender,
                extent=ruler.ascender - ruler.descender,
                vertical=name != "date",
                justified=name == "heading",
            )
        rows.append((height, block))
        top += height
    return Spine(width_pt=width_pt, rows=tuple(rows))


def block_room(block: Block) -> tuple[float, float]:
    """A block's own row height, and how far its ink starts below that row's top.

    A vertical block fills its row exactly, so its row is as deep as its ink.
    The date stacks line boxes instead, and half a line's leading sits above
    the first of them.
    """
    if block.vertical:
        deep = max(line.advance for line in block.lines) * block.size_pt
        room = deep + LINE_SLACK_EM * block.size_pt
        # A justified line starts at the top of its row; a centred one sits in
        # the middle of it, so half the slack is above the ink.
        return room, 0.0 if block.justified else (room - deep) / 2
    leading = block.pitch_pt - block.size_pt * block.extent
    return len(block.lines) * block.pitch_pt, leading / 2


def lay_out(text: SpineText, width_pt: float, ruler: pymupdf.Font) -> Spine:
    """Lay the spine out, stretched to the same extent as the cover's text.

    NTU's form is drawn for a generic cover. On a bound book the spine reads
    better when its first character starts level with the cover's first line
    and its last finishes level with the cover's last, so that the two faces
    of the book agree.

    What gives is the space, not the type. The degree, the title, the author
    and the date keep the point sizes the format rules name, so their depth is
    already settled; the gaps between them, and the depth the heading
    justifies across, take up the difference in one proportion. The two ends
    then land on the cover's by construction, and the table finishes where the
    cover's last line does, so it always fits the sheet.
    """
    form = build_rows(text, width_pt, ruler, form_heights())
    blocks = form.blocks
    settled = sum(block.ink_bottom_pt - block.ink_top_pt for block in blocks[1:])
    elastic = blocks[0].height_pt + sum(
        after.ink_top_pt - before.ink_bottom_pt for before, after in zip(blocks, blocks[1:])
    )
    if COVER_TEXT_HEIGHT_PT <= settled or elastic <= 0:
        raise CollectionError(
            "The spine's own lines are deeper than the cover's text, so the two "
            "cannot be made to line up. The title is the usual reason."
        )
    stretch = (COVER_TEXT_HEIGHT_PT - settled) / elastic

    heights = form_heights()
    lettered = [index for index, (name, _) in enumerate(LAYOUT) if name]
    ink_top, filled, previous = COVER_TOP_PT, 0.0, -1
    for order, index in enumerate(lettered):
        block = blocks[order]
        if order:
            ink_top += (block.ink_top_pt - blocks[order - 1].ink_bottom_pt) * stretch
        room, inset = block_room(block)
        if order == 0:
            room = block.height_pt * stretch
        # Whatever lies between the last row and this one is blank, and the
        # form's own proportions decide how it is shared out.
        blank = ink_top - inset - filled
        shares = [inch(LAYOUT[row][1]) for row in range(previous + 1, index)]
        for row, share in zip(range(previous + 1, index), shares):
            heights[row] = blank * share / sum(shares)
        heights[index] = room
        filled = ink_top - inset + room
        ink_top += block.ink_bottom_pt - block.ink_top_pt if order else room
        previous = index

    # The form's table stops short of the foot of the sheet, and the stretched
    # one stops in the same place: filling the page to its edge would leave an
    # office suite's own rounding nowhere to go but a second page.
    heights[-1] = form_foot_pt() - sum(heights[:-1])
    if heights[-1] < 0:
        raise CollectionError(
            "Lining the spine up with the cover would run it past the foot of the "
            "form's table."
        )
    return build_rows(text, width_pt, ruler, heights)


# --------------------------------------------------------------------------
# The PDF
# --------------------------------------------------------------------------


def vertical_forms(font: FontFile, characters: str) -> dict[str, str]:
    """The glyph a vertical line draws each character with, named.

    Vertical CJK does not merely turn the page: a bracket, a comma or a full
    stop takes a different shape down a column, and which shape lives in the
    font rather than at a code point of its own. HarfBuzz is asked for it --
    the shaper an office suite lays the ODT out with -- rather than the
    font's feature tables being read here and applied by guesswork.

    Only what stands upright is asked about: a turned run is drawn from the
    horizontal form and rotated, so a vertical form folded into one of those
    would be turned twice.
    """
    face = hb.Face(hb.Blob.from_file_path(str(font.path)), font.index)
    shaper = hb.Font(face)
    with font.open(lazy=True) as opened:
        names = opened.getGlyphOrder()

    def glyphs(character: str, direction: str) -> list[int]:
        buffer = hb.Buffer()
        buffer.add_str(character)
        buffer.guess_segment_properties()
        buffer.direction = direction
        hb.shape(shaper, buffer)
        return [info.codepoint for info in buffer.glyph_infos]

    forms = {}
    for character in characters:
        if not upright(character):
            continue
        down, across = glyphs(character, "ttb"), glyphs(character, "ltr")
        if len(down) == 1 and down != across:
            forms[character] = names[down[0]]
    return forms


def drawn_face(font_bytes: bytes, forms: dict[str, str]) -> bytes:
    """The copy of the face the PDF draws from, with two corrections.

    The first is the vertical forms. A PDF carries glyphs already chosen, so
    folding the shaper's choice into this copy's character map is what puts
    the vertical shapes on the page. The mapping back to Unicode is
    untouched, so the PDF still reads as what it says.

    The second is `post.isFixedPitch`. 標楷體 sets it, though its ideographs
    are a full em wide and its digits half of one, and a PDF writer that
    believes it emits a single width for every glyph -- which sets the year on
    the spine as three digits piled on top of each other. Clearing the flag
    costs a font that really is monospaced nothing: its widths are then simply
    written out, and they all still agree.
    """
    face = TTFont(io.BytesIO(font_bytes))
    kept = set(face.getGlyphOrder())
    turned = 0
    for table in face["cmap"].tables:
        for code, name in list(table.cmap.items()):
            wanted = forms.get(chr(code))
            if wanted and wanted in kept and name != wanted:
                table.cmap[code] = wanted
                turned += 1
    if turned:
        logging.info("Set %d character(s) in their vertical form.", turned)
    if face["post"].isFixedPitch:
        logging.info(
            "%s claims to be monospaced; writing its real widths.",
            face["name"].getDebugName(1),
        )
        face["post"].isFixedPitch = 0
    written = io.BytesIO()
    face.save(written)
    face.close()
    return written.getvalue()


def write_pdf(
    spine: Spine,
    font: pymupdf.Font,
    metadata: dict[str, str],
    target: Path,
    subsettable: bool = True,
) -> None:
    """Draw the spine, run by run, where the layout puts it.

    Upright characters are centred in their column, each on the glyph the
    shaper chose for a vertical line. A turned run is drawn horizontally and
    rotated a quarter turn clockwise about its own start, which is how a
    vertical line sets Latin.
    """
    with pymupdf.open() as document:
        page = document.new_page(width=spine.width_pt, height=PAGE_HEIGHT_PT)
        upright_text = pymupdf.TextWriter(page.rect)
        turned: list[tuple[pymupdf.TextWriter, pymupdf.Point]] = []
        for block in spine.blocks:
            if not block.vertical:
                draw_across(block, spine.width_pt, font, upright_text)
                continue
            for index in range(len(block.lines)):
                centre = block.centre_pt(index, spine.width_pt)
                for run, offset in block.placed(index):
                    if run.turned:
                        turned.append(draw_turned(run, offset, centre, block, font, page))
                        continue
                    for position, character in enumerate(run.text):
                        advance = font.glyph_advance(ord(character)) * block.size_pt
                        upright_text.append(
                            pymupdf.Point(
                                centre - advance / 2,
                                offset + position * block.size_pt + block.ascent * block.size_pt,
                            ),
                            character,
                            font=font,
                            fontsize=block.size_pt,
                        )
        upright_text.write_text(page)
        for writer, pivot in turned:
            writer.write_text(page, morph=(pivot, pymupdf.Matrix(-90)))
        document.set_metadata(metadata)
        if subsettable:
            # The buffer is already cut to the spine's characters; this trims
            # whatever the layout tables dragged along with them.
            document.subset_fonts()
        document.save(target, garbage=4, deflate=True)
    logging.info("Wrote %s", target)


def draw_across(
    block: Block, width_pt: float, font: pymupdf.Font, writer: pymupdf.TextWriter
) -> None:
    """Set the one horizontal block, its lines centred across the spine."""
    # Half the leading above the line and half below, the way a line box is built.
    leading = block.pitch_pt - block.size_pt * block.extent
    top = block.top_pt + (block.height_pt - len(block.lines) * block.pitch_pt) / 2
    for index, line in enumerate(block.lines):
        baseline = top + index * block.pitch_pt + leading / 2 + font.ascender * block.size_pt
        length = font.text_length(line.text, fontsize=block.size_pt)
        writer.append(
            pymupdf.Point((width_pt - length) / 2, baseline),
            line.text,
            font=font,
            fontsize=block.size_pt,
        )


def draw_turned(
    run: Run,
    offset: float,
    centre: float,
    block: Block,
    font: pymupdf.Font,
    page: pymupdf.Page,
) -> tuple[pymupdf.TextWriter, pymupdf.Point]:
    """Queue one Latin run, laid out horizontally for a quarter turn clockwise.

    Rotating about the pivot carries the run down its column, so it is written
    left to right from there and the rotation does the rest. A quarter turn
    clockwise puts what was above the baseline to the right of it, so the
    baseline sits left of the column's centre line by as much as the face
    leaves above it, less half an em.
    """
    pivot = pymupdf.Point(centre - block.size_pt * (font.ascender - 0.5), offset)
    writer = pymupdf.TextWriter(page.rect)
    writer.append(pivot, run.text, font=font, fontsize=block.size_pt)
    return writer, pivot


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


def millimetres(value_pt: float) -> str:
    """Widths in the unit a bindery quotes, so no rounding creeps in.

    A spine given in whole millimetres survives as one; expressed in points it
    comes back a hundredth of a millimetre short.
    """
    return f"{value_pt * MM_PER_IN / PT_PER_IN:.4f}mm"


# The first four bytes of an sfnt say which outlines it carries: OTTO for the
# CFF ones, a version number for the TrueType ones. The ODT has to say which
# it is in three places, and a reader may refuse a face that does not match
# the label -- falling back, silently, to something else on the machine.
SFNT_CFF = b"OTTO"


def sfnt_flavour(face: bytes) -> tuple[str, str, str]:
    """The file extension, ODF format hint and media type a face should carry."""
    if face[:4] == SFNT_CFF:
        return ".otf", "opentype", "application/x-font-otf"
    return ".ttf", "truetype", "application/x-font-ttf"


def font_declaration(family: str, embedded: str | None, flavour: str = "truetype") -> str:
    """Declare the face, pointing at the copy inside the ODT when there is one.

    Both content.xml and styles.xml carry this; a reader consults whichever it
    reaches first. Without an embedded copy the declaration is just a name,
    and the reader's own machine supplies the face.
    """
    source = (
        f"<svg:font-face-src><svg:font-face-uri xlink:href={quoteattr(embedded)} "
        'xlink:type="simple" loext:font-style="normal" loext:font-weight="normal">'
        f"<svg:font-face-format svg:string={quoteattr(flavour)}/>"
        "</svg:font-face-uri></svg:font-face-src>"
        if embedded
        else ""
    )
    return (
        f"<office:font-face-decls><style:font-face style:name={quoteattr(family)} "
        f"""svg:font-family={quoteattr(f"'{family}'")} """
        'style:font-family-generic="system" style:font-pitch="variable">'
        f"{source}</style:font-face></office:font-face-decls>"
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


def automatic_styles(spine: Spine, family: str) -> str:
    """Every style content.xml needs: the table, its rows and cells, the text."""
    width_pt = spine.width_pt
    pieces = [
        '<style:style style:name="Spine" style:family="table">'
        f'<style:table-properties style:width={quoteattr(millimetres(width_pt))} '
        'table:align="center" fo:margin-top="0pt" fo:margin-bottom="0pt" '
        'style:writing-mode="page"/></style:style>',
        '<style:style style:name="SpineColumn" style:family="table-column">'
        f'<style:table-column-properties style:column-width={quoteattr(millimetres(width_pt))}/>'
        "</style:style>",
        '<style:style style:name="Plain" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none"/></style:style>',
        '<style:style style:name="Upright" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none" '
        'style:vertical-align="middle"/></style:style>',
        # no-wrap matters: the layout gives each line a column of its own, and
        # a reader whose metrics make a line a hair too long would otherwise
        # break it into a second one and lay the whole block out differently.
        '<style:style style:name="Sideways" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none" '
        'style:vertical-align="middle" style:writing-mode="tb-rl" '
        'fo:wrap-option="no-wrap"/></style:style>',
        '<style:style style:name="Blank" style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt"/>'
        "</style:style>",
    ]
    for index, (height_pt, _) in enumerate(spine.rows):
        pieces.append(
            f'<style:style style:name="Row{index}" style:family="table-row">'
            f"<style:table-row-properties style:row-height={quoteattr(pt(height_pt))} "
            'fo:keep-together="auto"/></style:style>'
        )
    for block in spine.blocks:
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


def table_rows(spine: Spine) -> str:
    rows = []
    for index, (_, block) in enumerate(spine.rows):
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
                for line in block.texts
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


def content_xml(spine: Spine, family: str, font_path: str | None, flavour: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-content {ODF_NAMESPACES} office:version="1.3">'
        f"{font_declaration(family, font_path, flavour)}"
        f"{automatic_styles(spine, family)}"
        "<office:body><office:text>"
        '<table:table table:name="Spine" table:style-name="Spine">'
        '<table:table-column table:style-name="SpineColumn"/>'
        f"{table_rows(spine)}"
        "</table:table>"
        "</office:text></office:body></office:document-content>"
    )


def styles_xml(width_pt: float, family: str, font_path: str | None, flavour: str) -> str:
    """The page itself: as tall as the thesis, as wide as the spine, no margins."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<office:document-styles {ODF_NAMESPACES} office:version="1.3">'
        f"{font_declaration(family, font_path, flavour)}"
        "<office:styles>"
        '<style:style style:name="Standard" style:family="paragraph" style:class="text">'
        '<style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt" '
        'fo:text-align="start" style:writing-mode="lr-tb"/></style:style>'
        "</office:styles>"
        "<office:automatic-styles>"
        '<style:page-layout style:name="Spine">'
        f"<style:page-layout-properties fo:page-width={quoteattr(millimetres(width_pt))} "
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
    """What the document says about itself, and what the PDF inherits.

    The exported PDF takes its author from meta:initial-creator and its
    keywords from meta:keyword, one element each; dc:description is the
    document's comments and goes nowhere near them.
    """
    keywords = "".join(
        f"<meta:keyword>{escape(keyword)}</meta:keyword>"
        for keyword in metadata["keywords"].split("; ")
        if keyword
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" office:version="1.3"><office:meta>'
        f"<dc:title>{escape(metadata['title'])}</dc:title>"
        f"<dc:subject>{escape(metadata['subject'])}</dc:subject>"
        f"<meta:initial-creator>{escape(metadata['author'])}</meta:initial-creator>"
        f"<dc:creator>{escape(metadata['author'])}</dc:creator>"
        f"{keywords}"
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


def manifest_xml(font_path: str | None, media_type: str = "application/x-font-ttf") -> str:
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
        + (
            f"<manifest:file-entry manifest:full-path={quoteattr(font_path)} "
            f"manifest:media-type={quoteattr(media_type)}/>"
            if font_path
            else ""
        )
        + "</manifest:manifest>"
    )


def write_odt(
    spine: Spine,
    family: str,
    font_bytes: bytes | None,
    metadata: dict[str, str],
    target: Path,
) -> None:
    """Write the ODT, carrying the face when its rights allow and naming it when not."""
    extension, flavour, media_type = sfnt_flavour(font_bytes or b"")
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", family)
    font_path = f"Fonts/{stem}{extension}" if font_bytes else None
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        # The mimetype has to come first and unstored, so that a reader can
        # identify the file from its first bytes without inflating anything.
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("META-INF/manifest.xml", manifest_xml(font_path, media_type))
        archive.writestr("content.xml", content_xml(spine, family, font_path, flavour))
        archive.writestr("styles.xml", styles_xml(spine.width_pt, family, font_path, flavour))
        archive.writestr("meta.xml", meta_xml(metadata))
        archive.writestr("settings.xml", settings_xml())
        if font_path:
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
        "keywords": f"{binding.name_zh}; 書背寬 {thickness.width_mm:g} mm",
        "producer": "scripts/make_spine.py",
    }


def describe(binding: Binding, thickness: Thickness, spine: Spine, written: list[Path]) -> None:
    print(f"{binding.name_zh} ({binding.key}): {thickness.width_mm:g} mm wide")
    for block in spine.blocks:
        note = " (shrunk to fit)" if block.shrunk else ""
        print(f"  {block.name:<9} {block.size_pt:g} pt{note}  {' / '.join(block.texts)}")
    for path in written:
        print(f"  {path.name:<30} {path.stat().st_size:,} bytes")


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
        pages = document.page_count

    text = read_spine_text(PROJECT_ROOT)
    font_file = locate_font(class_options(PROJECT_ROOT / "main.tex"), PROJECT_ROOT)
    logging.info("The thesis sets Chinese in %s", font_file.path)
    absent = missing_characters(font_file, text.characters())
    if absent:
        raise CollectionError(f"{font_file.name} has no glyph for {absent!r}.")

    shipped = redistributed(font_file, PROJECT_ROOT)
    if not shipped:
        # Where the first character of a vertical line sits is the face's own
        # doing: one that declares no vertical metrics -- 標楷體 is one -- has
        # an office suite hang its column about an ascent higher than the row
        # the layout gives it, while the PDF here draws it in the row itself.
        logging.warning(
            "%s is not one of the faces this template ships. Both files are laid "
            "out alike, but an office suite sets some faces' vertical lines about "
            "an ascent higher than the PDF draws them, so take the PDF as the one "
            "to print.",
            font_file.name,
        )
    embedding = embeddable_font(font_file, text.characters(), shipped)
    family = font_names(font_file)[0]
    # The ODT keeps the face as it is, because an office suite picks the
    # vertical forms itself; the PDF carries a copy that has already picked
    # them, and both are measured with the same advances.
    drawn = drawn_face(embedding.face, vertical_forms(font_file, text.characters()))
    ruler = pymupdf.Font(fontbuffer=drawn)

    for binding in BINDINGS:
        if args.binding not in ("both", binding.key):
            continue
        thickness = measure(pages, binding, measured_mm=args.paperback_width)
        spine = lay_out(text, mm(thickness.width_mm), ruler)
        metadata = spine_metadata(text, binding, thickness)
        # Appended, not substituted: a thesis called thesis.final.pdf would
        # otherwise have Path.with_suffix take ".final-spine-paperback" for an
        # extension and write every file of both bindings over one another.
        stem = f"{source.stem}-spine-{binding.key}"
        odt, pdf = args.output_dir / f"{stem}.odt", args.output_dir / f"{stem}.pdf"
        write_odt(spine, family, embedding.face if embedding.editable else None, metadata, odt)
        write_pdf(spine, ruler, metadata, pdf, embedding.subsettable)
        describe(binding, thickness, spine, [odt, pdf])


def arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "input", nargs="?", type=Path, default=DEFAULT_INPUT,
        help="built thesis PDF, for its page count (default: main.pdf)",
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
        "--paperback-width", type=float, metavar="MM",
        help=(
            "the 平裝 copy's own measured thickness in mm, used instead of the "
            "computed one; 精裝 is always this plus its boards, so measure the "
            "paperback even when writing the hardcover"
        ),
    )
    return parser


def main() -> int:
    args = arguments().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # fontTools narrates every table it touches; only its complaints matter here.
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    if args.paperback_width is not None and args.paperback_width <= 0:
        # A hardcover adds its boards to whatever this says, so a negative
        # measurement would come out the other side looking like a real width.
        logging.error("--paperback-width must be positive.")
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
