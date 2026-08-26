#!/usr/bin/env python3
"""Write the spine of the bound thesis (書側) as ODT and PDF, in both bindings.

A bindery needs the artwork at the finished book's thickness, which follows
from the page count of `main.pdf`. Four files come out, two per binding: the
ODT a print shop can edit, and the PDF to print. Both are laid out from one
table of measurements taken off NTU's official form and set every character
on the glyph HarfBuzz chooses for a vertical line, so the two agree. What the
spine says comes from main.tex and ntusetup.tex; the built PDF is opened only
to be counted.
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
import regex
import uharfbuzz as hb
import unicodedataplus
from fontTools import subset
from fontTools.ttLib import TTFont


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()

MM_PER_IN = 25.4
PT_PER_IN = 72.0
PAGE_HEIGHT_PT = 297.0 * PT_PER_IN / MM_PER_IN  # the A4 height of the thesis


def inch(value: float) -> float:
    return value * PT_PER_IN


def mm(value: float) -> float:
    return value * PT_PER_IN / MM_PER_IN


# --- How thick the finished book is ----------------------------------------
#
# 內頁紙材：80 磅道林紙約 10 條，即 0.1 mm。
# 80 磅道林紙, the usual text stock, is about 10 條 -- hundredths of a mm.
PAPER_THICKNESS_MM = 0.10

# 平裝（膠裝）的封面與書背膠層，約 1 mm。
# Perfect binding adds about a millimetre for the cover and the glue.
PAPERBACK_BINDING_MM = 1.00

# 精裝的紙板，兩面各 2 mm，正是官方 8 mm 平裝與 12 mm 精裝的差距。
# 2 mm of board a side: the gap between NTU's own 8 mm and 12 mm samples.
BOARD_THICKNESS_MM = 4.00

# 少於 80 頁預設單面列印，80 面以上預設雙面列印。
# Every page of the built PDF is an interior page: `pixi run cover` reproduces
# page one for the card cover rather than replacing it.
DUPLEX_THRESHOLD_PAGES = 80


# 兩種裝訂：檔名、書側上的名稱、紙板厚度。
BINDINGS = (("paperback", "平裝", 0.0), ("hardcover", "精裝", BOARD_THICKNESS_MM))


# --- The layout of the official form ---------------------------------------
#
# Row heights in inches, measured off NTU's form: named rows carry text,
# unnamed ones are the spacing between them. The form places its two heading
# columns in drawing frames instead of the table; those are written out here
# as three rows (0.3942 + 0.9450 + 0.3143 = its 1.6535 in row) so that one
# table drives the page.
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

# The form sets the two heading columns 1.01 em apart, near enough to solid.
# Pinning it also keeps a face with a taller natural line height from pushing
# the second column off a narrow spine.
HEADING_COLUMN_PITCH = 1.01

# The date is the one horizontal block on the spine; the form leads it at
# 15 pt on a 14 pt body.
DATE_LINE_PITCH = 15.0 / 14.0

# One character's worth of room at the foot of every vertical line: a reader
# whose metrics make a line a hair longer would otherwise break it into a
# second column. LibreOffice ignores fo:wrap-option on a Writer cell, so the
# room has to be left rather than the wrap forbidden.
LINE_SLACK_EM = 1.0

# 封面第一行的頂端與最後一行的底端，寫死，因為類別也是寫死的。
# \makecover sets a fixed A4 page inside a 3 cm margin and spreads it with
# \vfill, so the cover's first and last lines fall here in every thesis.
# Changing \ntu@geometry@cover or the cover's 18/27 pt body changes these.
COVER_TOP_PT = 83.9
COVER_BOTTOM_PT = 748.2
COVER_TEXT_HEIGHT_PT = COVER_BOTTOM_PT - COVER_TOP_PT

# How close to the fold a character may set. NTU's 8 mm sample leaves about
# 0.3 mm beside its widest line, so a shade under that keeps the sample width
# setting at the form's own sizes.
SIDE_CLEARANCE_MM = 0.25


# --- What the spine says ---------------------------------------------------
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


# A variation selector, a joiner and the rest of the invisible characters that
# only qualify the character before them. A spine has one slot per character
# and no face has to hold a glyph for these, so what the cover draws for them
# -- nothing -- is what the spine draws.
IGNORABLE = regex.compile(r"\p{Default_Ignorable_Code_Point}")


def value(setup: dict[str, str], key: str) -> str:
    """One \ntusetup value, as the class would set it: 讀到什麼是什麼."""
    return IGNORABLE.sub("", collapse_spaces(setup.get(key, "")))


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
    """Collect what the spine letters, in the thesis's own words."""
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
    """The family, full and PostScript names a face answers to."""
    try:
        with font.open(lazy=True) as opened:
            table = opened["name"]
            return tuple(name for name in (table.getDebugName(i) for i in (1, 4, 6)) if name)
    except Exception:  # noqa: BLE001 - fontTools raises a different type per defect
        logging.debug("Not a readable font: %s", font.name)
        return ()


