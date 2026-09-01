# AGENTS.md

A LaTeX template for NTU master's theses and doctoral dissertations, published
for other students to start from. Everything in it is example content: there is
no real thesis here, and none should be added.

## Build

XeLaTeX is required (`fontspec`/`xeCJK`; Overleaf uses it too). `minted` needs
shell escape; `biblatex` runs through `biber` (latexmk handles it).

The preferred sudo-free workflow is Pixi plus PyTinyTeX. `build` depends on
`setup`, so a single build command installs or verifies the toolchain and then
compiles:

```bash
pixi run build
pixi run setup     # install TeX packages without building
pixi run doctor    # inspect the installation
pixi run clean     # then rebuild, for stale-state problems
pixi run spine     # write the 書側 artwork (not part of build)
```

TinyTeX installs under `~/.cache/ntu-thesis-template/pytinytex` (override with
`NTU_THESIS_TINYTEX_ROOT`). Keep it outside the repository: `minted` v3's
`latexrestricted` rejects executables located below the document working
directory.

The plain command, when the toolchain is already on `PATH`:

```bash
latexmk -pdf -pdflatex="xelatex -shell-escape -interaction=nonstopmode -file-line-error %O %S" main.tex
```

## Project map

- `main.tex` — every style and layout setting: class options, the
  verification-letter path, package loading, biblatex configuration, and the
  inclusion order. Carries a `\nocite{*}` that exists only to print the example
  bibliography in full, and is marked for deletion by real users.
- `ntusetup.tex` — personal data only: the `\ntusetup` metadata block and the
  `\ntucommittee` entries. Keep style out of it; that split is the point.
- `ntuthesis.cls` — the class. Cover, verification letter, watermark, DOI
  stamp, front-matter environments, and font configuration.
