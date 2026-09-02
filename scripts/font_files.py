"""Resolve an OpenType face by file or system family name.

The thesis class gives a file beside the project precedence over an installed
family.  Python helpers that inspect the selected face must make the same
choice, including the face index when the file is a TrueType/OpenType
collection.  Fontconfig is allowed to propose a system face, but its fallback
substitutions are never accepted as the requested family.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fontTools.ttLib import TTCollection, TTFont


FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
FONT_NAME_IDS = (1, 4, 6, 16)


class FontResolutionError(ValueError):
    """The configured face cannot be found without a fallback substitution."""


def reduced_font_name(value: str) -> str:
    """Remove spacing and punctuation while retaining letters from every script."""
    return re.sub(r"[\W_]+", "", value.casefold())


def same_font(name: str, candidate: str) -> bool:
    """Whether two family/full/PostScript names differ only cosmetically."""
    return reduced_font_name(name) == reduced_font_name(candidate)


@dataclass(frozen=True)
class FontFile:
    """One face on disk; collections carry the selected zero-based index."""

    path: Path
    index: int = 0

    @property
    def name(self) -> str:
        return self.path.name if not self.index else f"{self.path.name}#{self.index}"

    def open(self, **kwargs: object) -> TTFont:
        return TTFont(self.path, fontNumber=self.index, **kwargs)


def font_names(font: FontFile) -> tuple[str, ...]:
    """All localized family, full, PostScript and typographic-family names."""
    try:
        with font.open(lazy=True) as opened:
            table = opened["name"]
            found = [table.getDebugName(identifier) for identifier in FONT_NAME_IDS]
            found += [
                record.toUnicode(errors="backslashreplace")
                for record in table.names
                if record.nameID in FONT_NAME_IDS
            ]
    except Exception:  # noqa: BLE001 - fontTools uses several defect exceptions
        logging.debug("Not a readable font: %s", font.name)
        return ()

    names: list[str] = []
    for name in found:
        if name and name not in names:
            names.append(name)
    return tuple(names)


def _regular_score(font: FontFile) -> tuple[int, int, int]:
    """Prefer a regular face while scanning directories without a font manager."""
    try:
        with font.open(lazy=True) as opened:
            os2 = opened["OS/2"]
            selection = os2.fsSelection
            styled = bool(selection & ((1 << 0) | (1 << 5) | (1 << 9)))
            return (
                int(styled),
                abs(os2.usWeightClass - 400),
                int(not selection & (1 << 6)),
            )
    except Exception:  # noqa: BLE001 - an unreadable candidate sorts last
        pass
    return (2, 1000, 1)


def collection_faces(path: Path) -> tuple[FontFile, ...]:
    """Every face in a font file, or an empty tuple for an unreadable file."""
    if path.suffix.casefold() not in {".ttc", ".otc"}:
        return (FontFile(path),)
    try:
        collection = TTCollection(path, lazy=True)
        try:
            count = len(collection.fonts)
        finally:
            collection.close()
    except Exception:  # noqa: BLE001 - fontTools uses several defect exceptions
        return ()
    return tuple(FontFile(path, index) for index in range(count))


def _parse_fc_match(
    output: str, search_directories: Iterable[Path] = ()
) -> FontFile | None:
    """Read either the tab-separated or two-line fc-match format."""
    stripped = output.strip()
    if not stripped:
        return None
    first, separator, index = stripped.partition("\t")
    if not separator:
        lines = stripped.splitlines()
        if len(lines) >= 2:
            first, index = lines[0], lines[1]
        else:
            first, index = lines[0], "0"
    path = Path(first.strip())
    if path.is_absolute():
        if not path.is_file():
            return None
    else:
        directories = tuple(search_directories)
        resolved = next(
            (
                directory / path
                for directory in directories
                if (directory / path).is_file()
            ),
            None,
        )
        if resolved is not None:
            path = resolved
        elif directories or not path.is_file():
            return None
    index = index.strip()
    return FontFile(path, int(index) if index.isdigit() else 0)


def fontconfig_match(family: str) -> FontFile | None:
    """Ask fontconfig for a regular face, tolerating Windows format quirks."""
    formats = ("%{file}\t%{index}\n", "%{file}\n%{index}\n")
    for output_format in formats:
        try:
            matched = subprocess.run(
                ["fc-match", f"--format={output_format}", f"{family}:style=Regular"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if matched.returncode == 0 and (
            font := _parse_fc_match(matched.stdout, windows_font_directories())
        ):
            return font
    return None


def windows_font_directories() -> tuple[Path, ...]:
    """The machine-wide and per-user Windows font directories."""
    if os.name != "nt" and sys.platform != "win32":
        return ()
    directories: list[Path] = []
    windows = os.environ.get("WINDIR")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if windows:
        directories.append(Path(windows) / "Fonts")
    if local_app_data:
        directories.append(Path(local_app_data) / "Microsoft" / "Windows" / "Fonts")
    return tuple(directory for directory in directories if directory.is_dir())


def iter_font_files(directories: Iterable[Path]) -> Iterable[Path]:
    """Font files below the given directories, once each and deterministically."""
    seen: set[Path] = set()
    paths: list[Path] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in FONT_EXTENSIONS
        )
    for path in sorted(paths, key=lambda candidate: str(candidate).casefold()):
        try:
            identity = path.resolve()
        except OSError:
            identity = path
        if identity not in seen:
            seen.add(identity)
            yield path


def directory_match(family: str, directories: Iterable[Path]) -> FontFile | None:
    """Find an exactly named regular face by scanning font directories."""
    matches: list[FontFile] = []
    for path in iter_font_files(directories):
        for face in collection_faces(path):
            if any(same_font(family, name) for name in font_names(face)):
                matches.append(face)
    if not matches:
        return None
    return min(matches, key=lambda face: (_regular_score(face), str(face.path).casefold(), face.index))


def system_font(family: str) -> FontFile | None:
    """Resolve an installed family without accepting fontconfig substitution."""
    candidate = fontconfig_match(family)
    if candidate and any(same_font(family, name) for name in font_names(candidate)):
        return candidate
    # Fontconfig in a Pixi process on Windows may have no initialized cache.
    # Scanning the two platform directories also covers that case without
    # changing global fontconfig state.
    return directory_match(family, windows_font_directories())


def local_font_path(root: Path, directory: str | Path, name: str) -> Path:
    """The path the class forms when it checks a configured project font."""
    return root / directory / name


def font_source(root: Path, directory: str | Path, name: str) -> str:
    """Whether the class will interpret the configured name as file or family."""
    return "file" if local_font_path(root, directory, name).is_file() else "family"


def resolve_font(
    root: Path,
    directory: str | Path,
    name: str,
    index: int | None = None,
) -> FontFile:
    """Resolve a configured face exactly as the class does: local file first."""
    path = local_font_path(root, directory, name)
    if path.is_file():
        return FontFile(path, 0 if index is None else index)
    candidate = system_font(name)
    if candidate is None:
        raise FontResolutionError(
            f"{name!r} is neither a file in {directory}/ nor an installed font family"
        )
    return candidate if index is None else FontFile(candidate.path, index)
