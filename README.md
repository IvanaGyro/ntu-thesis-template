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
override that with `NTU_THESIS_TINYTEX_ROOT`. Keep it outside the repository —
`minted` v3's `latexrestricted` refuses to run an executable located below the
document's working directory.

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

Deleting the file entirely makes `\makeverification` fall back to a typeset
letter that fills in your title, author, ID, and advisor from `ntusetup.tex`,
with blank signature rules. latexmk notices the file appearing, but not
disappearing, so switching back needs `pixi run clean && pixi run build`.

<details>
<summary>Where the shipped forms came from</summary>

Both are published by 教務處 at
<https://www.aca.ntu.edu.tw/w/aca/GAADForms>. NTU distributes the doctoral form
as a PDF, which is included unchanged. The master's form is only published as
`碩士審定書.odt` and was converted with LibreOffice:

```bash
soffice --headless --convert-to pdf --outdir front/ 碩士審定書.odt
```

The form asks for 標楷體. If that font is not installed, LibreOffice silently
substitutes a sans-serif face; alias 標楷體 to a 楷書 font such as
`AR PL KaitiM Big5` in `fontconfig` before converting. Re-run this if NTU
revises the form.

</details>

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

Note that `zhlipsum`, used for the Chinese placeholder text, defaults to
simplified Chinese. The template calls it as `\zhlipsum[1][name=trad]`.

## NTU format compliance

