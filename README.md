# NTU Thesis Template

A LaTeX template for National Taiwan University master's theses and doctoral
dissertations, following 國立臺灣大學碩、博士學位論文格式規範. Chinese and English
are both supported, and the cover, verification letter, table of contents,
denotation list, and bibliography are all generated for you.

Compile it once before changing anything — the shipped example builds to a
complete 36-page thesis with placeholder content, so you can see every feature
working before you replace it.

## Quick start on Overleaf

1. Download this repository as a ZIP and upload it to Overleaf as a new project.
2. Open **Menu → Compiler** and select **XeLaTeX**. This is required: the
   template uses `xeCJK` and `fontspec`, which pdfLaTeX cannot run.
3. Compile.

`minted` needs the compiler to run with `-shell-escape`. Overleaf enables this
for all projects, so nothing further is needed there.

## Building locally

The repository ships a rootless toolchain based on [Pixi](https://pixi.sh) and
PyTinyTeX, so no system-wide TeX installation and no `sudo` are required:

```bash
pixi run setup     # download TinyTeX and install every TeX package used
pixi run doctor    # check the installation
pixi run build     # produce main.pdf
pixi run clean     # remove build artifacts, keep the toolchain
```

`build` depends on `setup`, so a single `pixi run build` is enough the first
time. TinyTeX is installed under `~/.cache/ntu-thesis-template/pytinytex`;
`NTU_THESIS_TINYTEX_ROOT` overrides that, but keep it outside the repository or
`minted` will refuse to run.

On Intel Macs (`osx-64`), `pixi run setup` compiles one dependency from source,
which needs Apple's SDK headers; install Xcode's Command Line Tools first
(`xcode-select --install`) if you don't already have them.

If XeLaTeX, latexmk, and Biber are already on your `PATH`, skip Pixi entirely:

```bash
latexmk -pdf -pdflatex="xelatex -shell-escape -interaction=nonstopmode -file-line-error %O %S" main.tex
```

When a change does not seem to take effect, `pixi run clean` and build again.

## What to edit, in order

The split is deliberate: **`main.tex` holds every style and layout setting,
`ntusetup.tex` holds nothing but personal data.**

| Step | File | What goes in it |
| --- | --- | --- |
| 1 | `ntusetup.tex` | Title, author, student ID, advisor, department, keywords, DOI, email, ORCID, and the oral examination committee. The only place personal data belongs. |
| 2 | `main.tex` | Class options, the verification-letter path, package loading, and the bibliography style. |
| 3 | `front/abstract.tex` | Chinese and English abstracts, three pages each at most. |
| 4 | `front/acknowledgement.tex` | 謝辭, optional, one page at most. |
| 5 | `front/denotation.tex` | Symbol list. Ships one example per broad field — keep what fits, delete the rest. |
| 6 | `contents/chapter0*.tex` | Your chapters. Chapter 2 is a live demo of every feature; delete it when you no longer need it. |
| 7 | `back/references.bib` | Your references. Ships one worked example per biblatex entry type. |
| 8 | `main.tex` | **Delete the `\nocite{*}` line** — it exists only so the example bibliography prints in full. |
| 9 | `back/appendix0*.tex` | Appendices, or comment out their `\input` lines in `main.tex`. |

Two things to know about the names in `ntusetup.tex`:

- `college` and `institute`, and the English `college*` and `institute*`, must
  all be names NTU publishes, with `college` and `college*` the published pair
  for one college and each institute listed under the college of its own
  language. A name that is not on the list is a warning while you are writing
  and an error when you generate the TDR upload script. If NTU has reorganised
  a college since this template was last updated, `pixi run units` refreshes
  the list it is checked against.
- English unit names containing `&` — 98 of them do — must be written `\&`,
  exactly as they would be to typeset on the cover.

## Verification letter (口試委員審定書)

`front/verification-letter.pdf` ships as NTU's **official blank master's form**,
so page `i` is already the document you need to print and get signed. The
doctoral form is included too — point `main.tex` at it:

```latex
\ntusetup{ verificationfile = {front/verification-letter-doctor.pdf} }
```

The `verification` class option chooses the source:

| Value | Behaviour |
| --- | --- |
| `auto` | Use the file when it exists, otherwise typeset a letter. The default. |
| `file` | Always use the file; stop with an error when it is missing. |
| `typeset` | Always typeset, ignoring the file. |

The typeset letter fills in your title, author, ID, and advisor from
`ntusetup.tex` and leaves blank signature rules.

Once the letter is signed, scan it and overwrite `front/verification-letter.pdf`
with the scan. The page number, watermark, and DOI stamp are all drawn on top
of whatever PDF sits there, and the image is scaled to the paper without
distortion. A PDF, PNG, or JPG all work.

Deleting the file entirely falls back to the typeset letter. latexmk notices
the file appearing, but not disappearing, so switching back needs
`pixi run clean && pixi run build`.

## Fonts

`fontset = default` uses **your system's Times New Roman** for English — the
font the format rules name, present on Windows and macOS, and not shipped here
because it is proprietary — together with **全字庫正楷體 TW-Kai**, which is
bundled. `cjkfont = sung` switches the Chinese face to **全字庫正宋體 TW-Sung**.

If Times New Roman is not installed, the build **stops with an error** rather
than quietly substituting a look-alike. Set `fontset = tinos` to use the
bundled, metric-compatible Tinos instead; that combination needs no installed
fonts at all and always compiles, including on Overleaf.

`fontset = template` (your own files in `fonts/`), `fontset = system`
(everything from installed system fonts), and `fontset = overleaf` are also
available. Full details, licences, and where to obtain Times New Roman, 標楷體
and 新細明體 are in [`fonts/README.md`](fonts/README.md).

## NTU format compliance

From 國立臺灣大學碩、博士學位論文格式規範 (112學年度第1學期第1次教務會議通過,
[source](https://www.lib.ntu.edu.tw/doc/cl/THESISSAMPLE.doc)):

> ＊字體：原則上中文以12號楷書（細明體及標楷體為主），英文以12號 Times New
> Roman 打字，中文撰寫以1.5間距，英文則以雙行間距，本文留白上3公分、下2公分、
> 左右各3公分，字體顏色為黑色

The template sets the layout for you: A4 paper, a 12 pt body in 楷書 and Times
New Roman, the 上3 下2 左右3 公分 margins, black body text, the cover at
18/16/14 pt centred, and the order of the front matter. Citation labels, URLs,
and the DOI stamp are colored by default; `grayprint = true` (below) paints
those black as well.

The body is double-spaced, which is what the rules ask of a thesis written in
English. A thesis written in Chinese is asked for 1.5 spacing instead, and that
is not switched for you: change the `\setstretch{1.6}` in `ntuthesis.cls` to
`\setstretch{1.2}`.

The lengths are yours to keep to — 摘要 at three pages and 謝辭 at one — and each
file says so at the top; nothing stops an overlong one from typesetting.

Departments may add their own rules on top of these — check with your 系所.

## Grayscale printing of the text pages

The class colors the citation labels green and the URLs and the per-page DOI
stamp magenta. Printing those pages on a grayscale printer turns the citation
labels into a mid gray that is harder to read than the text around them. The
`grayprint` class option in `main.tex` prepares the PDF for that printer:

```latex
\documentclass[
  grayprint = true,                 % grayprint = true | false
]{ntuthesis}
```

| Element | `grayprint = false` (default) | `grayprint = true` |
| --- | --- | --- |
| Citation labels (`\cite`) | green | the text color |
| URLs and the DOI stamp | magenta | the text color |
| Figures | unchanged | unchanged |

Links stay clickable either way, and figures keep their colors — print those
pages in color.

## Cover page as a separate PDF

NTU asks for the cover (`封面`) as its own file alongside the thesis.
`pixi run cover` reads `main.pdf` and writes `main-cover.pdf`:

```bash
pixi run cover                          # main.pdf -> main-cover.pdf
pixi run cover -- --output front.pdf    # other input, output, or options
```

What you get is page one and nothing else, a small fraction of the whole
thesis's file size, and checked against page one of `main.pdf` before the run
reports success. Like `protect` and `spine`, it is never part of
`pixi run build`.

## Spine artwork (書側)

The bindery letters the spine, and to do that it needs the artwork at the
finished book's exact thickness. `pixi run spine` measures the thesis and
writes an editable ODT and a print-ready PDF for each binding:

```bash
pixi run spine                # main.pdf -> main-spine-{paperback,hardcover}.{odt,pdf}
pixi run spine -- --width 8   # one artwork at a thickness you measured, in mm
pixi run spine -- -o artwork  # write them somewhere else
```

Run it after `pixi run build`. The width is estimated from `main.pdf`'s page
count, assuming 80 磅道林紙 plus the 平裝 cover or the 精裝 board; both bindings
are written every time. Once you have a bound copy in hand, measure it and pass
`--width` for a single artwork at exactly that thickness.

Every word comes from `main.tex` and `ntusetup.tex` — the degree from the class
options, the rest from `\ntusetup`, dated today if you leave `date` commented
out. The layout is the one in NTU's own samples, [THESISSAMPLE.doc][zh] and
[thesissample_en.doc][en], lined up with the cover. A block that would
otherwise run off the artwork is set smaller, and the run reports every size it
had to shrink.

[zh]: https://www.lib.ntu.edu.tw/doc/cl/THESISSAMPLE.doc
[en]: https://www.lib.ntu.edu.tw/doc/CL/thesissample_en.doc

## Submission

`pixi run protect` writes `main-protected.pdf` from `main.pdf`: an empty user
password so it opens without prompting, and an owner password guarding the
permission flags. Printing and accessibility text extraction stay allowed;
copying, editing, annotating, form filling, and page assembly are denied.

```bash
pixi run protect                       # prompts for the owner password twice
pixi run protect -- --output final.pdf # other input, output, or options
```

Submit `main-protected.pdf` and keep the owner password. The password can also
come from `--password` or the `NTU_THESIS_PDF_OWNER_PASSWORD` environment
variable, which is what a non-interactive shell needs. `--encryption` selects
`aes-256` (default), `aes-128`, or `rc4-128` for readers older than Acrobat 9.

`generate_tdr_upload_script.py` builds a copy-ready JavaScript snippet that
fills in NTU's TDR upload form, reading the metadata from `ntusetup.tex`,
`main.tex`, `front/abstract.tex`, `main.toc`, and `main.pdf`. Run it after the
final build. It prompts for anything it cannot infer, including any field still
holding a template placeholder, and refuses to run while the committee still
holds the template's example members.

The generated script fills **both** TDR pages — paste it once on 輸入論文資料 and
again on 設定口試委員名單, and it detects which one is open.

The committee comes from the `\ntucommittee` entries in `ntusetup.tex`, one per
member, each with a Chinese and English name, an email, a 身分, and an optional
ORCID. Nothing typesets them; the signatures on the letter are handwritten.

**The 指導教授 must be first.** TDR offers that 身分 only in its first committee
block, so the entries and the blocks line up only in that order; every entry
after it must be `共同指導教授` or `口試委員`.

## Credits and license

Built on the
[NTU Thesis LaTeX Template](https://github.com/Hsins/NTU-Thesis-LaTeX-Template)
by Hsin-Hsiang Peng (Hsins), with a scanned-verification-letter path, a seal
watermark and DOI stamp, a rootless Pixi build, the `wherelist` environment,
PDF permission locking, and TDR submission tooling added on top.

MIT licensed, like the upstream template. See [`LICENSE`](LICENSE) — it also
records what the MIT terms do *not* cover: the NTU seal, the official
verification-letter forms, and the fonts, none of which belong to this
repository.
