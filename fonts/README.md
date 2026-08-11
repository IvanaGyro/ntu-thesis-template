# Optional font drop-in slot

This directory is empty on purpose. The template ships `fontset = default`, which uses two fonts that
come with every TeX Live installation — including Overleaf's — so nothing has to be installed:

| Script | Font | Package |
| --- | --- | --- |
| Latin | TeX Gyre Termes (`texgyretermes-*.otf`) | `tex-gyre` |
| CJK | AR PL KaitiM Big5 (`bkai00mp.ttf`) | `arphic-ttf` |

TeX Gyre Termes is metric-compatible with Times New Roman, and AR PL KaitiM Big5 is a 楷書 face, so the
result satisfies NTU's format rule (中文以12號楷書、英文以12號 Times New Roman) without redistributing
any proprietary font file.

## Using the exact fonts NTU names

If you want literal Times New Roman and 標楷體 — for example because your department asks for them —
drop the files in here and switch `main.tex` to `fontset = template`:

```
fonts/english/Times New Roman.ttf
fonts/english/Times New Roman-Bold.ttf
fonts/english/Times New Roman-Italic.ttf
fonts/english/Times New Roman-BoldItalic.ttf
fonts/chinese/BiauKai.ttf
fonts/chinese/Kaiti-Black.ttf       (optional; used as the CJK bold face)
```

The filenames matter — `ntuthesis.cls` loads them by name through `fontspec`'s `Path`/`Extension`
options. A missing file is a hard error at compile time, which is the intended signal.

Both fonts are proprietary (Monotype and DynaComware respectively). You almost certainly already have
them on Windows or macOS, but they are licensed to you, not to this repository: **do not commit them.**
`.gitignore` covers `fonts/**/*.ttf` so an accidental `git add -A` cannot pick them up.

If the fonts are installed system-wide rather than copied here, use `fontset = system` instead and
fontspec will resolve them by family name.