def matched_font(family: str) -> FontFile | None:
    """The file fontconfig answers a request for `family` with.

    `fc-match`, not `fc-list`: the build asks fontconfig to match a family and
    is given one face, while a listing is in no particular order and holds
    every style the family has. Fontconfig always answers something, so the
    caller still has to ask the file whether it is the face wanted.
    """
    try:
        matched = subprocess.run(
            ["fc-match", "--format=%{file}\t%{index}\n", f"{family}:style=Regular"],
            capture_output=True,
            text=True,
        )
    except OSError:
        logging.debug("No fc-match on this machine, so only the shipped faces are known.")
        return None
    path, _, index = matched.stdout.strip().partition("\t")
    if matched.returncode != 0 or not path:
        return None
    return FontFile(Path(path), int(index) if index.isdigit() else 0)


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
    """The file the class sets Chinese in, found the way the class finds it."""
    fontset = options.get("fontset", "default")
    if fontset in CJK_FAMILIES:
        family = CJK_FAMILIES[fontset]
        candidate = matched_font(family)
        if candidate and any(same_font(family, found) for found in font_names(candidate)):
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


# The faces this template redistributes. Their licences (政府資料開放授權條款-1.0,
# OFL-1.1) permit a modified version, so a subset of these -- and of nothing
# else -- may have its embedding rights relaxed to travel inside the ODT.
SHIPPED_FILES = ("fonts/chinese/TW-Kai-98_1.ttf", "fonts/chinese/TW-Sung-98_1.ttf")


def redistributed(font: FontFile, root: Path) -> bool:
    """Whether a file is one of the two faces this repository ships."""
    return any(
        font.path.resolve() == (root / relative).resolve() for relative in SHIPPED_FILES
    )


# OS/2 fsType. The permission is the low four bits and is a level, not a flag
# set -- zero is installable, the most permissive. The bits above are separate
# restrictions and say nothing about that level.
FSTYPE_LEVEL = 0x000F
FSTYPE_RESTRICTED = 0x0002  # embedding forbidden without the vendor's leave
FSTYPE_EDITABLE = 0x0008  # embedding allowed in a document that can be edited
FSTYPE_NO_SUBSETTING = 0x0100  # embed the whole face or none of it
FSTYPE_BITMAP_ONLY = 0x0200  # only the bitmaps inside it, never the outlines


def embeddable_font(font: FontFile, characters: str, relabel: bool) -> tuple[bytes, bool, bool]:
    """Cut the face down to the glyphs the spine prints, and say where it may go."""
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
    # A subset is written with a post 3.0 table by default, which carries no
    # glyph names, and a reader then names each glyph after the character that
    # maps to it. The vertical forms are reached through `vert` and not through
    # the cmap, so that leaves them nameless and `drawn_face` cannot find the
    # one it was told to put in place.
    options.glyph_names = True
    # OS/2 says which scripts and code pages the face covers, and a subsetter
    # cuts those declarations down to what it kept. A spine's two dozen
    # characters leave a face that no longer claims Chinese, and a reader that
    # picks the face for a run by that claim -- rather than by asking the cmap
    # -- then letters the spine in whatever it falls back to.
    options.prune_unicode_ranges = False
    options.prune_codepage_ranges = False
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
    single_family(face, font_names(font)[0])
    written = io.BytesIO()
    face.save(written)
    face.close()
    # The face, whether it may travel inside a document that can be edited,
    # and whether it may be cut down further.
    return written.getvalue(), editable, not rights & FSTYPE_NO_SUBSETTING


