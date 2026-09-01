#!/usr/bin/env python3
"""Install and use a rootless TinyTeX toolchain through PyTinyTeX."""

from __future__ import annotations

import argparse
import html
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pygments
import pytinytex


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
PIXI_DIR = PROJECT_ROOT / ".pixi"
USER_CACHE_BASE = Path(
    os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")
).expanduser()
TINYTEX_ROOT = Path(
    os.environ.get(
        "NTU_THESIS_TINYTEX_ROOT", USER_CACHE_BASE / "ntu-thesis-template" / "pytinytex"
    )
).expanduser().resolve()
DOWNLOAD_DIR = TINYTEX_ROOT.parent / "downloads"
FONTCONFIG_DIR = PIXI_DIR / "fontconfig"

# TeX Live packages providing imports in ntuthesis.cls and ntusetup.tex.
# tlmgr resolves their transitive dependencies, avoiding thousands of
# unrelated packages from the broad TeX Live collections.
TEX_PACKAGES = (
    "accsupp",
    "amsfonts",
    "amsmath",
    "biber",
    "biblatex",
    "booktabs",
    "caption",
    "cjk",
    "datetime",
    "diagbox",
    "enumitem",
    "eso-pic",
    "fancyhdr",
    "fontspec",
    "footmisc",
    "fp",
    "geometry",
    "graphics",
    "hyperref",
    "iftex",
    "kvdefinekeys",
    "kvoptions",
    "kvsetkeys",
    "l3experimental",
    "l3packages",
    "latexmk",
    "lipsum",
    "minted",
    "multirow",
    "paralist",
    "pdfpages",
    "pgf",
    "pict2e",
    "placeins",
    "setspace",
    "stix2-otf",
    "titlesec",
    "tocloft",
    "tools",
    "ulem",
    "unicode-math",
    "xcolor",
    "xecjk",
    "zhlipsum",
)

REQUIRED_TEX_FILES = (
    "biblatex.sty",
    "minted.sty",
    "unicode-math.sty",
    "xeCJK.sty",
    "STIXTwoMath-Regular.otf",
)

# Fonts the class loads by filename. XeTeX resolves these through kpathsea, so
# the build does not depend on fontconfig; the entries below only exist so that
# `doctor` can report where each one came from.
FONT_PROBES = (
    "STIXTwoMath-Regular.otf",
)


def configure_pytinytex() -> None:
    """Point PyTinyTeX at the thesis-specific, rootless installation."""
    os.environ["PYTINYTEX_TINYTEX"] = str(TINYTEX_ROOT)
    pytinytex.clear_path_cache()


def tinytex_bin() -> Path:
    """Return TinyTeX's platform binary directory and add it to PATH."""
    configure_pytinytex()
    bin_dir = Path(pytinytex.get_tinytex_path()).resolve()
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    if os.path.normcase(str(bin_dir)) not in {
        os.path.normcase(entry) for entry in path_entries if entry
    }:
        os.environ["PATH"] = os.pathsep.join((str(bin_dir), *path_entries))
    return bin_dir


def find_tlmgr(bin_dir: Path) -> Path | None:
    """Locate tlmgr in bin_dir regardless of platform extension.

    TinyTeX ships it as a bare `tlmgr` on Linux and macOS but as `tlmgr.bat`
    on Windows, so an extension-less path check never matches there.
    """
    for candidate in bin_dir.iterdir():
        if candidate.is_file() and candidate.stem == "tlmgr":
            return candidate
    return None


def ensure_tinytex() -> Path:
    """Download the extended TinyTeX distribution when it is not installed."""
    try:
        bin_dir = tinytex_bin()
        if find_tlmgr(bin_dir) is not None:
            return bin_dir
    except (FileNotFoundError, RuntimeError):
        pass

    TINYTEX_ROOT.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logging.info("Downloading TinyTeX into %s", TINYTEX_ROOT)
    pytinytex.download_tinytex(
        # PyTinyTeX 0.5.1 cannot unpack the current variation-1 .tar.xz asset.
        # Variation 2 is still natively supported and also gives the thesis a
        # more complete baseline before the explicit package checks below.
        variation=2,
        target_folder=TINYTEX_ROOT,
        download_folder=DOWNLOAD_DIR,
    )
    return tinytex_bin()


def installed_package_names() -> set[str]:
    """Normalize PyTinyTeX's installed-package records across releases."""
    names: set[str] = set()
    for record in pytinytex.list_installed():
        if isinstance(record, str):
            names.add(record)
        elif isinstance(record, dict):
            name = record.get("name") or record.get("package")
            if name:
                names.add(str(name))
    return names


