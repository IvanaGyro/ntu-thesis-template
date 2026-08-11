#!/usr/bin/env python3
"""Apply NTU submission permissions to the built thesis PDF.

The generated PDF keeps an empty user password, so anyone can open and read
it without being prompted.  An owner password locks the permission flags:
copying and editing are denied, while printing and text extraction for
accessibility tools stay allowed.

This step is deliberately manual; ``pixi run build`` never calls it.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
from pathlib import Path

import pymupdf


PROJECT_ROOT = Path(
    os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
DEFAULT_INPUT = PROJECT_ROOT / "main.pdf"
DEFAULT_SUFFIX = "-protected"
PASSWORD_ENV = "NTU_THESIS_PDF_OWNER_PASSWORD"
OWNER_ACCESS = 4  # Document.authenticate() bit for owner-level access.

ENCRYPTION_METHODS = {
    "aes-256": pymupdf.PDF_ENCRYPT_AES_256,
    "aes-128": pymupdf.PDF_ENCRYPT_AES_128,
    "rc4-128": pymupdf.PDF_ENCRYPT_RC4_128,
}

# Permissions granted to a reader who opens the file without a password.
# Everything omitted here requires the owner password.
GRANTED_PERMISSIONS = {
    "print the document": pymupdf.PDF_PERM_PRINT,
    "print at full resolution": pymupdf.PDF_PERM_PRINT_HQ,
    "extract text for accessibility tools": pymupdf.PDF_PERM_ACCESSIBILITY,
}
DENIED_PERMISSIONS = {
    "copy text and graphics": pymupdf.PDF_PERM_COPY,
    "modify the contents": pymupdf.PDF_PERM_MODIFY,
    "add or change annotations": pymupdf.PDF_PERM_ANNOTATE,
    "fill in form fields": pymupdf.PDF_PERM_FORM,
    "insert, delete, or rotate pages": pymupdf.PDF_PERM_ASSEMBLE,
}


def permission_flags(allow_printing: bool) -> int:
    flags = 0
    for name, flag in GRANTED_PERMISSIONS.items():
        if not allow_printing and flag in (
            pymupdf.PDF_PERM_PRINT,
            pymupdf.PDF_PERM_PRINT_HQ,
        ):
            logging.debug("withholding permission: %s", name)
            continue
        flags |= flag
    return flags


def resolve_password(argument: str | None) -> str:
    password = argument or os.environ.get(PASSWORD_ENV)
    if password:
        return password

    if not sys.stdin.isatty():
        raise RuntimeError(
            "No owner password given. Pass --password, set "
            f"{PASSWORD_ENV}, or run the script from a terminal."
        )

    password = getpass.getpass("Owner password (needed to edit the PDF): ")
    if password != getpass.getpass("Repeat owner password: "):
        raise RuntimeError("The two passwords do not match.")
    if not password:
        raise RuntimeError("The owner password must not be empty.")
    return password


def default_output(source: Path) -> Path:
    return source.with_name(f"{source.stem}{DEFAULT_SUFFIX}{source.suffix}")


def warn_when_untagged(document: pymupdf.Document) -> None:
    """Report whether the PDF carries the tags screen readers rely on.

    The accessibility permission only removes the legal restriction on text
    extraction. Reading order and alternative text come from a tagged PDF,
    which XeLaTeX does not produce for this thesis.
    """
    catalog = document.pdf_catalog()
    tagged = document.xref_get_key(catalog, "StructTreeRoot")[0] != "null"
    if not tagged:
        logging.warning(
            "The PDF has no structure tree, so it is not a tagged PDF. "
            "Assistive tools may extract the text but cannot rely on the "
            "reading order."
        )


def describe(document: pymupdf.Document) -> None:
    granted = document.permissions
    print(f"{Path(document.name).name}: opens without a password.")
    print("Permissions of a reader who does not know the owner password:")
    for name, flag in {**GRANTED_PERMISSIONS, **DENIED_PERMISSIONS}.items():
        print(f"  {'allowed' if granted & flag else 'denied':<7}  {name}")


def verify(target: Path, password: str, expected: int) -> None:
    with pymupdf.open(target) as document:
        if document.needs_pass:
            raise RuntimeError(f"{target.name} asks for a password to open.")
        granted = document.permissions
        for name, flag in {**GRANTED_PERMISSIONS, **DENIED_PERMISSIONS}.items():
            if bool(granted & flag) == bool(expected & flag):
                continue
            verb = "may still" if granted & flag else "cannot"
            raise RuntimeError(f"A reader without the password {verb} {name}.")

    with pymupdf.open(target) as document:
        # authenticate() reports 2 for the (empty) user password and 4 for the
        # owner password, so only bit 4 proves the password grants full rights.
        if not document.authenticate(password) & OWNER_ACCESS:
            raise RuntimeError("The owner password does not unlock the PDF.")
        if not document.permissions & pymupdf.PDF_PERM_MODIFY:
            raise RuntimeError("The owner password does not allow editing.")
        logging.info("Owner password accepted; it grants full access.")


def protect(
    source: Path,
    target: Path,
    password: str,
    encryption: int,
    allow_printing: bool,
) -> None:
    if not source.is_file():
        raise RuntimeError(f"No such PDF: {source}. Run `pixi run build` first.")
    if target.resolve() == source.resolve():
        raise RuntimeError(
            "Refusing to overwrite the source PDF; choose another --output."
        )

    flags = permission_flags(allow_printing)
    with pymupdf.open(source) as document:
        if document.needs_pass:
            raise RuntimeError(f"{source.name} cannot be opened without a password.")
        if document.metadata.get("encryption"):
            raise RuntimeError(
                f"{source.name} is already encrypted "
                f"({document.metadata['encryption']}). Protect the PDF that "
                "`pixi run build` produced instead."
            )
        warn_when_untagged(document)
        document.save(
            target,
            encryption=encryption,
            owner_pw=password,
            user_pw="",
            permissions=flags,
        )
    logging.info("Wrote %s", target)

    verify(target, password, flags)
    with pymupdf.open(target) as document:
        describe(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="PDF to protect (default: main.pdf)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="where to write the protected PDF (default: <input>-protected.pdf)",
    )
    parser.add_argument(
        "-p",
        "--password",
        help=(
            "owner password; prompted for interactively when omitted, or read "
            f"from {PASSWORD_ENV}"
        ),
    )
    parser.add_argument(
        "--encryption",
        choices=tuple(ENCRYPTION_METHODS),
        default="aes-256",
        help="encryption algorithm (default: aes-256)",
    )
    parser.add_argument(
        "--no-print",
        dest="allow_printing",
        action="store_false",
        help="also require the password for printing",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    source = args.input.resolve()
    target = (args.output or default_output(source)).resolve()

    try:
        protect(
            source,
            target,
            resolve_password(args.password),
            ENCRYPTION_METHODS[args.encryption],
            args.allow_printing,
        )
    except (EOFError, KeyboardInterrupt):
        logging.error("Interrupted before the PDF was protected.")
        return 1
    except (RuntimeError, pymupdf.FileDataError, OSError) as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