def missing_characters(font: FontFile, characters: str) -> str:
    with font.open(lazy=True) as opened:
        table = opened.getBestCmap()
    return "".join(char for char in characters if ord(char) not in table)


# --- How wide the spine has to be ------------------------------------------


def spine_width_mm(pages: int, board_mm: float, measured_mm: float | None) -> float:
    """How wide the artwork is, in the whole millimetres a bindery works in."""
    if measured_mm is not None:
        return measured_mm + board_mm
    sheets = math.ceil(pages / 2) if pages >= DUPLEX_THRESHOLD_PAGES else pages
    # 無條件進位：書背略寬還裝得上，略窄就裝不上。
    # Rounded up: a spine a shade too wide still binds, one a shade too narrow
    # does not.
    return math.ceil(sheets * PAPER_THICKNESS_MM + PAPERBACK_BINDING_MM + board_mm - 1e-9)


# --- Placing the text ------------------------------------------------------
#
# Vertical CJK is not horizontal text turned on its side: a wide character
# keeps its shape in a slot one em deep, a Latin run turns a quarter turn and
# advances at its own width, and punctuation takes the shape `vert` gives it.


@dataclass(frozen=True)
class Run:
    """A stretch of one line that shares an orientation."""

    text: str
    turned: bool
    glyphs: tuple[Shaped, ...]

    @property
    def advance(self) -> float:
        """How far the pen moves over the run, in em, so a point size scales it."""
        return sum(glyph.advance for glyph in self.glyphs)


def split_runs(line: str, shaper: Shaper) -> tuple[Run, ...]:
    """Break a line into upright characters and turned Latin runs."""
    runs: list[Run] = []
    # By grapheme cluster: a mark belongs to the character it sits on, and the
    # two take one slot between them rather than one each.
    for cluster in regex.findall(r"\X", line):
        if shaper.upright(cluster):
            runs.append(Run(cluster, False, shaper.shape(cluster, True)))
        elif runs and runs[-1].turned:
            grown = runs[-1].text + cluster
            runs[-1] = Run(grown, True, shaper.shape(grown, False))
        else:
            runs.append(Run(cluster, True, shaper.shape(cluster, False)))
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
        """Every run of line `index` with the page offset of its slot's top."""
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
        """Where line `index` sits across the spine."""
        offset = (len(self.lines) - 1) / 2 - index
        return width_pt / 2 + offset * self.pitch_pt

    @property
    def ink_top_pt(self) -> float:
        """The top of the block's first line box, leading excluded."""
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
    """The form's point size, or the largest tenth of a point that still fits."""
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
    """Return the point size and line pitch that keep a block inside its row."""
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
    text: SpineText, width_pt: float, shaper: Shaper, ruler: pymupdf.Font, heights: list[float]
) -> Spine:
    """Fill the rows, each block sized to whatever room its own row leaves."""
    rows: list[tuple[float, Block | None]] = []
    top = 0.0
    for (name, _), height in zip(LAYOUT, heights):
        block = None
        if name:
            lines = tuple(Line(split_runs(line, shaper)) for line in text.block(name))
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
    """A block's own row height, and how far its ink starts below that row's top."""
    if block.vertical:
        deep = max(line.advance for line in block.lines) * block.size_pt
        room = deep + LINE_SLACK_EM * block.size_pt
        # A justified line starts at the top of its row; a centred one sits in
        # the middle of it, so half the slack is above the ink.
        return room, 0.0 if block.justified else (room - deep) / 2
    leading = block.pitch_pt - block.size_pt * block.extent
    return len(block.lines) * block.pitch_pt, leading / 2


