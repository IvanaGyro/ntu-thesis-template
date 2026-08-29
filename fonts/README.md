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

`main.tex` names one Latin face and one CJK face, in four variables under
`\documentclass`, then applies them with `\ntusetfonts`:

```latex
\newcommand{\ntuengfont}{Tinos-Regular.ttf}   % english/, then the system
\newcommand{\ntuengfontoptions}{
  BoldFont       = Tinos-Bold.ttf,
  ItalicFont     = Tinos-Italic.ttf,
  BoldItalicFont = Tinos-BoldItalic.ttf,
}
\newcommand{\ntucjkfont}{TW-Kai-98_1.ttf}     % chinese/, then the system
\newcommand{\ntucjkfontoptions}{}
\ntusetfonts
```

A font variable is looked for in two places, and the first hit wins:

1. **A file** in `english/` (for `\ntuengfont`) or `chinese/` (for
   `\ntucjkfont`), named exactly or with the `.ttf`, `.otf`, or `.ttc`
   extension left off.
2. **A font family installed on the machine**, Overleaf's image included:
   `Times New Roman`, `BiauKai`, `AR PL KaitiM Big5`.

The options variable is passed to `fontspec` untouched, so anything `fontspec`
accepts can go in it.

**Bold and italic depend on which of the two you used.** A family name is
resolved by the operating system's font manager, which knows every weight and
slant that family has, and `fontspec` pairs them up on its own — leave the
options empty. A font file is one face and nothing else, and nothing can guess
which other files sit beside it, so name them yourself:

```latex
\newcommand{\ntuengfontoptions}{
  BoldFont       = Tinos-Bold.ttf,
  ItalicFont     = Tinos-Italic.ttf,
  BoldItalicFont = Tinos-BoldItalic.ttf,
}
```

Leaving them out still compiles; `\textbf` and `\textit` just fall back to the
upright, and LaTeX says so with `Font shape ... undefined`.

The combinations worth knowing:

| What you want | `\ntuengfont` | `\ntucjkfont` |
| --- | --- | --- |
| The default: nothing installed, everything bundled | `Tinos-Regular.ttf` | `TW-Kai-98_1.ttf` |
| The format rules exactly, fonts from your system | `Times New Roman` | `BiauKai` |
| The rules' English face, bundled Chinese | `Times New Roman` | `TW-Kai-98_1.ttf` |
| Your own files dropped in here | `Times New Roman.ttf` | `BiauKai.ttf` |
| Overleaf's built-in Chinese face | — | `AR PL KaitiM Big5` |

Nothing sets a Latin sans or monospaced face; NTU's rules name only the body
face. Add `\setsansfont` and `\setmonofont` to `main.tex` if you want them.

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

The default `\ntuengfont` of `Tinos-Regular.ttf` is a deliberate trade: the template compiles on
a fresh clone anywhere, at the cost of naming a metric-compatible clone rather
than the Times New Roman the rules ask for. Windows and macOS ship Times New
Roman, so write `Times New Roman` there. Most Linux distributions do
not; install it yourself, or keep Tinos and check with your department before
submitting.

## Using the exact fonts NTU names

To typeset with real Times New Roman and 標楷體 without installing them, put the
files here and keep the names in `main.tex` matching:

```
fonts/english/Times New Roman.ttf
fonts/english/Times New Roman Bold.ttf
fonts/english/Times New Roman Italic.ttf
fonts/chinese/BiauKai.ttf
```

```latex
\newcommand{\ntuengfont}{Times New Roman.ttf}
\newcommand{\ntuengfontoptions}{
  BoldFont   = Times New Roman Bold.ttf,
  ItalicFont = Times New Roman Italic.ttf,
}
\newcommand{\ntucjkfont}{BiauKai.ttf}
\newcommand{\ntucjkfontoptions}{}
\ntusetfonts
```

The filenames are yours to choose — whatever you copied them as, write that. The
variables are the only place they are named, so nothing has to be renamed to
match a pattern. With the files in place these names resolve here and never
reach the system, so the same `main.tex` builds on a machine where the fonts are
installed and on one where they are not.

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

If the fonts are installed system-wide rather than copied here, write the family
names instead — `\ntuengfont` as `Times New Roman`, `\ntucjkfont` as `BiauKai`,
with both options variables empty. Nothing matches in `fonts/`, the lookup falls
through to the system's font manager, and that manager supplies the bold and
italic faces itself.
