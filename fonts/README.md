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

## Choosing a set

`fontset` in `main.tex`:

| Value | English | Chinese |
| --- | --- | --- |
| `default` | **your system's Times New Roman** | shipped 全字庫 |
| `tinos` | shipped Tinos | shipped 全字庫 |
| `template` | your files in `english/` | your files in `chinese/` |
| `system` | your installed Times New Roman | your installed 標楷體 |
| `overleaf` | Overleaf's built-in fonts | Overleaf's built-in fonts |

`cjkfont` picks which shipped face `default` and `tinos` use: `kai` (楷體, the
default and what the format rules ask for) or `sung` (宋體).

**`default` fails loudly when Times New Roman is missing.** That is deliberate.
`fontconfig` answers a request for Times New Roman with a metric-compatible
substitute — run `fc-match "Times New Roman"` and you may well see Tinos or
Liberation Serif — which produces a PDF that looks right but is set in a font
the rules do not name. Rather than let that pass silently, the class checks
first and stops with a message telling you to install the font or switch to
`fontset = tinos`.

Windows and macOS ship Times New Roman. Most Linux distributions do not; use
`fontset = tinos` there, or install the font yourself.

## Using the exact fonts NTU names

To typeset with real Times New Roman, 標楷體, and 新細明體, put the files here
and set `fontset = template`:

```
fonts/english/Times New Roman.ttf
fonts/english/Times New Roman-Bold.ttf
fonts/english/Times New Roman-Italic.ttf
fonts/english/Times New Roman-BoldItalic.ttf
fonts/chinese/BiauKai.ttf
fonts/chinese/Kaiti-Black.ttf       (optional; used as the CJK bold face)
```

The filenames matter — `ntuthesis.cls` loads them by name through `fontspec`'s
`Path`/`Extension` options, and a missing file is a compile-time error.

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

If the fonts are installed system-wide rather than copied here, use
`fontset = system` instead and `fontspec` resolves them by family name.