def lay_out(text: SpineText, width_pt: float, shaper: Shaper, ruler: pymupdf.Font) -> Spine:
    """Lay the spine out, stretched to the same extent as the cover's text."""
    form = build_rows(text, width_pt, shaper, ruler, form_heights())
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
    return build_rows(text, width_pt, shaper, ruler, heights)


# --- The PDF ---------------------------------------------------------------


# Six characters LibreOffice reads as Tu when the text is Chinese, whatever
# UTR#50 has them as: the fullwidth colon and semicolon, which it makes Tr,
# and the four Bopomofo tone marks, which it makes R. The spine is Chinese,
# so this is how the ODT is laid out and the PDF has to letter it the same.
# https://github.com/LibreOffice/core/commit/cd6b70497180dbf0f3f78684e74702c993bbe449
# https://github.com/LibreOffice/core/commit/b087e451527f2e497ccab83b63b4f10099bfb8b8
CHINESE_UPRIGHT = "：；ˊˋˇ˙"


@dataclass(frozen=True)
class Shaped:
    """What HarfBuzz says about one glyph: which it is, and where it goes."""

    glyph: str
    advance: float  # em, along the line
    x_offset: float  # em, across it
    y_offset: float  # em, up from the pen


class Shaper:
    """HarfBuzz, asked how the face sets a line.

    The same shaper an office suite lays the ODT out with, so what it says
    about a glyph -- which form a vertical line takes, how far the pen moves,
    and where the glyph sits against that pen -- is what both files use.
    """

    def __init__(self, font: FontFile) -> None:
        face = hb.Face(hb.Blob.from_file_path(str(font.path)), font.index)
        self.upem = face.upem
        self.font = hb.Font(face)
        with font.open(lazy=True) as opened:
            self.names = opened.getGlyphOrder()

    def shape(self, text: str, down: bool) -> tuple[Shaped, ...]:
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        buffer.direction = "ttb" if down else "ltr"
        hb.shape(self.font, buffer)
        return tuple(
            Shaped(
                self.names[info.codepoint],
                (-place.y_advance if down else place.x_advance) / self.upem,
                place.x_offset / self.upem,
                place.y_offset / self.upem,
            )
            for info, place in zip(buffer.glyph_infos, buffer.glyph_positions)
        )

    def substitutes(self, text: str) -> bool:
        """Whether a vertical line draws `text` with a glyph of its own."""
        down = [glyph.glyph for glyph in self.shape(text, True)]
        return down != [glyph.glyph for glyph in self.shape(text, False)]

    def upright(self, cluster: str) -> bool:
        """Whether a vertical line stands this cluster up or turns it.

        UTR#50: U and Tu stand and R turns, whatever the face holds. Tr is
        "transformed, falling back to rotated" -- 「 and （ are Tr -- so it
        stands only where the face has a vertical form to stand it in, and
        turns where it has none. TW-Kai has one for the brackets.
        """
        if cluster[0] in CHINESE_UPRIGHT:
            return True
        orientation = unicodedataplus.vertical_orientation(cluster[0])
        if orientation in ("U", "Tu"):
            return True
        return orientation == "Tr" and self.substitutes(cluster)

    def vertical_forms(self, characters: str) -> dict[str, str]:
        """Each upright character that a vertical line draws with another glyph.

        Only what stands upright is asked about: a turned run is drawn from
        the horizontal form and rotated, so a vertical form folded into one of
        those would be turned twice.
        """
        forms = {}
        for character in characters:
            if not self.upright(character):
                continue
            down = self.shape(character, True)
            if len(down) == 1 and self.substitutes(character):
                forms[character] = down[0].glyph
        return forms


