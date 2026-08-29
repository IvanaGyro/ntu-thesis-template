#!/usr/bin/env python3
"""Read the thesis's own words out of main.tex and ntusetup.tex.

Two scripts need the same few facts about a thesis -- the spine artwork and
the TDR upload filler -- and both should read them from the same place and
in the same way. This is that place: the `\\documentclass` options that say
which degree and which fonts, and the `\\ntusetup` block that says whose
thesis it is and what it is called.

The source is read rather than the built PDF: what `\\ntusetup` holds is one
value per key, already free of the line breaks a typeset cover puts in.
"""

from __future__ import annotations

import re
from pathlib import Path


class CollectionError(ValueError):
    """Raised when the thesis does not say something a caller needs."""


def strip_comments(text: str) -> str:
    """Drop every LaTeX comment, keeping an escaped percent sign."""
    lines = []
    for line in text.splitlines():
        match = re.search(r"(?<!\\)%", line)
        lines.append(line[: match.start()] if match else line)
    return "\n".join(lines)


def braced_group(text: str, opening: int) -> tuple[str, int]:
    """The contents of the group at `opening`, and where it ends.

    Counting braces rather than matching a pattern, so a value may hold
    groups of its own -- `title = {以 \\textbf{粗體} 標示}` is one value.
    """
    if opening >= len(text) or text[opening] != "{":
        raise CollectionError("Expected an opening brace while parsing LaTeX")
    depth = 0
    escaped = False
    for index in range(opening, len(text)):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index], index + 1
    raise CollectionError("Unbalanced braces while parsing LaTeX")


def latex_to_plain(text: str) -> str:
    """What a value says once the markup around it is taken off."""
    text = strip_comments(text)
    text = re.sub(r"\\(?:begin|end)\{[^{}]+\}", "", text)
    text = re.sub(r"\\texorpdfstring\s*\{([^{}]*)\}\s*\{[^{}]*\}", r"\1", text)
    unwrap = re.compile(
        r"\\(?:textbf|textit|emph|mbox|textrm|textsf|texttt|mathrm|mathbf|"
        r"mathit|operatorname|url)\s*\{([^{}]*)\}"
    )
    previous = None
    while previous != text:
        previous = text
        text = unwrap.sub(r"\1", text)
    for source, target in {
        r"\&": "&",
        r"\%": "%",
        r"\#": "#",
        r"\_": "_",
        r"\$": "$",
        r"\{": "{",
        r"\}": "}",
        "~": " ",
    }.items():
        text = text.replace(source, target)
    text = re.sub(r"\\[(),\[\]]", "", text).replace("$", "")
    text = re.sub(r"\\[A-Za-z@]+\*?", "", text)
    return text.replace("{", "").replace("}", "")


def collapse_spaces(text: str) -> str:
    """One space wherever the source had any run of whitespace."""
    return re.sub(r"\s+", " ", text).strip()


KEY = re.compile(r"([A-Za-z][\w*-]*)\s*=\s*")


def key_values(block: str) -> dict[str, str]:
    """The key=value pairs of a keyval list, as the class's own parser reads it.

    A value runs to the comma that ends it, counting braces on the way so
    that `title = {以 {粗體} 標示}, ...` is one value; the braces come off
    only when they wrap the whole of it, since `title = {AI} 與醫療` says
    more than `AI`.
    """
    values: dict[str, str] = {}
    cursor = 0
    while match := KEY.search(block, cursor):
        cursor, depth = match.end(), 0
        while cursor < len(block) and not (block[cursor] == "," and not depth):
            if block[cursor] == "\\":
                cursor += 1
            elif block[cursor] == "{":
                depth += 1
            elif block[cursor] == "}":
                depth -= 1
            cursor += 1
        value = block[match.end() : cursor].strip()
        if value.startswith("{") and braced_group(value, 0)[1] == len(value):
            value = value[1:-1].strip()
        values[match.group(1)] = value
    return values


def parse_ntusetup(path: Path) -> dict[str, str]:
    """Every key of every `\\ntusetup` block in the file, as plain text.

    A file may hold more than one block -- main.tex keeps the fonts in one and
    the verification letter in another -- and the class reads them all, so this
    does too. A later block wins, exactly as it would when the class runs.
    """
    text = strip_comments(path.read_text(encoding="utf-8"))
    blocks = re.compile(r"\\ntusetup\s*\{")
    values: dict[str, str] = {}
    cursor, seen = 0, False
    while marker := blocks.search(text, cursor):
        seen = True
        block, cursor = braced_group(text, marker.end() - 1)
        values.update(key_values(block))
    if not seen:
        raise CollectionError(f"Could not find \\ntusetup in {path}")
    return {key: latex_to_plain(value).strip() for key, value in values.items()}


def class_options(path: Path) -> dict[str, str]:
    """The ntuthesis options set in main.tex.

    A document may take the class without options at all, which is not an
    error: every option has a default, and an absent one simply takes it.
    """
    text = strip_comments(path.read_text(encoding="utf-8"))
    if not re.search(r"\\documentclass\s*(\[.*?\])?\s*\{ntuthesis\}", text, re.DOTALL):
        raise CollectionError(f"Could not find \\documentclass{{ntuthesis}} in {path}")
    given = re.search(r"\\documentclass\s*\[(.*?)\]\s*\{ntuthesis\}", text, re.DOTALL)
    return key_values(given.group(1)) if given else {}
