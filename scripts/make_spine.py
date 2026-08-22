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
import unicodedata
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

# 民國紀年：西元年減 1911。
# The ROC calendar counts from 1912, so its year is the Gregorian one less this.
ROC_EPOCH = 1911

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
    braced_group,
    collapse_spaces,
    parse_ntusetup,
    strip_comments,
)


# The commands the shared parser keeps, by unwrapping them or by turning them
# into the character they stand for. Every other control sequence it deletes,
# so a title of `\LaTeX{} Thesis` would reach the spine as `Thesis` while the
# cover still reads otherwise -- silently, and at either end of the value,
# where comparing against the cover's own text cannot catch it.
UNDERSTOOD_COMMANDS = frozenset(
    "begin end texorpdfstring textbf textit emph mbox textrm textsf texttt "
    "mathrm mathbf mathit operatorname url".split()
)
COMMAND = re.compile(r"\\([A-Za-z@]+)\*?|\\([^A-Za-z@])")
ESCAPED = frozenset("&%#_${}")


def dropped_commands(latex: str) -> list[str]:
    """The control sequences in a value that the parser would throw away."""
    lost = []
    for word, symbol in COMMAND.findall(latex):
        if word and word not in UNDERSTOOD_COMMANDS:
            lost.append("\\" + word)
        elif symbol and symbol not in ESCAPED and symbol not in "(),[]":
            lost.append("\\" + symbol)
    return lost


def raw_ntusetup(path: Path) -> dict[str, str]:
    """The \\ntusetup values as written, before the parser plains them out."""
    text = strip_comments(path.read_text(encoding="utf-8"))
    marker = re.search(r"\\ntusetup\s*\{", text)
    if not marker:
        return {}
    block, _ = braced_group(text, marker.end() - 1)
    values, cursor = {}, 0
    pattern = re.compile(r"([A-Za-z][\w*-]*)\s*=\s*\{")
    while match := pattern.search(block, cursor):
        value, cursor = braced_group(block, match.end() - 1)
        values[match.group(1)] = value
    return values


DEGREE_NAMES = {"master": "碩士論文", "doctor": "博士論文"}


def parse_degree(path: Path) -> str:
    """Read the ntuthesis `degree` option, which names the kind of thesis.

    `degree = {doctor}` is as valid as `degree = doctor`, so both spellings
    have to be read. Only a genuinely absent option falls back to the class
    default; a value that is present but unrecognised stops the run rather
    than lettering a doctoral spine 碩士論文.
    """
    text = strip_comments(path.read_text(encoding="utf-8"))
    # The option list is itself optional: \documentclass{ntuthesis} is valid
    # and takes every class default, this one included.
    declared = re.search(r"\\documentclass\s*(?:\[(.*?)\])?\s*\{ntuthesis\}", text, re.DOTALL)
    if not declared:
        raise CollectionError(f"Could not find \\documentclass{{ntuthesis}} in {path}")
    degree = re.search(r"\bdegree\s*=\s*\{?\s*([A-Za-z]+)\s*\}?", declared.group(1) or "")
    if degree is None:
        return DEGREE_NAMES["master"]
    if degree.group(1) not in DEGREE_NAMES:
        raise CollectionError(
            f"{path.name} sets degree = {degree.group(1)}; expected master or doctor."
        )
    return DEGREE_NAMES[degree.group(1)]


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

    def vertical_characters(self) -> str:
        """Everything set down a column; the date alone runs across."""
        joined = "".join(
            "".join(self.block(name)) for name in NOMINAL_SIZE_PT if name != "date"
        )
        return "".join(sorted(set(joined)))