def install_tex_packages() -> None:
    installed = installed_package_names()
    for package in TEX_PACKAGES:
        if package in installed:
            logging.info("TeX package already installed: %s", package)
            continue
        logging.info("Installing TeX package: %s", package)
        pytinytex.install(package)


def find_font_file(filename: str) -> Path:
    """Locate a font TinyTeX installed, by filename, anywhere in its texmf tree."""
    matches = list(TINYTEX_ROOT.glob(f"**/texmf-dist/fonts/**/{filename}"))
    if not matches:
        raise RuntimeError(
            f"TinyTeX does not provide {filename}; check TEX_PACKAGES"
        )
    return matches[0]


def font_dirs() -> list[Path]:
    """Directories holding the fonts the class loads, deduplicated, in order."""
    dirs: list[Path] = []
    for filename in FONT_PROBES:
        directory = find_font_file(filename).parent
        if directory not in dirs:
            dirs.append(directory)
    return dirs


def configure_fontconfig() -> Path:
    """Configure fontconfig for TinyTeX's bundled and platform fonts."""
    dirs = font_dirs()
    FONTCONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = FONTCONFIG_DIR / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    config_file = FONTCONFIG_DIR / "fonts.conf"

    include_files: list[Path] = []
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        prefix = Path(conda_prefix)
        include_files.extend(
            (
                prefix / "etc/fonts/fonts.conf",
                prefix / "Library/etc/fonts/fonts.conf",
            )
        )
    include_files.append(Path("/etc/fonts/fonts.conf"))

    includes = "\n".join(
        f'  <include ignore_missing="yes">{html.escape(str(path))}</include>'
        for path in include_files
    )
    font_dir_elements = "\n".join(
        f"  <dir>{html.escape(str(path))}</dir>" for path in dirs
    )
    config_file.write_text(
        "<?xml version=\"1.0\"?>\n"
        "<!DOCTYPE fontconfig SYSTEM \"urn:fontconfig:fonts.dtd\">\n"
        "<fontconfig>\n"
        f"{includes}\n"
        f"{font_dir_elements}\n"
        f"  <cachedir>{html.escape(str(cache_dir))}</cachedir>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    os.environ["FONTCONFIG_FILE"] = str(config_file)
    subprocess.run(["fc-cache", "-f", *(str(path) for path in dirs)], check=True)
    return config_file


def executable(name: str) -> Path:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required executable is unavailable: {name}")
    return Path(path)


def verify_toolchain() -> None:
    bin_dir = tinytex_bin()
    configure_fontconfig()

    required_commands = ("xelatex", "latexmk", "biber", "kpsewhich", "fc-match")
    for command in required_commands:
        logging.info("%s: %s", command, executable(command))

    for filename in REQUIRED_TEX_FILES:
        result = subprocess.run(
            ["kpsewhich", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            raise RuntimeError(f"TinyTeX cannot find required file: {filename}")
        logging.info("%s: %s", filename, result.stdout.strip())

    # The class loads its text fonts by filename, so kpathsea already proved they
    # exist above. fontconfig only has to resolve the math font, which
    # unicode-math looks up by family name.
    matched_font = subprocess.run(
        ["fc-match", "--format=%{family}\n", "STIX Two Math"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if "STIX Two Math" not in matched_font:
        raise RuntimeError(f"fontconfig did not select STIX Two Math (got {matched_font!r})")

    print(f"TinyTeX bin: {bin_dir}")
    print(f"Pygments: {pygments.__version__}")
    print(f"Math font: {matched_font}")
    for filename in FONT_PROBES:
        print(f"{filename}: {find_font_file(filename)}")


def setup() -> None:
    ensure_tinytex()
    install_tex_packages()
    verify_toolchain()


def doctor() -> None:
    ensure_tinytex()
    configure_fontconfig()
    report = pytinytex.doctor()
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status} {check.name}: {check.message}")
    if not report.healthy:
        raise RuntimeError("PyTinyTeX doctor reported a failed check")
    verify_toolchain()


def build() -> None:
    verify_toolchain()
    subprocess.run(
        [
            "latexmk",
            "-pdf",
            "-pdflatex=xelatex -shell-escape -interaction=nonstopmode "
            "-file-line-error %O %S",
            "main.tex",
        ],
        check=True,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
    )


def clean() -> None:
    ensure_tinytex()
    subprocess.run(
        ["latexmk", "-C", "main.tex"],
        check=True,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "doctor", "build", "clean"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        {"setup": setup, "doctor": doctor, "build": build, "clean": clean}[
            args.command
        ]()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