def single_family(face: TTFont, family: str) -> None:
    """Leave the face answering to one family name, whatever the locale.

    A face may name its family once per language -- TW-Sung calls itself
    `TW-Sung` in English and 全字庫正宋體 in Chinese -- and a platform reports
    the name for its own locale: Windows in Taiwan registers the embedded copy
    as 全字庫正宋體, while the ODT asks for `TW-Sung`, finds nothing, and
    letters the spine in whatever it falls back to. Naming both in
    `svg:font-family` does not help, since an office suite reads that as one
    name and not as a list. So the copy that travels inside the document keeps
    the one name the document asks for.
    """
    table = face["name"]
    kept = []
    for record in table.names:
        if record.nameID not in (1, 4, 16):
            kept.append(record)
            continue
        try:
            named = record.toUnicode()
        except UnicodeDecodeError:
            continue
        if named == family:
            kept.append(record)
    table.names = kept


def drawn_face(font_bytes: bytes, forms: dict[str, str]) -> bytes:
    """The copy of the face the PDF draws from, with two corrections."""
    face = TTFont(io.BytesIO(font_bytes))
    absent = sorted(set(forms.values()) - set(face.getGlyphOrder()))
    if absent:
        # Better to stop than to letter the horizontal form in a vertical line,
        # which is a difference only a reader of the finished sheet would catch.
        raise CollectionError(
            f"The vertical forms {', '.join(absent)} are not in the face the PDF "
            "draws from, though the face shapes with them."
        )
    turned = 0
    for table in face["cmap"].tables:
        for code, name in list(table.cmap.items()):
            wanted = forms.get(chr(code))
            if wanted and name != wanted:
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
    """Draw the spine, run by run, where the layout puts it."""
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
                    # Where HarfBuzz puts the glyph against the pen: across
                    # the column by x_offset, and up from it by y_offset,
                    # which on a page whose y grows downward is a descent.
                    glyph = run.glyphs[0]
                    upright_text.append(
                        pymupdf.Point(
                            centre + glyph.x_offset * block.size_pt,
                            offset - glyph.y_offset * block.size_pt,
                        ),
                        run.text,
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
    """Queue one Latin run, laid out horizontally for a quarter turn clockwise."""
    pivot = pymupdf.Point(centre - block.size_pt * (font.ascender + font.descender) / 2, offset)
    writer = pymupdf.TextWriter(page.rect)
    if len(run.glyphs) != len(run.text):
        # A ligature or a mark left the shaper with its own count of glyphs,
        # and the pen positions no longer line up with the characters; the
        # writer lays the run out itself rather than being placed wrongly.
        writer.append(pivot, run.text, font=font, fontsize=block.size_pt)
        return writer, pivot
    pen = 0.0
    for glyph, character in zip(run.glyphs, run.text):
        writer.append(
            pymupdf.Point(
                pivot.x + (pen + glyph.x_offset) * block.size_pt,
                pivot.y - glyph.y_offset * block.size_pt,
            ),
            character,
            font=font,
            fontsize=block.size_pt,
        )
        pen += glyph.advance
    return writer, pivot


# --- The ODT ---------------------------------------------------------------

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
    """Widths in the unit a bindery quotes, so no rounding creeps in."""
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


def css_family(family: str) -> str:
    """A family name as a CSS font-family value."""
    if not regex.search(r"""[\s,'"]""", family):
        return family
    quote = '"' if "'" in family else "'"
    return f"{quote}{family}{quote}"


def font_declaration(family: str, embedded: str | None, flavour: str = "truetype") -> str:
    """Declare the face, pointing at the copy inside the ODT when there is one."""
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
        # Quoted only where a family name has to be, as an office suite quotes
        # it in its own files: `'DejaVu Sans'` but `TW-Kai`.
        f"svg:font-family={quoteattr(css_family(family))} "
        'style:font-family-generic="system" style:font-pitch="variable">'
        f"{source}</style:font-face></office:font-face-decls>"
    )