def read_thesis_text(root: Path, cover_date: tuple[int, int] | None) -> SpineText:
    """Collect what the spine letters, in the words the cover already uses.

    TeX collapses a run of spaces and newlines into one space, so a value
    wrapped across lines inside its braces reaches the class as a single line.
    Collapsing it here too keeps a newline out of the spine, where it would be
    counted as a character and looked up in the font as a glyph.
    """
    setup = {key: collapse_spaces(value) for key, value in parse_ntusetup(root / "ntusetup.tex").items()}
    missing = [key for key in ("university", "institute", "title", "author") if not setup.get(key)]
    if missing:
        raise CollectionError(
            f"ntusetup.tex has no {', '.join(missing)}; the spine cannot be lettered without it."
        )
    if cover_date is not None:
        # The cover is what gets bound; the spine has to agree with it, and
        # `date` is commented out in the template, so a later run of this
        # script would otherwise date the spine to the day it was run.
        roc_year, month = cover_date
    elif setup.get("date"):
        try:
            written = date.fromisoformat(setup["date"])
        except ValueError as error:
            raise CollectionError(
                f"ntusetup.tex has date = {{{setup['date']}}}, which is not a YYYY-MM-DD date."
            ) from error
        roc_year, month = written.year - ROC_EPOCH, written.month
    else:
        today = date.today()
        roc_year, month = today.year - ROC_EPOCH, today.month
    return SpineText(
        university=setup["university"],
        institute=setup["institute"],
        degree=parse_degree(root / "main.tex"),
        title=setup["title"],
        author=setup["author"],
        roc_year=roc_year,
        month=month,
    )


# --------------------------------------------------------------------------
# Reading the cover
# --------------------------------------------------------------------------
#
# Page one of the built PDF is the cover, and it is the page the spine has to
# agree with: it prints the same words, in the same face, on the board the
# spine folds away from.

# 封面日期行：中華民國 115 年 8 月。
COVER_DATE = re.compile(r"中華民國\s*(\d+)\s*年\s*(\d+)\s*月")

# The class stamps a linked doi: line a centimetre from the foot of every
# page, page one included. It is an overlay, not part of the cover's text
# block, and measuring to it would stretch the spine past the cover's last
# line -- so anything inside a link on the cover is left out.
COVER_OVERLAY = re.compile(r"^\s*doi:")

# Anything at or above this code point is CJK rather than Latin, which is
# enough to tell the cover's two faces apart.
CJK_FIRST = 0x2E80


@dataclass(frozen=True)
class Cover:
    """What the built thesis's cover tells the spine."""

    font: str
    width_pt: float
    height_pt: float
    top_pt: float
    bottom_pt: float
    date: tuple[int, int] | None
    text: str

    @property
    def text_height_pt(self) -> float:
        return self.bottom_pt - self.top_pt

    def prints(self, wording: str) -> bool:
        """Whether the cover carries this wording, spacing and breaks aside."""
        return re.sub(r"\s", "", wording) in re.sub(r"\s", "", self.text)


