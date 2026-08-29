# Fonts

NTU's format rules ask for 12 pt 楷書 for Chinese and 12 pt Times New Roman for
English. This directory holds what the template can legally redistribute; the
rest comes from your system.

## What ships here

| File | Font | Copyright | Licence |
| --- | --- | --- | --- |
| `chinese/TW-Kai-98_1.ttf` | 全字庫正楷體 TW-Kai | 數位發展部 | 政府資料開放授權條款－第1版 **or** OFL-1.1 |
| `chinese/TW-Sung-98_1.ttf` | 全字庫正宋體 TW-Sung | 數位發展部 | 政府資料開放授權條款－第1版 **or** OFL-1.1 |
| `english/Tinos-*.ttf` | Tinos (Regular, Bold, Italic, Bold Italic) | Google Inc., designed by Steve Matteson | OFL-1.1 |

Both licences require their terms to travel with the font files, so
[`OFL.txt`](OFL.txt) sits alongside them with the full licence text and the
copyright notices copied verbatim out of the fonts' own metadata. **Keep it
next to the fonts if you redistribute this template**, and keep the fonts
unmodified unless you have read the OFL's renaming clause.

The 全字庫 fonts are published by 數位發展部 at
<https://data.gov.tw/dataset/5961>; only the BMP files are included, not the
`Ext-B` and `Plus` variants, which cover rare planes a thesis will not need.
Tinos is metric-compatible with Times New Roman, so swapping between them does
not reflow the document.

Your own compiled thesis is unaffected by any of this: embedding a subset of a
font in a PDF is normal use, and both licences permit it.

## Naming the two fonts

`main.tex` names one Latin face and one CJK face:

```latex
\ntusetup{
  engfont = {Times New Roman},   % fonts/english/, then the system
  cjkfont = {TW-Kai-98_1.ttf},   % fonts/chinese/, then the system
}
```

Each value is looked for in three places, in order, and the first hit wins:

1. **The exact file** of that name in `english/` (for `engfont`) or `chinese/`
   (for `cjkfont`) — `cjkfont = {TW-Kai-98_1.ttf}` loads that one file and
   nothing else.
2. **A base name** in the same directory: `engfont = {Tinos}` matches
   `Tinos.ttf`, `.otf`, or `.ttc`, with or without a `-Regular` suffix, and
   picks up `Tinos-Bold`, `Tinos-Italic`, and `Tinos-BoldItalic` beside it as
   the bold and italic faces. This is the form to use for a family with several
   styles; naming one file directly gets you that file alone.
3. **A font family installed on the machine**, Overleaf's image included:
   `engfont = {Times New Roman}`, `cjkfont = {BiauKai}`,
   `cjkfont = {AR PL KaitiM Big5}`.

The combinations worth knowing:

| What you want | What to write |
| --- | --- |
| The format rules exactly, fonts from your system | `engfont = {Times New Roman}`, `cjkfont = {BiauKai}` |
| The default: system Times New Roman, bundled Chinese | `engfont = {Times New Roman}`, `cjkfont = {TW-Kai-98_1.ttf}` |
| Nothing installed, everything bundled | `engfont = {Tinos}`, `cjkfont = {TW-Kai-98_1.ttf}` |
| Your own files dropped in here | `engfont = {Times New Roman}`, `cjkfont = {BiauKai}`, with the files named below |
| Overleaf's built-in Chinese face | `cjkfont = {AR PL KaitiM Big5}` |

These two keys replace the old `fontset` class option; a `main.tex` that still
sets it stops with an error naming the pair to write instead. One thing does not
carry over: the old `fontset = overleaf` also set a Latin sans and monospaced
face (Droid Sans, Courier New), and nothing sets those now. Add `\setsansfont`
and `\setmonofont` to `main.tex` if you want them — the body face is the only
one NTU's rules name.

**A font in this directory is found by file, never by family name.** XeTeX asks
the operating system's font manager to resolve a family — fontconfig on Linux,
CoreText on macOS, DirectWrite on Windows — and none of them knows about a
directory inside your project. `OSFONTDIR` does not change that: it extends
kpathsea's *filename* search, so `kpsewhich Tinos-Regular.ttf` finds the file
while `\setmainfont{Tinos}` still does not. Registering this directory with
fontconfig and running `fc-cache` would work, but only on Linux and never on
Overleaf, whereas loading by path behaves identically everywhere.

**A name that matches nothing fails the build.** That is deliberate.
`fontconfig` answers a request for Times New Roman with a metric-compatible
substitute — run `fc-match "Times New Roman"` and you may well see Tinos or
Liberation Serif — which produces a PDF that looks right but is set in a font
the rules do not name. Rather than let that pass silently, the class checks with
`\IfFontExistsTF`, which is not fooled by the substitution, and stops with a
message listing everything it tried.

Windows and macOS ship Times New Roman. Most Linux distributions do not; use
`engfont = {Tinos}` there, or install the font yourself.

## Using the exact fonts NTU names

To typeset with real Times New Roman and 標楷體 without installing them, put the
files here and keep the names in `main.tex` matching:

```
fonts/english/Times New Roman.ttf
fonts/english/Times New Roman-Bold.ttf
fonts/english/Times New Roman-Italic.ttf
fonts/english/Times New Roman-BoldItalic.ttf
fonts/chinese/BiauKai.ttf
fonts/chinese/BiauKai-Bold.ttf      (optional; becomes the CJK bold face)
```

```latex
\ntusetup{
  engfont = {Times New Roman},
  cjkfont = {BiauKai},
}
```

The suffixes are what matter: the upright face is the bare name (or `-Regular`),
and `-Bold`, `-Italic`, and `-BoldItalic` beside it are attached automatically.
A file under any other name is simply not found, so rename rather than hope —
`Kaiti-Black.ttf`, which earlier versions of this template used as the CJK bold
face, has to become `BiauKai-Bold.ttf` to be picked up. With the files in place,
these names resolve here and never reach the system, so the same `main.tex`
builds on a machine where the fonts are installed and on one where they are not.

Where to get them:

- **Times New Roman** — already on Windows (`C:\Windows\Fonts`) and macOS
  (`/System/Library/Fonts/Supplemental`). Copy it from a machine you own.
- **標楷體 (BiauKai/DFKai-SB) and 新細明體 (PMingLiU)** — bundled on Windows,
  and also carried by the upstream template this one is derived from:
  <https://github.com/Hsins/NTU-Thesis-LaTeX-Template/tree/master/fonts>

Both are proprietary — Monotype and DynaComware respectively. They are licensed
to you, not to this repository, so **do not commit them**. `.gitignore` covers
`fonts/**/*.ttf` with an exception only for the freely licensed files listed
above, so an accidental `git add -A` cannot pick them up.

If the fonts are installed system-wide rather than copied here, the same
`engfont = {Times New Roman}`, `cjkfont = {BiauKai}` finds them: nothing matches
in `fonts/`, so the lookup falls through to the system's own font manager.
