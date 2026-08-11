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

| Step | File | What goes in it |
| --- | --- | --- |
| 1 | `ntusetup.tex` | Title, author, student ID, advisor, department, keywords, DOI, email, ORCID. The only place personal data belongs. |
| 2 | `main.tex` | Degree (`master`/`doctor`), language (`chinese`/`english`), font set. |
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
doctoral form is included too — point the class at it:

```latex
\ntusetup{ verification = {front/verification-letter-doctor.pdf} }
```

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

The template defaults to `fontset = default`, which uses two freely licensed
fonts that ship with every TeX Live, including Overleaf's:

- **TeX Gyre Termes** — metric-compatible with Times New Roman.
- **AR PL KaitiM Big5** — a Big5 楷書 face.

They are loaded by filename, so kpathsea resolves them and the result is
identical on Overleaf and locally. This satisfies the format rule below without
redistributing any proprietary font.

To use literal Times New Roman and 標楷體, see [`fonts/README.md`](fonts/README.md).
Other choices are `fontset = template` (files you drop into `fonts/`),
`fontset = system` (installed system-wide), and `fontset = overleaf`.

Note that `zhlipsum`, used for the Chinese placeholder text, defaults to
simplified Chinese, which a Big5 font cannot set. The template calls it as
`\zhlipsum[1][name=trad]`.

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
| 楷書 + Times New Roman | `fontset` (see above) |
| Cover at 18/16/14 pt, centred | `\makecover` |
| Page order, 摘要 ≤ 3 pages, 謝辭 ≤ 1 page | `main.tex` inclusion order; noted in each file |

Departments may add their own rules on top of these — check with your 系所.

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

## Example figures

The four plots in `figures/` are generated by
`scripts/make_example_figures.py`. The PDFs are committed, so Overleaf never
needs Python; regenerate them with `pixi run figures`.

## Credits

Built on [Hsins/NTU-Thesis](https://github.com/Hsins/NTU-Thesis) by Hsins, with
a scanned-verification-letter path, a seal watermark and DOI stamp, a rootless
Pixi build, the `wherelist` environment, PDF permission locking, and TDR
submission tooling added on top.
