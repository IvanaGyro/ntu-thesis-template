#!/usr/bin/env python3
"""Regenerate ntu-academic-units.tex from NTU's published lists of units.

    pixi run units

The generated file is committed, so neither the build nor the TDR generator
needs network access. Re-run this when NTU reorganises a college, which happens
every few years:

    https://www.ntu.edu.tw/academics/academics_list.html
    https://www.ntu.edu.tw/english/academics/academics_list.html

Both pages list one section per college with its departments beneath, in the
same order, so the colleges are zipped positionally into bilingual pairs; the
script refuses to write anything if their counts disagree, since that would pair
a college with the wrong English name.

The department lists are NOT zipped. The two pages disagree about a few of them
— at the time of writing the English page carries a graduate program the Chinese
one omits, and the Chinese page carries one the English one omits — so pairing
by position would silently attach the wrong translation. Each language's
departments are therefore recorded against the college of that same language,
and each field is checked against its own list.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ZH_URL = "https://www.ntu.edu.tw/academics/academics_list.html"
EN_URL = "https://www.ntu.edu.tw/english/academics/academics_list.html"
OUTPUT = Path(__file__).resolve().parents[1] / "ntu-academic-units.tex"

# Colleges are h2 headings carrying the site's `searchcontent` marker class and
# departments are links carrying the same marker, both in document order.
SECTION = re.compile(
    r'<h2[^>]*class="[^"]*searchcontent[^"]*"[^>]*>(.*?)</h2>'
    r'|<a[^>]*class="searchcontent[^"]*"[^>]*>(.*?)</a>',
    re.S,
)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "ntu-thesis-template"})
    with urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="ignore")


def text_of(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def tex_escape(name: str) -> str:
    """Write a unit name the way it has to be written in ntusetup.tex.

    98 of the English names contain an ampersand, and a user has to type it as
    \\& or the cover will not typeset. The declarations must match that spelling
    exactly, because the class compares the two as text.
    """
    for character in "&%#_":
        name = name.replace(character, "\\" + character)
    return name


def parse(page: str) -> dict[str, list[str]]:
    """Map each college to its departments, preserving page order."""
    units: dict[str, list[str]] = {}
    college: str | None = None
    for match in SECTION.finditer(page):
        heading, link = match.group(1), match.group(2)
        if heading is not None:
            name = text_of(heading)
            # Each college heading is emitted twice, once per responsive layout.
            if name and name != college:
                units.setdefault(name, [])
                college = name
        elif college is not None:
            name = text_of(link)
            if name and name not in units[college]:
                units[college].append(name)
    return units


def read_existing_pairs() -> list[tuple[str, str]]:
    """The college pairs in the committed file, for comparison against a refresh."""
    if not OUTPUT.is_file():
        return []
    body = re.sub(r"(?m)^%.*$", "", OUTPUT.read_text(encoding="utf-8"))
    return [
        (m.group(1).replace("\\&", "&"), m.group(2).replace("\\&", "&"))
        for m in re.finditer(r"\\ntu@declarecollege\{([^}]*)\}\{([^}]*)\}", body)
    ]


def main() -> None:
    zh = parse(fetch(ZH_URL))
    en = parse(fetch(EN_URL))

    if len(zh) != len(en):
        sys.exit(f"college counts differ: {len(zh)} Chinese, {len(en)} English")
    if not zh:
        sys.exit("no colleges found; the page markup has probably changed")

    for (zh_college, zh_depts), (en_college, en_depts) in zip(
        zh.items(), en.items()
    ):
        if len(zh_depts) != len(en_depts):
            print(
                f"note: {zh_college} lists {len(zh_depts)} units, "
                f"{en_college} lists {len(en_depts)}; "
                "each language is checked against its own list",
                file=sys.stderr,
            )

    # 兩頁的院系順序若有一邊改動而數量不變，數量檢查是看不出來的，配對就會整批
    # 錯掉。因此把與前一版不同的配對列出來，讓人確認過再提交。
    #
    # Equal counts do not prove equal order: if one page reorders its colleges,
    # every pair silently shifts and the generated file becomes a confidently
    # wrong source for both validators. Print whatever differs from the
    # committed version so a human confirms the pairing before it is committed.
    pairs = list(zip(zh, en))
    previous = read_existing_pairs()
    if previous and previous != pairs:
        print("\nThe college pairing changed since the committed file:", file=sys.stderr)
        for zh_name, en_name in pairs:
            if (zh_name, en_name) not in previous:
                print(f"  + {zh_name}  ->  {en_name}", file=sys.stderr)
        for zh_name, en_name in previous:
            if (zh_name, en_name) not in pairs:
                print(f"  - {zh_name}  ->  {en_name}", file=sys.stderr)
        print(
            "Check these against the two pages before committing: the counts "
            "matching does not prove the order did.\n",
            file=sys.stderr,
        )

    lines = [
        "% Generated by scripts/fetch_academic_units.py; do not edit by hand.",
        "%",
        "% 臺大公布的學術單位一覽，供 ntuthesis.cls 與 generate_tdr_upload_script.py",
        "% 檢查 ntusetup.tex 的 college 與 institute 是否為正式名稱。",
        "%",
        "% NTU's published list of academic units. ntuthesis.cls warns and",
        "% generate_tdr_upload_script.py errors when ntusetup.tex names a college",
        "% or institute that is not here.",
        "%",
        "% \\ntu@declarecollege{中文}{English} pairs the two names of one college.",
        "% \\ntu@declareinstitute{學院}{系所} lists a unit under the college of the",
        "% same language, because the two pages do not list identical departments.",
        "%",
        f"% {ZH_URL}",
        f"% {EN_URL}",
        "",
    ]
    for (zh_college, zh_depts), (en_college, en_depts) in zip(
        zh.items(), en.items()
    ):
        zh_key, en_key = tex_escape(zh_college), tex_escape(en_college)
        lines.append(f"\\ntu@declarecollege{{{zh_key}}}{{{en_key}}}")
        for dept in zh_depts:
            lines.append(f"\\ntu@declareinstitute{{{zh_key}}}{{{tex_escape(dept)}}}")
        for dept in en_depts:
            lines.append(f"\\ntu@declareinstitute{{{en_key}}}{{{tex_escape(dept)}}}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    total = sum(len(v) for v in zh.values())
    print(f"wrote {OUTPUT.name}: {len(zh)} colleges, {total} units")


if __name__ == "__main__":
    main()