def read_cover(document: pymupdf.Document) -> Cover:
    """Measure the cover: its Chinese face, its date, and where its text sits.

    The extremes are the top of the first line and the bottom of the last, in
    line boxes rather than ink, so that they mean the same thing on a line of
    CJK as on a line of Latin.
    """
    page = document[0]
    overlays = [pymupdf.Rect(link["from"]) for link in page.get_links()]
    font, top, bottom, printed = "", None, None, ""
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = "".join(char["c"] for char in span["chars"])
                if COVER_OVERLAY.match(text):
                    continue
                for char in span["chars"]:
                    if char["c"].isspace():
                        continue
                    box = pymupdf.Rect(char["bbox"])
                    if any(box in overlay for overlay in overlays):
                        continue
                    top = box.y0 if top is None else min(top, box.y0)
                    bottom = box.y1 if bottom is None else max(bottom, box.y1)
                    printed += char["c"]
                    if not font and ord(char["c"]) >= CJK_FIRST:
                        font = re.sub(r"^[A-Z]{6}\+", "", span["font"])
    if not font:
        raise CollectionError(
            "Page 1 of the built PDF prints no Chinese, so its Chinese font cannot "
            "be identified. Build the cover before writing the spine."
        )
    dated = COVER_DATE.search(page.get_text())
    return Cover(
        font=font,
        width_pt=page.rect.width,
        height_pt=page.rect.height,
        top_pt=top,
        bottom_pt=bottom,
        date=(int(dated.group(1)), int(dated.group(2))) if dated else None,
        text=printed,
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

    @property
    def shipped(self) -> bool:
        return any(same_font(face, name) for face in SHIPPED_FACES for name in font_names(self))

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
    """Every face fontconfig knows about, collections expanded."""
    listed = subprocess.run(
        ["fc-list", "--format=%{file}\t%{index}\n"],
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        return []
    found = []
    for row in listed.stdout.splitlines():
        path, _, index = row.partition("\t")
        if path:
            found.append(FontFile(Path(path), int(index) if index.isdigit() else 0))
    return found


def locate_font(name: str, root: Path) -> FontFile:
    """Find the face behind a PDF font name: shipped with the template, or installed.

    The built PDF names the face it used, and that name is a PostScript one --
    標楷體 comes through as DFKaiShu-SB-Estd-BF -- so the search has to match
    on more than the family. fontconfig is asked for what it has rather than
    asked to match: it answers a request for a face it does not have with a
    metric-compatible stand-in, so every candidate is opened and made to say
    for itself that it is the font the thesis was built with. A .ttc is
    several faces in one file, and only one of them is the answer.
    """
    for path in sorted(root.glob("fonts/**/*")):
        if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
            continue
        for index in range(collection_size(path)):
            candidate = FontFile(path, index)
            if any(same_font(name, found) for found in font_names(candidate)):
                return candidate
    for candidate in installed_fonts():
        if any(same_font(name, found) for found in font_names(candidate)):
            return candidate
    raise CollectionError(
        f"The built PDF sets Chinese in {name}, but no file for it was found in "
        f"{root / 'fonts'} or among the fonts installed on this system. Install "
        "it, or build with a fontset whose Chinese face ships with the template."
    )


def collection_size(path: Path) -> int:
    if path.suffix.lower() != ".ttc":
        return 1
    try:
        from fontTools.ttLib import TTCollection

        with TTCollection(path, lazy=True) as collection:
            return len(collection.fonts)
    except Exception:  # noqa: BLE001 - an unreadable collection is simply not a match
        return 1


# The Chinese faces this template redistributes. Two things are true of these
# and of no others: their licences (政府資料開放授權條款-1.0 or OFL-1.1) permit
# a modified version, so a subset of them may be written with its embedding
# rights relaxed; and the two outputs have been checked against them, with
# LibreOffice setting the ODT within a tenth of a millimetre of where the PDF
# draws it. Other faces are laid out the same way and print the same from the
# PDF, but LibreOffice sets some of them -- 標楷體 among them -- about one
# ascent higher on the page.
SHIPPED_FACES = ("TW-Kai-98_1", "TW-Sung-98_1")


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


def embeddable_font(font: FontFile, characters: str) -> Embedding:
    """Cut the face down to the glyphs the spine prints, and say where it may go.

    The shipped 全字庫 faces are tens of megabytes; a spine sets a few dozen
    characters. Every name record is kept so that the family name in the ODT
    still resolves to the embedded file.

    Whether the ODT may carry the subset is the second answer. A PDF is a
    printed page, which `fsType` level 4 allows; an ODT is a document that can
    be edited, which it does not, and an office suite honours only a face
    marked installable. The template's own faces may simply be marked so --
    their licences permit a modified version -- but a face belonging to the
    user may not be relabelled on their behalf, so the ODT names it and
    leaves the machine to supply it.
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
        # A spine is lettered at whatever size it takes, and both outputs carry
        # outlines; a face that allows only its bitmaps to travel cannot be one
        # of them, whatever else its rights permit.
        raise CollectionError(
            f"{font.name} allows only its bitmaps to be embedded, not its outlines, "
            "which is what the spine files carry. Build the thesis with a fontset "
            "whose Chinese face ships with the template."
        )

    options = subset.Options()
    # `vert` has to survive: LibreOffice reads it out of the ODT's copy, and
    # the PDF folds it into its own.
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
    if not editable and font.shipped:
        face["OS/2"].fsType = 0
        editable = True
    elif not editable:
        logging.warning(
            "%s allows embedding for print but not for editing, and is not one of "
            "the faces this template may relabel. The PDF carries it; the ODT "
            "names it instead, so open the ODT on a machine that has it installed.",
            font.name,
        )
    written = io.BytesIO()
    face.save(written)
    face.close()
    return Embedding(written.getvalue(), editable, not rights & FSTYPE_NO_SUBSETTING)


def vertical_substitutions(font: TTFont) -> dict[str, str]:
    """Each glyph that has a vertical form, mapped to it, per the font's `vert`.

    Vertical CJK does not merely turn the page: a bracket, a comma or a full
    stop is drawn differently down a column than across a line, and the shape
    to use lives in the font rather than at a code point of its own.
    """
    gsub = font.get("GSUB")
    if gsub is None:
        return {}
    lookups: set[int] = set()
    for record in gsub.table.FeatureList.FeatureRecord:
        if record.FeatureTag in ("vert", "vrt2"):
            lookups.update(record.Feature.LookupListIndex)
    mapping: dict[str, str] = {}
    for index in sorted(lookups):
        for table in gsub.table.LookupList.Lookup[index].SubTable:
            # A type 7 lookup only wraps the real one.
            table = getattr(table, "ExtSubTable", table)
            mapping.update(getattr(table, "mapping", {}))
    return mapping


def drawn_face(font_bytes: bytes, vertical: str) -> bytes:
    """The copy of the face the PDF draws from, with two corrections.

    The first is the vertical forms. LibreOffice applies `vert` itself when it
    sets the ODT, but a PDF carries glyphs already chosen, so folding the
    substitution into this copy's character map is what makes the drawn page
    agree with the editable one. The mapping back to Unicode is untouched, so
    the PDF still reads as what it says.

    The second is `post.isFixedPitch`. 標楷體 sets it, though its ideographs
    are a full em wide and its digits half of one, and a PDF writer that
    believes it emits a single width for every glyph -- which sets the year on
    the spine as three digits piled on top of each other. Clearing the flag
    costs a font that really is monospaced nothing: its widths are then simply
    written out, and they all still agree.
    """
    face = TTFont(io.BytesIO(font_bytes))
    mapping = vertical_substitutions(face)
    wanted = {ord(character) for character in vertical}
    turned = 0
    for table in face["cmap"].tables:
        for code, name in list(table.cmap.items()):
            if code in wanted and name in mapping:
                table.cmap[code] = mapping[name]
                turned += 1
    if turned:
        logging.info("Set %d character(s) in their vertical form.", turned)
    if face["post"].isFixedPitch:
        logging.info("%s claims to be monospaced; writing its real widths.", face["name"].getDebugName(1))
        face["post"].isFixedPitch = 0
    written = io.BytesIO()
    face.save(written)
    face.close()
    return written.getvalue()


def missing_characters(font: FontFile, characters: str) -> str:
    with font.open(lazy=True) as opened:
        table = opened.getBestCmap()
    return "".join(char for char in characters if ord(char) not in table)


# --------------------------------------------------------------------------
# How wide the spine has to be
# --------------------------------------------------------------------------


# 封面另以卡紙印製，不算內頁。
# Page one is the cover, printed on the card the binding allowance already
# pays for, so it is not one of the text sheets stacked in the spine.
COVER_PAGES = 1


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
    interior = max(pages - COVER_PAGES, 0)
    return Thickness(
        pages=pages,
        duplex=duplex,
        sheets=math.ceil(interior / 2) if duplex else interior,
        paper_mm=paper_mm,
        binding_mm=binding_mm,
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


def upright(character: str) -> bool:
    """Whether a character stands up in a vertical line or turns on its side.

    East Asian width very nearly draws this line: wide and full-width stand
    up, narrow turns. The ambiguous class needs a second look, because it
    holds both marks a CJK line sets upright (×, °) and the accented letters
    of European alphabets -- and turning `Caf` while standing `é` up would
    break one word into two orientations.
    """
    width = unicodedata.east_asian_width(character)
    if width in ("W", "F"):
        return True
    if width != "A":
        return False
    return not (ord(character) < CJK_FIRST and unicodedata.category(character)[0] in "LM")


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
            leading = self.pitch_pt - self.size_pt
            return self.top_pt + (self.height_pt - len(self.lines) * self.pitch_pt + leading) / 2
        return min(self.placed(index)[0][1] for index in range(len(self.lines)))

    @property
    def ink_bottom_pt(self) -> float:
        if not self.vertical:
            return self.ink_top_pt + (len(self.lines) - 1) * self.pitch_pt + self.size_pt
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
    size = capped(name, height_pt / deepest, across / (pitch_factor * len(lines)))
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
        return max(line.advance for line in block.lines) * block.size_pt, 0.0
    return len(block.lines) * block.pitch_pt, (block.pitch_pt - block.size_pt) / 2


def lay_out(
    text: SpineText,
    width_pt: float,
    ruler: pymupdf.Font,
    cover: Cover | None,
) -> Spine:
    """Lay the spine out, optionally stretched to the cover's own text extent.

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
    if cover is None:
        return form
    blocks = form.blocks
    settled = sum(block.ink_bottom_pt - block.ink_top_pt for block in blocks[1:])
    elastic = blocks[0].height_pt + sum(
        after.ink_top_pt - before.ink_bottom_pt for before, after in zip(blocks, blocks[1:])
    )
    if cover.text_height_pt <= settled or elastic <= 0:
        raise CollectionError(
            "The cover's text is shorter than the spine's own lines, so the two "
            "cannot be aligned. Pass --no-cover-alignment to keep the form's rows."
        )
    stretch = (cover.text_height_pt - settled) / elastic

    heights = form_heights()
    lettered = [index for index, (name, _) in enumerate(LAYOUT) if name]
    ink_top, filled, previous = cover.top_pt, 0.0, -1
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

    heights[-1] = PAGE_HEIGHT_PT - sum(heights[:-1])
    if heights[-1] < 0:
        raise CollectionError(
            "Aligning to the cover would run the spine past the foot of the page. "
            "Pass --no-cover-alignment to keep the form's own rows."
        )
    return build_rows(text, width_pt, ruler, heights)


# --------------------------------------------------------------------------
# The PDF
# --------------------------------------------------------------------------


def write_pdf(
    spine: Spine,
    font: pymupdf.Font,
    metadata: dict[str, str],
    target: Path,
    subsettable: bool = True,
) -> None:
    """Draw the spine directly, run by run.

    Converting the ODT would mean an office suite in the toolchain; the
    placement is already computed, so the text is simply set where the layout
    puts it. Upright characters are centred in their column; a turned run is
    drawn horizontally and rotated a quarter turn clockwise about its own
    start, which is how a vertical line sets Latin.
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
    leading = block.pitch_pt - block.size_pt * (font.ascender - font.descender)
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
        '<style:style style:name="Sideways" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0pt" fo:border="none" '
        'style:vertical-align="middle" style:writing-mode="tb-rl"/></style:style>',
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
        "keywords": f"{binding.name_zh}書背寬 {thickness.width_mm:g} mm",
        "creator": "scripts/make_spine.py",
        "producer": "scripts/make_spine.py",
    }


def verify(odt: Path, pdf: Path, spine: Spine, family: str, embedded: bool) -> None:
    """Refuse to report success until both files hold what was asked for."""
    expected = "".join(line for block in spine.blocks for line in block.texts)
    with pymupdf.open(pdf) as document:
        if document.page_count != 1:
            raise CollectionError(f"{pdf.name} holds {document.page_count} pages, not one.")
        page = document[0]
        if abs(page.rect.width - spine.width_pt) > 0.01:
            raise CollectionError(
                f"{pdf.name} is {page.rect.width:.2f}pt wide, not {spine.width_pt:.2f}pt."
            )
        if abs(page.rect.height - PAGE_HEIGHT_PT) > 0.01:
            raise CollectionError(f"{pdf.name} is not as tall as the thesis page.")
        # One face, though a turned run refers to it under a name of its own,
        # so it is the distinct font objects that have to come to one. A PDF
        # writer names an embedded face by its full name, style included, so
        # the family has to be found inside that rather than equal to it.
        fonts = {font[0]: font[3] for font in page.get_fonts(full=True)}
        drawn_in = [reduced(re.sub(r"^[A-Z]{6}\+", "", name)) for name in fonts.values()]
        if len(fonts) != 1 or reduced(family) not in drawn_in[0]:
            raise CollectionError(f"{pdf.name} does not set the spine in {family} alone.")
        if not document.extract_font(next(iter(fonts)))[3]:
            raise CollectionError(f"{pdf.name} does not embed {family}.")
        printed = re.sub(r"\s", "", page.get_text())
        if sorted(printed) != sorted(re.sub(r"\s", "", expected)):
            raise CollectionError(f"{pdf.name} does not print the spine text.")

    with zipfile.ZipFile(odt) as archive:
        names = archive.namelist()
        if names[0] != "mimetype" or archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
            raise CollectionError(f"{odt.name} does not open with an unstored mimetype.")
        content = archive.read("content.xml").decode("utf-8")
        font_entries = [name for name in names if name.startswith("Fonts/")]
        if embedded and (len(font_entries) != 1 or not archive.read(font_entries[0])):
            raise CollectionError(f"{odt.name} does not embed {family}.")
        if font_entries and font_entries[0] not in content:
            raise CollectionError(f"{odt.name} does not point its styles at the embedded font.")
        if quoteattr(family) not in content:
            raise CollectionError(f"{odt.name} does not name {family}.")
        for character in set(expected) - set(" 　"):
            if escape(character) not in content:
                raise CollectionError(f"{odt.name} is missing {character!r}.")


def write_proof(spine_pdf: Path, thesis: Path, target: Path) -> None:
    """Join the spine to the cover, the way the two meet on the bound book.

    An 8 mm spine beside a 210 mm cover makes a 218 mm sheet: the spine on the
    left, the cover butted against it, nothing between them. Reading across
    the join is the quickest check that the two agree.
    """
    with pymupdf.open(spine_pdf) as spine, pymupdf.open(thesis) as book:
        cover = book[0]
        width = spine[0].rect.width + cover.rect.width
        with pymupdf.open() as proof:
            page = proof.new_page(width=width, height=cover.rect.height)
            page.show_pdf_page(
                pymupdf.Rect(0, 0, spine[0].rect.width, spine[0].rect.height), spine, 0
            )
            page.show_pdf_page(
                pymupdf.Rect(spine[0].rect.width, 0, width, cover.rect.height), book, 0
            )
            proof.save(target, garbage=4, deflate=True)
    logging.info("Wrote %s", target)


def describe(
    binding: Binding,
    thickness: Thickness,
    spine: Spine,
    cover: Cover | None,
    written: list[Path],
) -> None:
    sides = "雙面 (double-sided)" if thickness.duplex else "單面 (single-sided)"
    print(f"{binding.name_zh} ({binding.key}): {thickness.width_mm:g} mm wide")
    if thickness.measured_mm is None:
        print(
            f"  thickness   {thickness.pages} pages less the cover, {sides},"
            f" {thickness.sheets} sheets x {thickness.paper_mm:g} mm"
            f" = {thickness.text_block_mm:.2f} mm"
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
    if cover is None:
        print("  alignment   the form's own rows (cover alignment off)")
    else:
        print(
            f"  alignment   text {spine.ink_top_pt:.1f}-{spine.ink_bottom_pt:.1f} pt,"
            f" the cover's {cover.top_pt:.1f}-{cover.bottom_pt:.1f} pt"
        )
    for block in spine.blocks:
        note = " (shrunk to fit)" if block.shrunk else ""
        print(f"  {block.name:<9} {block.size_pt:g} pt{note}  {' / '.join(block.texts)}")
    for path in written:
        print(f"  {path.name:<34} {path.stat().st_size:,} bytes")


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
        cover = read_cover(document)

    text = read_thesis_text(PROJECT_ROOT, cover.date)
    font_file = locate_font(cover.font, PROJECT_ROOT)
    logging.info("The thesis sets Chinese in %s (%s)", cover.font, font_file.path)
    absent = missing_characters(font_file, text.characters())
    if absent:
        raise CollectionError(f"{font_file.name} has no glyph for {absent!r}.")

    if not font_file.shipped:
        logging.warning(
            "%s is not one of the faces this template ships. Both files are laid "
            "out alike, but LibreOffice sets some faces' vertical lines about an "
            "ascent higher than the PDF draws them, so take the PDF as the one "
            "to print.",
            font_file.name,
        )
    # Two ways the spine could letter something the cover does not: a value
    # holding LaTeX the shared parser throws away, which is invisible when it
    # sits at either end of the value, and a main.pdf older than the
    # ntusetup.tex beside it. Neither is worth stopping for, and both are
    # worth saying out loud.
    written = raw_ntusetup(PROJECT_ROOT / "ntusetup.tex")
    for name in ("university", "institute", "title", "author"):
        lost = dropped_commands(written.get(name, ""))
        if lost:
            logging.warning(
                "ntusetup.tex writes %s with %s, which the spine cannot read and "
                "leaves out. The cover still prints it, so the two will differ.",
                name,
                ", ".join(sorted(set(lost))),
            )
    for name in ("university", "institute", "degree", "title", "author"):
        wording = getattr(text, name)
        if not cover.prints(wording):
            logging.warning(
                "The cover does not print %s %r. Check that main.pdf is the build "
                "of this ntusetup.tex.",
                name,
                wording,
            )
    embedding = embeddable_font(font_file, text.characters())
    # The ODT keeps the face as it is, because LibreOffice picks the vertical
    # forms itself; the PDF carries a copy that has already picked them.
    drawn = drawn_face(embedding.face, text.vertical_characters())
    family = font_names(font_file)[0]
    ruler = pymupdf.Font(fontbuffer=drawn)
    aligned = None if args.no_cover_alignment else cover

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
            measured_mm=args.paperback_width,
        )
        spine = lay_out(text, mm(thickness.width_mm), ruler, aligned)
        metadata = spine_metadata(text, binding, thickness)
        stem = args.output_dir / f"{source.stem}-spine-{binding.key}"
        odt, pdf = stem.with_suffix(".odt"), stem.with_suffix(".pdf")
        write_odt(spine, family, embedding.face if embedding.editable else None, metadata, odt)
        write_pdf(spine, ruler, metadata, pdf, embedding.subsettable)
        verify(odt, pdf, spine, family, embedding.editable)
        written = [odt, pdf]
        if args.with_cover:
            proof = stem.with_name(f"{stem.name}-with-cover").with_suffix(".pdf")
            write_proof(pdf, source, proof)
            written.append(proof)
        describe(binding, thickness, spine, aligned, written)


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
        "--paperback-width", type=float, metavar="MM",
        help=(
            "the 平裝 copy's own measured thickness in mm, used instead of the "
            "computed one; 精裝 is always this plus its boards, so measure the "
            "paperback even when writing the hardcover"
        ),
    )
    parser.add_argument(
        "--with-cover", action="store_true",
        help="also write <name>-with-cover.pdf: the spine joined to the thesis's cover",
    )
    parser.add_argument(
        "--no-cover-alignment", action="store_true",
        help=(
            "keep the form's own row positions instead of stretching them so the "
            "spine's text lines up with the cover's first and last lines"
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