- `environments.tex` — the `wherelist` environment.
- `front/` — abstract, acknowledgement, denotation, and the two official
  verification-letter PDFs (blank master's and doctoral forms from 教務處).
- `contents/chapter01.tex` — Introduction; demonstrates chapter cross-references.
- `contents/chapter02.tex` — a live demo of every feature: equations,
  `wherelist`, figures, sub-figures, `booktabs`, `minted`, all citation forms.
- `contents/chapter03-05.tex`, `back/appendix0*.tex` — skeletons.
- `back/references.bib` — one worked example per biblatex entry type, subjects
  rotated across eight broad fields.
- `figures/` — `seal*.pdf` used by the class; `example-*.pdf` shown in
  `contents/chapter02.tex`.
- `scripts/` — `tex_toolchain.py` (TinyTeX), `protect_pdf.py` (submission
  locking), `extract_cover.py` (cover-page extraction), `make_spine.py` (書側
  artwork), `generate_line_spacing.py` (font metrics), and `thesis_metadata.py`
  (the shared reader for main.tex and ntusetup.tex).
- `ntu-line-spacing.tex` — generated line-spacing values for configured fonts
  that are not precomputed; `pixi run line-spacing` writes it.
- `generate_tdr_upload_script.py`, `tdr_upload_template.js` — NTU TDR form
  filler.

## Editing rules

- This is a template. Example prose can be rewritten freely — unlike a real
  thesis, there is no author whose voice needs preserving.
- Keep placeholder content obviously fake. Author is Stitch / 史迪奇, advisor is
  Lilo / 莉蘿, ID is `R12345678`, DOI is `DOI Number`. Bibliography entries use
  invented authors and journals such as "Journal of Example Medicine" so that
  nothing can be mistaken for a real citation, or leak into a user's own
  bibliography unnoticed.
- Never commit a real signed verification letter, a real DOI, a real student
  ID, or a real acknowledgement.
- Never commit proprietary font files. This fork deliberately does not ship
  Times New Roman or 標楷體.
- MIT licensed, derived from
  [Hsins/NTU-Thesis-LaTeX-Template](https://github.com/Hsins/NTU-Thesis-LaTeX-Template)
  (MIT, © 2017 Hsin-Hsiang Peng). MIT requires that copyright notice to travel
  with the work, so `LICENSE` must keep both copyright lines.
- Comments for user-editable settings are bilingual, Chinese first;
  implementation comments are English. Keep them to use and non-obvious
  constraints, not design rationale.
- Keep the README's user-facing overview in sync with changes to user-editable
  configuration.

## Constraints worth remembering

- `front/abstract.tex` calls `\zhlipsum[1][name=trad]`; the package default is
  simplified Chinese, which a traditional-only CJK face cannot set.
- Set fonts with `\ntufontsetup` in `main.tex`, below `\documentclass`.
- `fonts/` is ~72 MB, almost all of it the two 全字庫 TTFs. Adding the `Ext-B`
  or `Plus` variants would roughly double that for characters a thesis will not
  use.
- `\makeverification` picks its source from the `verification` class option
  (`auto`/`file`/`typeset`) and its path from `\ntusetup{verificationfile}`.
  All three paths must keep the same page number, watermark, and DOI stamp.
- `\ntucommittee` typesets nothing. It exists so
  `generate_tdr_upload_script.py` can read the committee; the letter's
  signatures are handwritten. TDR offers 指導教授 only in its first committee
  block, so that entry must lead the list.
- The same rules are enforced twice on purpose: `ntuthesis.cls` only *warns*
  about a bad 身分 order or an unpublished college/institute, so a half-filled
  `ntusetup.tex` still builds, while `generate_tdr_upload_script.py` raises on
  them, because by then the names are going onto a submission. Keep both sides
  in step when changing either.
- `ntu-academic-units.tex` is committed and is what both validators read; the
  build never fetches anything. `scripts/fetch_academic_units.py`
  (`pixi run units`) regenerates it from NTU's published lists on the rare
  occasion they change. College names are bilingual pairs; unit names are
  registered under the college of their own language, because the two pages do
  not list identical departments — pairing them by position attaches the wrong
  translation. Equal counts do not prove equal order, so the script prints any
  change to the college pairing for a human to confirm.
- 98 of the unit names contain `&`, which `ntusetup.tex` has to spell `\&` for
  the cover to typeset. `\&` is a macro, and expanding it while building a
  control sequence name raises `Missing \endcsname` and kills the build, so the
  data file stores the escaped form and both sides of every lookup are
  `\detokenize`d. Note the declarations receive literal text while the checks
  receive macros: `\detokenize{#1}` for the former, `\expandafter\detokenize
  \expandafter{#1}` for the latter. Mixing them makes the key the literal string
  `\ntu@college`, and every check then passes silently.
- The class reads the data file inside `\makeatletter` at `\AtBeginDocument`,
  since `@` is not a letter there.
- `\ntucommittee` parses with `\setkeys*`, so an unknown key is kept rather than
  raising. A typo like `titel` must not stop a thesis from compiling.
- The TDR selectors in `tdr_upload_template.js` were read off the real
  「設定口試委員名單」page. Field names repeat once per member, so every lookup is
  scoped to its own `.advisor_layout` block — never `document.querySelector` or
  an id.
- The seal is drawn twice by design: `\makewatermark` paints it into every
  page's background, and `\ntu@makeoverlaywatermark` repaints it in the
  foreground of the verification page, where an opaque scan would otherwise
  hide it. That only stays correct because `\ntu@makescanpage` fills the page
  white first — the official forms are vector PDFs with no background of their
  own, and without the fill both copies show through at
  `1-(1-0.25)^2 = 0.4375` instead of `0.25`. Removing the fill silently
  darkens page `i` alone. Verify by rendering page `i` and a body page and
  differencing each against a `watermark=false` build; both seals must reach
  the same peak ink.
- `scripts/thesis_metadata.py` is the one reader of `main.tex` and
  `ntusetup.tex`; the spine, line-spacing generator, and TDR filler all go
  through it, so a change to how a value is written is a change in one place.
- When changing font resolution, keep `ntuthesis.cls`,
  `scripts/generate_line_spacing.py`, and `scripts/make_spine.py` aligned.
- The spine stretches its rows between two hard-coded points, `COVER_TOP_PT`
  and `COVER_BOTTOM_PT`, where `\makecover`'s fixed 3 cm margins and its
  `\vfill`s put the cover's first and last lines. Changing
  `\ntu@geometry@cover`, or the cover's 18 pt on 27 pt body, changes those two
  numbers in `scripts/make_spine.py`.
- Line spacing goes through `\setstretch` only. The body follows `language`,
  each abstract follows its own language, and `\makecover` stays inside
  `singlespace` so the spine coordinates do not move.
- NTU's format rules (fonts, 12 pt, margins 3/2/3/3, spacing, cover sizes) are
  quoted with their source in `README.md`. Verify against
  <https://www.lib.ntu.edu.tw/doc/cl/THESISSAMPLE.doc> before changing layout.

## Verifying a change

A build that merely exits 0 is not enough — XeLaTeX reports these as warnings:

```bash
pixi run clean && pixi run build
grep -c "Missing character" main.log                     # must be 0
grep -cE "Reference .* undefined|Citation .* undefined" main.log   # must be 0
```

Then confirm the bibliography still prints all entries, the four example
figures appear with working sub-references, the denotation list renders, and
page `i` still carries the verification letter with the watermark and DOI on
top. Building once with `language=chinese` is worth doing whenever fonts or the
front matter change.
