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

import logging
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


# 會印出文字的控制序列，換成它們印出的字。
# The control sequences that put something on the page. What is left after
# these is markup -- \par, \\, \, and the like -- and dropping that is right;
# dropping one of these would quietly take a word out of a title.
TEXT_COMMANDS = {
    r"\LaTeXe": "LaTeX2e",
    r"\XeLaTeX": "XeLaTeX",
    r"\LaTeX": "LaTeX",
    r"\TeX": "TeX",
    r"\ldots": "…",
    r"\dots": "…",
    r"\textbackslash": "\\",
    r"\textasciitilde": "~",
    r"\textasciicircum": "^",
}


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
    # Every remaining control sequence in one pass, so that what a command
    # sets cannot be mistaken for markup by the pass after it. Most of them
    # print nothing outside a paragraph and taking them out is the point; one
    # that would have printed something is a word gone missing from a title,
    # so it is said out loud rather than swallowed.
    dropped: list[str] = []

    def printed(found: re.Match[str]) -> str:
        command = found.group(1)
        if command == "\\\\":  # a forced break, which is a space on one line
            return " "
        if command in TEXT_COMMANDS:
            return TEXT_COMMANDS[command]
        dropped.append(command)
        return ""

    written = re.sub(r"(\\\\|\\[A-Za-z@]+\*?)\s*(?:\{\})?", printed, text)
    if dropped:
        logging.warning(
            "Dropped %s from %r, which prints nothing here. Write what it sets "
            "as plain text if the cover needs it.",
            ", ".join(sorted(set(dropped))),
            collapse_spaces(text),
        )
    return written.replace("{", "").replace("}", "")


def collapse_spaces(text: str) -> str:
    """One space wherever the source had any run of whitespace."""
    return re.sub(r"\s+", " ", text).strip()


VALUE = re.compile(r"([A-Za-z][\w*-]*)\s*=\s*\{")


def parse_ntusetup(path: Path) -> dict[str, str]:
    """Every key of the `\\ntusetup` block, as plain text."""
    text = strip_comments(path.read_text(encoding="utf-8"))
    marker = re.search(r"\\ntusetup\s*\{", text)
    if not marker:
        raise CollectionError(f"Could not find \\ntusetup in {path}")
    block, _ = braced_group(text, marker.end() - 1)
    values: dict[str, str] = {}
    cursor = 0
    while match := VALUE.search(block, cursor):
        value, cursor = braced_group(block, match.end() - 1)
        values[match.group(1)] = latex_to_plain(value).strip()
    return values


def class_options(path: Path) -> dict[str, str]:
    """The ntuthesis options set in main.tex.

    A document may take the class without options at all, which is not an
    error: every option has a default, and an absent one simply takes it.
    """
    text = strip_comments(path.read_text(encoding="utf-8"))
    if not re.search(r"\\documentclass\s*(\[.*?\])?\s*\{ntuthesis\}", text, re.DOTALL):
        raise CollectionError(f"Could not find \\documentclass{{ntuthesis}} in {path}")
    given = re.search(r"\\documentclass\s*\[(.*?)\]\s*\{ntuthesis\}", text, re.DOTALL)
    if not given:
        return {}
    # A value may be wrapped in braces -- `degree = {doctor}` -- which the
    # class's own key-value parser takes off before it looks at the value, and
    # which also lets a value hold the comma that would otherwise end it.
    options, cursor = given.group(1), 0
    values: dict[str, str] = {}
    while match := re.compile(r"([A-Za-z][\w*-]*)\s*=\s*").search(options, cursor):
        if options[match.end() : match.end() + 1] == "{":
            value, cursor = braced_group(options, match.end())
        else:
            cursor = options.find(",", match.end())
            cursor = len(options) if cursor < 0 else cursor
            value = options[match.end() : cursor]
        values[match.group(1)] = value.strip()
    return values