def text_properties(family: str, size_pt: float) -> str:
    """Set one size in one family, for Western, Asian and complex scripts alike."""
    name, size = quoteattr(family), quoteattr(pt(size_pt))
    return (
        # The Asian language is what decides CHINESE_UPRIGHT, and an office
        # suite that is not told falls back to whatever its own default is --
        # a Japanese one turns the tone marks the spine stands up.
        '<style:text-properties style:language-asian="zh" style:country-asian="TW" '
        f"style:font-name={name} fo:font-family={name} "
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
    """What the document says about itself, and what the PDF inherits."""
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


# --- Driving the two bindings ----------------------------------------------


def spine_metadata(text: SpineText, name_zh: str, width_mm: float) -> dict[str, str]:
    return {
        "title": f"{text.university}{text.degree}書側" + (f"（{name_zh}）" if name_zh else ""),
        "author": text.author,
        "subject": f"{text.university}{text.institute}{text.degree}書側",
        "keywords": (f"{name_zh}; " if name_zh else "") + f"書背寬 {width_mm:g} mm",
        "producer": "scripts/make_spine.py",
    }


def describe(label: str, width_mm: float, spine: Spine, written: list[Path]) -> None:
    print(f"{label}: {width_mm:g} mm wide")
    for block in spine.blocks:
        note = " (shrunk to fit)" if block.shrunk else ""
        print(f"  {block.name:<9} {block.size_pt:g} pt{note}  {' / '.join(block.texts)}")
    for path in written:
        print(f"  {path.name:<30} {path.stat().st_size:,} bytes")


def build(args: argparse.Namespace) -> None:
    source = PROJECT_ROOT / "main.pdf"
    if not source.is_file():
        raise CollectionError(f"No such PDF: {source}. Run `pixi run build` first.")
    with pymupdf.open(source) as document:
        if document.needs_pass:
            raise CollectionError(
                f"{source.name} cannot be opened without a password. Write the spine "
                "from the PDF that `pixi run build` produced."
            )
        pages = document.page_count

    font_file = locate_font(class_options(PROJECT_ROOT / "main.tex"), PROJECT_ROOT)
    logging.info("The thesis sets Chinese in %s", font_file.path)
    text = read_spine_text(PROJECT_ROOT)
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
    face, editable, subsettable = embeddable_font(font_file, text.characters(), shipped)
    family = font_names(font_file)[0]
    # The ODT keeps the face as it is, because an office suite picks the
    # vertical forms itself; the PDF carries a copy that has already picked
    # them, and both are measured with the same advances.
    shaper = Shaper(font_file)
    drawn = drawn_face(face, shaper.vertical_forms(text.characters()))
    ruler = pymupdf.Font(fontbuffer=drawn)

    # 沒有指定寬度就平裝、精裝各出一份；指定了就只出那一份。
    # Both bindings unless a width is given, and only that one when it is.
    wanted = (
        [("", "", args.width)]
        if args.width
        else [(key, name, spine_width_mm(pages, board, None)) for key, name, board in BINDINGS]
    )
    for key, name_zh, width_mm in wanted:
        spine = lay_out(text, mm(width_mm), shaper, ruler)
        metadata = spine_metadata(text, name_zh, width_mm)
        stem = f"{source.stem}-spine-{key}" if key else f"{source.stem}-spine"
        odt, pdf = args.output_dir / f"{stem}.odt", args.output_dir / f"{stem}.pdf"
        write_odt(spine, family, face if editable else None, metadata, odt)
        write_pdf(spine, ruler, metadata, pdf, subsettable)
        describe(f"{name_zh} ({key})" if key else "書側 (the width you gave)", width_mm, spine, [odt, pdf])


def arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o", "--output-dir", type=Path, default=PROJECT_ROOT,
        help="where to write the four files (default: the project root)",
    )
    parser.add_argument(
        "--width", type=float, metavar="MM",
        help=(
            "the finished spine's own thickness in mm, measured off a bound "
            "copy; one artwork is written at exactly that width instead of the "
            "two the page count computes"
        ),
    )
    return parser


def main() -> int:
    args = arguments().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # fontTools narrates every table it touches; only its complaints matter here.
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    if args.width is not None and not (math.isfinite(args.width) and args.width > 0):
        logging.error("--width must be a positive number of millimetres.")
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