From 國立臺灣大學碩、博士學位論文格式規範 (112學年度第1學期第1次教務會議通過,
[source](https://www.lib.ntu.edu.tw/doc/cl/THESISSAMPLE.doc)):

> ＊字體：原則上中文以12號楷書（細明體及標楷體為主），英文以12號 Times New
> Roman 打字，中文撰寫以1.5間距，英文則以雙行間距，本文留白上3公分、下2公分、
> 左右各3公分，字體顏色為黑色

| Requirement | Handled by |
| --- | --- |
| A4, 12 pt body | `\LoadClass[a4paper, 12pt]{report}` |
| Margins 上3 下2 左右3 公分 | `geometry` in `ntuthesis.cls` |
| Line spacing | `\setstretch{1.6}` |
| 楷書 + Times New Roman | `fontset` / `cjkfont` (see above) |
| Cover at 18/16/14 pt, centred | `\makecover` |
| Page order, 摘要 ≤ 3 pages, 謝辭 ≤ 1 page | `main.tex` inclusion order; noted in each file |

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

The text color is `\colorlet{ntu@color@text}{black}` in `ntuthesis.cls`, the one
line to change if the body text ever stops being black. Links stay clickable
either way, and figures keep their colors — print those pages in color.

## Cover page as a separate PDF

NTU asks for the cover (`封面`) as its own file alongside the thesis.
`pixi run cover` reads `main.pdf` and writes `main-cover.pdf`:

```bash
pixi run cover                          # main.pdf -> main-cover.pdf
pixi run cover -- --output front.pdf    # other input, output, or options
```

Copying page one alone leaves the objects that describe a whole thesis
behind: the outline tree, the named destinations, the page labels, the
opening action, and the annotations and links of the copied page. The two
embedded fonts are then rewritten with only the glyphs the cover prints, and
everything left unreferenced is garbage collected, which cuts the cover down
to a small fraction of the whole thesis's file size (the example thesis in
this template goes from 490 kB to about 96 kB).

The script refuses to report success until the cover matches page one of
`main.pdf` in every respect it can measure: page and crop box, rotation, the
rendered pixels at 300 dpi (`--dpi` raises that), the extracted text, every
glyph with its font, size, color, and position, the vector drawings, and the
pixels of every embedded image. Like `protect`, it never runs as part of
`pixi run build`.

## Spine artwork (書側)

The bindery letters the spine, and to do that it needs the artwork at the
finished book's exact thickness. `pixi run spine` measures the thesis and
writes an editable ODT and a print-ready PDF for each binding:

```bash
pixi run spine                          # main.pdf -> main-spine-{paperback,hardcover}.{odt,pdf}
pixi run spine -- --with-cover          # also the spine joined to the cover, to check against
pixi run spine -- --binding hardcover   # one binding only
pixi run spine -- --paperback-width 8   # a 平裝 thickness you measured yourself, in mm
```

### How wide

The width comes from `main.pdf`'s own page count:

| Step | Default | Option |
| --- | --- | --- |
| Printed | one side of the sheet below 80 PDF pages, both from there up | `--sides single \| double` |
| Sheets of paper | one per page, or one per two | |
| Text block | sheets × 0.10 mm, 80 磅道林紙 at 10 條 | `--paper-thickness MM` |
| 平裝 | + 1 mm for the cover and the glue | `--binding-allowance MM` |
| 精裝 | 平裝 + 4 mm of board | |
| Rounding | up to the next whole millimetre | `--paperback-width MM` overrides the lot |

The 4 mm between the two bindings is the gap between NTU's own 8 mm 平裝 and
12 mm 精裝 samples. Once you have a bound copy in hand, measure the **平裝**
one and pass `--paperback-width`; the hardcover always adds its boards to that,
so measure the paperback even when only the hardcover is being written.

### What it says, and how it is set

Every word comes off the cover of `main.pdf` — page one, as the class
typeset it — rather than out of `ntusetup.tex`. The spine therefore says what
the bound book says: the LaTeX has already been rendered, so there is nothing
left to misread, and the two cannot drift apart. The cover runs the
university, the college and the institute together on one line; the spine
takes the first and the last of those, NTU's own list of colleges saying
where each one ends.

The layout follows NTU's official spine form to the row: 國立臺灣大學 and the
institute side by side at the head in 真正直書 (true vertical setting), then
碩士論文 or 博士論文 at 12 pt, the title and 「作者　撰」 at 14 pt, and the ROC
year over the month at the foot. Everything but the year is set vertically,
with the vertical forms of brackets and punctuation and any Latin turned a
quarter turn, the way a vertical line sets it.

The rows are then stretched so the spine's first character starts level with
the cover's first line and its last finishes level with the cover's last,
which is what makes the two faces of the bound book agree. Only the spacing
stretches: the point sizes stay the form's, because those are what the format
rules name. `--no-cover-alignment` keeps the form's own row positions instead.

A long institute name, a long title or a narrow spine makes a block set
smaller rather than run off the artwork, and the run reports every size it had
to shrink. A title long enough to wrap across two lines of the cover is put
back together as one.

### Fonts, and which file to print

Both files carry a subset of the very face `main.pdf` sets Chinese in --
whichever `fontset` and `cjkfont` in `main.tex` selected, found among the
shipped fonts or among the ones installed on this machine, by the PostScript
name the PDF records (標楷體 comes through as `DFKaiShu-SB-Estd-BF`, and a
`.ttc` collection by the index of the face inside it).

A face that forbids embedding is refused outright. One marked print-only is
carried by the PDF, which is what that permission covers; an ODT is a document
that can be edited, and an office suite honours only a face marked installable
there. The 全字庫 faces the template ships may simply be marked so, because
their licences permit a modified version — a face of your own is named in the
ODT instead and left to your machine to supply, and the run says which
happened.

The PDF is drawn rather than converted, so the ODT and the PDF agree without
an office suite in the toolchain: with the 全字庫 faces the template ships,
opening the ODT in LibreOffice puts every character within 0.12 mm of where
the PDF has it. Other faces are laid out identically and print identically
from the PDF, but LibreOffice sets some of them -- 標楷體 among them -- about
one ascent higher on the page, and the run says so. **Print the PDF**; the ODT
is there to be edited.

`pixi run spine -- --with-cover` also writes `<name>-with-cover.pdf`: the
spine joined to the cover on one sheet, 8 mm + 210 mm making a 218 mm page, so
that reading across the join shows at a glance whether the two line up. Like
`cover` and `protect`, none of this runs as part of `pixi run build`.

## Submission

`pixi run protect` writes `main-protected.pdf` from `main.pdf`: an empty user
password so it opens without prompting, and an owner password guarding the
permission flags. Printing and accessibility text extraction stay allowed;
copying, editing, annotating, form filling, and page assembly are denied.

```bash
pixi run protect                       # prompts for the owner password twice
pixi run protect -- --output final.pdf # other input, output, or options
```

It is never run as part of `build`. Submit `main-protected.pdf` and keep the
owner password. The password can also come from `--password` or the
`NTU_THESIS_PDF_OWNER_PASSWORD` environment variable, which is what a
non-interactive shell needs. `--encryption` selects `aes-256` (default),
`aes-128`, or `rc4-128` for readers older than Acrobat 9.

Enabling the accessibility permission only lifts the legal restriction on text
extraction; it does not make the file a tagged PDF. The script warns when the
structure tree is missing, which is the current state of this XeLaTeX build.

`generate_tdr_upload_script.py` builds a copy-ready JavaScript snippet that
fills in NTU's TDR upload form, reading the metadata from `ntusetup.tex`,
`main.tex`, `front/abstract.tex`, `main.toc`, and `main.pdf`. Run it after the
final build. It prompts for anything it cannot infer, including any field still
holding a template placeholder.

The generated script fills **both** TDR pages — paste it once on 輸入論文資料 and
again on 設定口試委員名單, and it detects which one is open.

The committee comes from the `\ntucommittee` entries in `ntusetup.tex`, one per
member, each with a Chinese and English name, an email, a 身分, and an optional
ORCID. Nothing typesets them; the signatures on the letter are handwritten.

**The 指導教授 must be first.** TDR offers that 身分 only in its first committee
block, so the entries and the blocks line up only in that order; every entry
after it must be `共同指導教授` or `口試委員`.

## Checks on your data

Two things are checked against sources rather than taken on trust:

| Checked | While building the PDF | While generating the TDR script |
| --- | --- | --- |
| `college`/`college*` and `institute`/`institute*` are names NTU publishes | warning | error |
| The 身分 order in `\ntucommittee` | warning | error |

The build only warns, because a half-filled `ntusetup.tex` should still produce
a PDF while you are writing. By the time you are generating an upload script the
names are going onto a submission, so the same problems become fatal.

The generator also refuses to run while the committee still holds the
template's example members, since it now types the list straight into TDR.

The official names live in `ntu-academic-units.tex`, which is committed — the
build never goes online. It was generated from
[NTU's list of academic units](https://www.ntu.edu.tw/academics/academics_list.html)
and its [English counterpart](https://www.ntu.edu.tw/english/academics/academics_list.html);
`pixi run units` refreshes it on the rare occasion NTU reorganises a college.
The two pages do not list identical departments, so each language is checked
against its own list rather than paired across languages.

Names containing `&` — 98 of the English ones do — must be written `\&` in
`ntusetup.tex`, exactly as they would be to typeset on the cover.

## Example figures

The four plots in `figures/` are generated by
`scripts/make_example_figures.py`. The PDFs are committed, so Overleaf never
needs Python; regenerate them with `pixi run figures`.

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
