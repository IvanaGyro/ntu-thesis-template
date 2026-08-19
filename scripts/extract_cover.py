#!/usr/bin/env python3
"""Extract the thesis cover, the first page of the built PDF, as its own file.

``main.pdf`` carries document-wide furniture that a one-page cover has no use
for: the outline tree, the named destinations, the page labels, the opening
action, and font programs holding every glyph the rest of the thesis needs.
This script copies page one into an empty document, drops that furniture,
subsets the embedded fonts down to the glyphs the cover actually prints, and
garbage collects whatever is left unreferenced.

The result must render exactly like page one of the source, so the script
compares the two before reporting success: page geometry, rendered pixels,
every character with its font and position, the vector drawings, and the
embedded images.

Like ``protect``, this step is deliberately manual; ``pixi run build`` never
calls it.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path

import pymupdf


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
DEFAULT_INPUT = PROJECT_ROOT / "main.pdf"
DEFAULT_SUFFIX = "-cover"
COVER_PAGE = 0  # zero-based index of the cover inside the built PDF
DEFAULT_DPI = 300

# Catalog entries that describe a whole thesis, not a single cover page.
# ``insert_pdf`` already leaves them behind; they are nulled here as well so a
# change in PyMuPDF cannot smuggle them into the cover unnoticed.
DOCUMENT_FURNITURE = (
    "AcroForm",
    "Dests",
    "Names",
    "OpenAction",
    "Outlines",
    "PageLabels",
    "PageMode",
    "StructTreeRoot",
    "Threads",
)


def default_output(source: Path) -> Path:
    return source.with_name(f"{source.stem}{DEFAULT_SUFFIX}{source.suffix}")


def characters(page: pymupdf.Page) -> list[tuple]:
    """Every glyph on the page with its font, size, and placement."""
    found = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                for char in span["chars"]:
                    found.append(
                        (
                            span["font"],
                            round(span["size"], 6),
                            span["color"],
                            char["c"],
                            tuple(round(value, 4) for value in char["bbox"]),
                            tuple(round(value, 4) for value in char["origin"]),
                        )
                    )
    return found


def image_digests(page: pymupdf.Page) -> list[str]:
    """Hash the pixels of every image the page draws, in drawing order."""
    document = page.parent
    digests = []
    for image in page.get_images(full=True):
        raw = document.extract_image(image[0])
        digests.append(hashlib.sha256(raw["image"]).hexdigest())
    return sorted(digests)


def pixels(page: pymupdf.Page, dpi: int) -> pymupdf.Pixmap:
    return page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)


def fingerprint(page: pymupdf.Page, dpi: int) -> dict[str, object]:
    return {
        "page geometry": (
            tuple(round(value, 4) for value in page.mediabox),
            tuple(round(value, 4) for value in page.cropbox),
            page.rotation,
        ),
        "rendered pixels": hashlib.sha256(pixels(page, dpi).samples).hexdigest(),
        "text": page.get_text(),
        "characters": characters(page),
        "vector drawings": page.get_drawings(),
        "images": image_digests(page),
    }


def report_pixel_difference(
    source: pymupdf.Page, cover: pymupdf.Page, dpi: int
) -> str:
    before, after = pixels(source, dpi), pixels(cover, dpi)
    if (before.width, before.height) != (after.width, after.height):
        return (
            f"{before.width}x{before.height} pixels became "
            f"{after.width}x{after.height} at {dpi} dpi"
        )
    differing = sum(1 for a, b in zip(before.samples, after.samples) if a != b)
    total = len(before.samples)
    return f"{differing} of {total} color samples differ at {dpi} dpi"


def verify(source_path: Path, target: Path, dpi: int) -> None:
    with pymupdf.open(source_path) as source, pymupdf.open(target) as cover:
        if cover.page_count != 1:
            raise RuntimeError(
                f"{target.name} holds {cover.page_count} pages, not just the cover."
            )
        if cover.get_toc():
            raise RuntimeError(f"{target.name} still carries the thesis outline.")
        if cover.embfile_count():
            raise RuntimeError(f"{target.name} still carries embedded files.")

        catalog = cover.pdf_catalog()
        for key in DOCUMENT_FURNITURE:
            if cover.xref_get_key(catalog, key)[0] != "null":
                raise RuntimeError(f"{target.name} still carries /{key}.")

        cover_page = cover[0]
        if cover_page.first_annot is not None:
            raise RuntimeError(f"{target.name} still carries annotations.")
        if cover_page.get_links():
            raise RuntimeError(f"{target.name} still carries links.")

        source_page = source[COVER_PAGE]
        expected = fingerprint(source_page, dpi)
        actual = fingerprint(cover_page, dpi)
        for name, value in expected.items():
            if actual[name] == value:
                logging.info("%s: identical", name)
                continue
            detail = (
                report_pixel_difference(source_page, cover_page, dpi)
                if name == "rendered pixels"
                else f"{value!r} became {actual[name]!r}"
            )
            raise RuntimeError(
                f"The cover does not match page {COVER_PAGE + 1} of "
                f"{source_path.name}: {name} changed ({detail})."
            )


def strip_document_furniture(cover: pymupdf.Document) -> None:
    catalog = cover.pdf_catalog()
    for key in DOCUMENT_FURNITURE:
        if cover.xref_get_key(catalog, key)[0] == "null":
            continue
        logging.debug("dropping /%s from the cover catalog", key)
        cover.xref_set_key(catalog, key, "null")
    if cover.get_toc():
        cover.set_toc([])
    while cover.embfile_count():
        cover.embfile_del(0)


def describe(source_path: Path, target: Path) -> None:
    before, after = source_path.stat().st_size, target.stat().st_size
    with pymupdf.open(target) as cover:
        page = cover[0]
        width = page.rect.width / 72 * 25.4
        height = page.rect.height / 72 * 25.4
        fonts = ", ".join(sorted(font[3] for font in page.get_fonts()))
    print(f"{target.name}: page {COVER_PAGE + 1} of {source_path.name}, one page.")
    print(f"  page size   {width:.0f} x {height:.0f} mm")
    print(f"  fonts kept  {fonts or 'none'}")
    print(f"  file size   {after:,} bytes ({before:,} bytes for the whole thesis)")


def extract(source_path: Path, target: Path, dpi: int) -> None:
    if not source_path.is_file():
        raise RuntimeError(f"No such PDF: {source_path}. Run `pixi run build` first.")
    if target.resolve() == source_path.resolve():
        raise RuntimeError(
            "Refusing to overwrite the source PDF; choose another --output."
        )

    with pymupdf.open(source_path) as source:
        if source.needs_pass:
            raise RuntimeError(
                f"{source_path.name} cannot be opened without a password. "
                "Extract the cover from the PDF that `pixi run build` produced."
            )
        if source.page_count <= COVER_PAGE:
            raise RuntimeError(f"{source_path.name} has no page {COVER_PAGE + 1}.")

        with pymupdf.open() as cover:
            cover.insert_pdf(
                source,
                from_page=COVER_PAGE,
                to_page=COVER_PAGE,
                annots=False,
                links=False,
            )
            strip_document_furniture(cover)
            # MuPDF rewrites the embedded font programs with only the glyphs
            # this page uses; the thesis-wide subsets are the bulk of a cover.
            cover.subset_fonts()
            cover.set_metadata(source.metadata)
            # clean=True re-serializes content streams through float32, which
            # nudges bezier control points on curve-heavy art (e.g. the cover
            # seal) by fractions of a point -- enough to flip a handful of
            # antialiased pixels and fail the pixel-exact check below.
            # garbage=4 already does the size-reducing work here, so clean is
            # left off rather than loosening what "exact" means.
            cover.save(target, garbage=4, deflate=True)
    logging.info("Wrote %s", target)

    verify(source_path, target, dpi)
    describe(source_path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="built thesis PDF (default: main.pdf)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="where to write the cover (default: <input>-cover.pdf)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=(
            "resolution at which the cover is compared with the source page "
            f"(default: {DEFAULT_DPI})"
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.dpi < 1:
        logging.error("--dpi must be positive.")
        return 1

    source_path = args.input.resolve()
    target = (args.output or default_output(source_path)).resolve()

    try:
        extract(source_path, target, args.dpi)
    except (RuntimeError, pymupdf.FileDataError, OSError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
