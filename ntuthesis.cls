% --------------------------------------------------
% 國立臺灣大學碩博士論文模板
% National Taiwan University (NTU) Thesis Template
% --------------------------------------------------
% Version       : 1.0
% Author        : Hsins <hsinspeng@gmail.com>
% Repository    : https://github.com/Hsins/NTU-Thesis
% Document      : https://hsins.github.io/NTU-Thesis/
% Last Updated  : 2020.05.01
%
% This copy has been extended: a scanned verification letter can replace the
% typeset one, the cover carries an optional seal watermark and DOI stamp, and
% the default font set uses freely redistributable Times/Kai clones.

% --------------------------------------------------
% 01 類別宣告（Class Declaration）
% --------------------------------------------------

% 告知編譯器當前的 LaTeX 版本
% Must indicate what's the release of LaTeX we are using.
\NeedsTeXFormat{LaTeX2e}

% 定義類別名稱與敘述
% Define the name and description of class.
\ProvidesClass{ntuthesis}[2020/05/01 v2.0 NTU Thesis Template]

% --------------------------------------------------
% 02 基礎設定（Basic Settings）
% --------------------------------------------------

% [引入套件]
% Include required packages for basic settings.

\RequirePackage{kvdefinekeys, kvsetkeys, kvoptions}
\RequirePackage{iftex}
\RequirePackage{ifthen}

% [定義變數]
% Define essential variables.

% 變數: 路徑
% Variables: Path
\newcommand{\ntu@path@font}{./fonts/english/}
\newcommand{\ntu@path@cjkfont}{./fonts/chinese/}

% 變數: 中文翻譯
% Variables: Translation (Chinese)
\newcommand{\ntu@verificationletter@zh}{口試委員審定書}
\newcommand{\ntu@tableofcontents@zh}{目錄}
\newcommand{\ntu@listoffigures@zh}{圖目錄}
\newcommand{\ntu@listoftables@zh}{表目錄}
\newcommand{\ntu@denotation@zh}{符號列表}
\newcommand{\ntu@bibliography@zh}{參考文獻}
\newcommand{\ntu@acknowledgement@zh}{致謝}
\newcommand{\ntu@abstract@zh}{摘要}
\newcommand{\ntu@keyword@zh}{關鍵字：}
\newcommand{\ntu@kwsymbol@zh}{、}
\newcommand{\ntu@appendix@zh}{附錄}

\newcommand{\ntu@titlechapter@zh}{第\CJKnumber{\thechapter}章}
\newcommand{\ntu@titlechaptertoc@zh}{第\CJKnumber{\thecontentslabel}章}

% 變數: 英文翻譯
% Variables: Translation (English)
\newcommand{\ntu@verificationletter@en}{Verification Letter from the Oral Examination Committee}
\newcommand{\ntu@tableofcontents@en}{Contents}
\newcommand{\ntu@listoffigures@en}{List of Figures}
\newcommand{\ntu@listoftables@en}{List of Tables}
\newcommand{\ntu@denotation@en}{Denotation}
\newcommand{\ntu@bibliography@en}{References}
\newcommand{\ntu@acknowledgement@en}{Acknowledgements}
\newcommand{\ntu@abstract@en}{Abstract}
\newcommand{\ntu@keyword@en}{Keywords:~}
\newcommand{\ntu@kwsymbol@en}{,~}
\newcommand{\ntu@appendix@en}{Appendix}

\newcommand{\ntu@titlechapter@en}{Chapter~\thechapter}
\newcommand{\ntu@titlechaptertoc@en}{Chapter~\thecontentslabel}

% 變數: 版面設定
% Variables: Layouts
\newcommand{\ntu@geometry@main}{top=3cm, bottom=2cm, left=3cm, right=3cm}
\newcommand{\ntu@geometry@cover}{top=3cm, bottom=3cm, left=3cm, right=3cm}

\newcommand{\ntu@tocvspace}{1em}
\newcommand{\ntu@tocchaptersize@zh}{4.5em}
\newcommand{\ntu@tocchaptersize@en}{5.5em}

\newcommand{\ntu@tocsecindent@zh}{1.5em}
\newcommand{\ntu@tocsecnumwidth@zh}{3.0em}
\newcommand{\ntu@tocsubsecindent@zh}{3.0em}
\newcommand{\ntu@tocsubsecnumwidth@zh}{3.0em}

\newcommand{\ntu@tocsecindent@en}{2.5em}
\newcommand{\ntu@tocsecnumwidth@en}{3.0em}
\newcommand{\ntu@tocsubsecindent@en}{3.0em}
\newcommand{\ntu@tocsubsecnumwidth@en}{3.0em}

% [定義命令]
% Define essential commands.

% 命令: 錯誤訊息
% Command: Error and Warning Messages
%
\newcommand{\ntu@error}[1]{
  \ClassError{ntuthesis}{#1}{}
}

\newcommand{\ntu@warning}[1]{
  \ClassWarning{ntuthesis}{#1}
}

% 命令: 鍵值設定
% Command: Key Value Options
%
\SetupKeyvalOptions{
  family=ntu,
  prefix=ntu@,
  setkeys=\kvsetkeys
}

\newcommand{\ntusetup}{
  \kvsetkeys{ntu}
}

\newcommand{\ntu@define@key}[1]{
  \kvsetkeys{ntu@key}{#1}
}

\kv@set@family@handler{ntu@key}{%
  \@namedef{ntu@#1@@name}{#1}%
  \def\ntu@@default{}%
  \def\ntu@@choices{}%
  \kv@define@key{ntu@value}{name}{%
    \@namedef{ntu@#1@@name}{##1}%
  }%
  \kv@define@key{ntu@value}{code}{%
    \@namedef{ntu@#1@@code}{##1}%
  }%
  \@namedef{ntu@#1@@check}{}%
  \@namedef{ntu@#1@@code}{}%
  \@namedef{ntu@#1@@hook}{%
    \expandafter\ifx\csname\@currname.\@currext-h@@k\endcsname\relax
      \@nameuse{ntu@#1@@code}%
    \else
      \AtEndOfClass{%
        \@nameuse{ntu@#1@@code}%
      }%
    \fi
  }%
  \kv@define@key{ntu@value}{choices}{%
    \def\ntu@@choices{##1}%
    \@namedef{ntu@#1@@reset}{}%
    \@namedef{ntu@#1@@check}{%
      \@ifundefined{%
        ifntu@\@nameuse{ntu@#1@@name}@\@nameuse{ntu@\@nameuse{ntu@#1@@name}}%
      }{%
        \ntu@error{Invalid value "#1 = \@nameuse{ntu@\@nameuse{ntu@#1@@name}}"}%
      }%
      \@nameuse{ntu@#1@@reset}%
      \@nameuse{ntu@\@nameuse{ntu@#1@@name}@\@nameuse{ntu@\@nameuse{ntu@#1@@name}}true}%
    }%
  }%
  \kv@define@key{ntu@value}{default}{%
    \def\ntu@@default{##1}%
  }%
  \kvsetkeys{ntu@value}{#2}%
  \@namedef{ntu@\@nameuse{ntu@#1@@name}}{}%
  \kv@set@family@handler{ntu@choice}{%
    \ifx\ntu@@default\@empty
      \def\ntu@@default{##1}%
    \fi
    \expandafter\newif\csname ifntu@\@nameuse{ntu@#1@@name}@##1\endcsname
    \expandafter\g@addto@macro\csname ntu@#1@@reset\endcsname{%
      \@nameuse{ntu@\@nameuse{ntu@#1@@name}@##1false}%
    }%
  }%
  \kvsetkeys@expandafter{ntu@choice}{\ntu@@choices}%
  \expandafter\let\csname ntu@\@nameuse{ntu@#1@@name}\endcsname\ntu@@default
  \expandafter\ifx\csname ntu@\@nameuse{ntu@#1@@name}\endcsname\@empty\else
    \@nameuse{ntu@#1@@check}%
    \@nameuse{ntu@#1@@hook}%
  \fi
  \kv@define@key{ntu}{#1}{%
    \@namedef{ntu@\@nameuse{ntu@#1@@name}}{##1}%
    \@nameuse{ntu@#1@@check}%
    \@nameuse{ntu@#1@@hook}%
  }%
}

\newcommand\ntu@option@hook[2]{
  \expandafter\g@addto@macro\csname ntu@#1@@code\endcsname{#2}
}

% 命令: 鍵值陣列使用
% Command: Retrieve the array value with key-value pair.
%
\newcommand\ntu@clist@use[2]{%
  \def\ntu@@tmp{}%
  \kv@set@family@handler{ntu@clist}{%
    \ifx\ntu@@tmp\@empty
      \def\ntu@@tmp{#2}%
    \else
      #2%
    \fi
    ##1%
  }%
  \kvsetkeys@expandafter{ntu@clist}{#1}%
}

% 命令: 日期格式
% Commands: Data Formating
%
\newcommand{\ntu@format@date}[2]{%
  \edef\ntu@@date{#2}%
  \def\ntu@@process@date##1-##2-##3\@nil{%
    #1{##1}{##2}{##3}%
  }%
  \expandafter\ntu@@process@date\ntu@@date\@nil
}
\newcommand\ntu@date@zh@short[3]{\zhdigits{#1}年\zhnumber{#2}月}
\newcommand\ntu@date@zh@digit[3]{\the\numexpr#1\relax~年~\number#2~月~\number#3~日}
\newcommand\ntu@date@zh@digit@short[3]{\the\numexpr#1-1911\relax~年~\number#2~月}
\newcommand\ntu@date@en@short[3]{\monthname[#2], #1}

\newcommand{\ntu@setgeometry}[1]{\expandafter\newgeometry\expandafter{#1}}

% --------------------------------------------------
% 03 編譯檢查（Compile Checking）
% --------------------------------------------------

\ifXeTeX\else
  \ntu@error{XeLaTeX is required to compile this document.}
\fi

% --------------------------------------------------
% 04 論文設定（Document Configs）
% --------------------------------------------------

% [文檔選項]
% Configs from options
%
\ntu@define@key{
  degree = {
    choices = {
      master,
      doctor,
    },
    default = master,
    name    = degreeset
  },
  language = {
    choices = {
      chinese,
      english,
    },
    default = chinese,
  },
  fontset = {
    choices = {
      default,
      system,
      overleaf,
      template,
    },
    default = default,
  },
  mathfont = {
    choices = {
      default,
      termes,
      stix,
    },
    default = default,
  },
  watermark = {
    choices = {
      true,
      false,
    },
    default = true,
  },
  doi = {
    choices = {
      true,
      false,
    },
    default = true,
  },
}

% [設定檔案]
% Configs from ntusetup.tex
%
\ntu@define@key{
  university = {
    default = {國立臺灣大學},
  },
  university* = {
    default = {National Taiwan University},
    name    = university@en,
  },
  college = {
    default = {工學院},
  },
  college* = {
    default = {College of Engineering},
    name    = college@en,
  },
  institute = {
    default = {工業工程學研究所},
  },
  institute* = {
    default = {Institute of Industrial Engineering},
    name    = institute@en,
  },
  title = {
    default = {論文標題},
  },
  title* = {
    default = {Title},
    name    = title@en,
  },
  author = {
    default = {論文作者},
  },
  author* = {
    default = {Name of author},
    name    = author@en,
  },
  ID = {
    default = {學號},
  },
  advisor = {
    default = {指導教授},
  },
  advisor* = {
    default = {Name of supervisor},
    name    = advisor@en,
  },
  DOI = {
    default = {DOI Number},
  },
  % 下列兩項不會排進論文，只供 generate_tdr_upload_script.py 填寫 TDR 上傳表單。
  % Neither field is typeset; generate_tdr_upload_script.py reads them to fill
  % in the NTU TDR submission form.
  email = {
    default = {Email Address},
  },
  ORCID = {
    default = {0000-0000-0000-0000},
  },
  keywords = {
    default = {關鍵字},
  },
  keywords* = {
    default = {Keywords},
    name    = keywords@en,
  },
  date = {
    default = {\the\year-\two@digits{\month}-\two@digits{\day}},
  },
  oral-date = {
    name    = oraldate,
    default = {\the\year-\two@digits{\month}-\two@digits{\day}},
  },
  % 掃描版口試委員審定書的路徑。檔案存在時，\makeverification 以掃描檔取代
  % 自動排版的審定書；不存在時仍排版空白簽名欄位的版本。
  % Path to the scanned verification letter. When the file exists,
  % \makeverification replaces the typeset letter with the scan.
  verification = {
    name    = verificationscan,
    default = {front/verification-letter.pdf},
  },
}

% --------------------------------------------------
% 06 選項設定（Options Settings）
% --------------------------------------------------

% 繼承類別選項（將未定義的傳給基礎文檔）
% Option Declaration (pass tundefined options to father class)
\DeclareDefaultOption{
  \PassOptionsToClass{\CurrentOption}{report}
}

% 處理選項並載入基礎文檔
% Terminates the options processing and loads the basic class.
\ProcessKeyvalOptions*\relax
\LoadClass[a4paper, 12pt]{report}
\newcommand{\ntumathfont}{\ntu@mathfont}


% 根據設定值賦值變數
% Assign variables according to configs.
\ifthenelse{\equal{\ntu@degreeset}{master}}{
  \newcommand{\ntu@degree}{碩士}
  \newcommand{\ntu@degree@en}{Master's}
  \newcommand{\ntu@type}{論文}
  \newcommand{\ntu@type@en}{Thesis}
}

\ifthenelse{\equal{\ntu@degreeset}{doctor}}{
  \newcommand{\ntu@degree}{博士}
  \newcommand{\ntu@degree@en}{Doctoral}
  \newcommand{\ntu@type}{論文}
  \newcommand{\ntu@type@en}{Dissertation}
}

\ifthenelse{\equal{\ntu@language}{chinese}}{
  % 設定中文
  \newcommand{\ntu@titlechapter}{\ntu@titlechapter@zh}
  \newcommand{\ntu@titlechaptertoc}{\ntu@titlechaptertoc@zh}
  \newcommand{\ntu@tocchaptersize}{\ntu@tocchaptersize@zh}
  \newcommand{\ntu@tocsectionindent}{\ntu@tocsectionindent@zh}
  \newcommand{\ntu@tocsubsectionindent}{\ntu@tocsubsectionindent@zh}
  \newcommand{\ntu@acknowledgement}{\ntu@acknowledgement@zh}
  \newcommand{\ntu@tableofcontents}{\ntu@tableofcontents@zh}
  \newcommand{\ntu@listoffigures}{\ntu@listoffigures@zh}
  \newcommand{\ntu@listoftables}{\ntu@listoftables@zh}
  \newcommand{\ntu@denotation}{\ntu@denotation@zh}
  \newcommand{\ntu@verificationletter}{\ntu@verificationletter@zh}
  \newcommand{\ntu@bibliography}{\ntu@bibliography@zh}
  \newcommand{\ntu@appendix}{\ntu@appendix@zh}

  % 設定單位
  \newcommand{\ntu@tocsecindent}{\ntu@tocsecindent@zh}
  \newcommand{\ntu@tocsecnumwidth}{\ntu@tocsecnumwidth@zh}
  \newcommand{\ntu@tocsubsecindent}{\ntu@tocsubsecindent@zh}
  \newcommand{\ntu@tocsubsecnumwidth}{\ntu@tocsubsecnumwidth@zh}
}

\ifthenelse{\equal{\ntu@language}{english}}{
  % 設定英文
  \newcommand{\ntu@titlechapter}{\ntu@titlechapter@en}
  \newcommand{\ntu@titlechaptertoc}{\ntu@titlechaptertoc@en}
  \newcommand{\ntu@tocchaptersize}{\ntu@tocchaptersize@en}
  \newcommand{\ntu@tocsectionindent}{\ntu@tocsectionindent@en}
  \newcommand{\ntu@tocsubsectionindent}{\ntu@tocsubsectionindent@en}
  \newcommand{\ntu@acknowledgement}{\ntu@acknowledgement@en}
  \newcommand{\ntu@tableofcontents}{\ntu@tableofcontents@en}
  \newcommand{\ntu@listoffigures}{\ntu@listoffigures@en}
  \newcommand{\ntu@listoftables}{\ntu@listoftables@en}
  \newcommand{\ntu@denotation}{\ntu@denotation@en}
  \newcommand{\ntu@verificationletter}{\ntu@verificationletter@en}
  \newcommand{\ntu@bibliography}{\ntu@bibliography@en}
  \newcommand{\ntu@appendix}{\ntu@appendix@en}

  % 設定單位
  \newcommand{\ntu@tocsecindent}{\ntu@tocsecindent@en}
  \newcommand{\ntu@tocsecnumwidth}{\ntu@tocsecnumwidth@en}
  \newcommand{\ntu@tocsubsecindent}{\ntu@tocsubsecindent@en}
  \newcommand{\ntu@tocsubsecnumwidth}{\ntu@tocsubsecnumwidth@en}
}

% --------------------------------------------------
% 07 載入套件 (Include Packages)
% --------------------------------------------------

% [載入套件]
% - ifthen                      條件判斷支持
% - xparse                      定義命令
% - xeCJK                       排版中日韓(CJK)字符
% - indentfirst                 首行縮進
% - fontspec                    設定中英文字體
% - xcolor                      設定顏色
% - geometry                    設定版面大小
% - titlesec                    設定章節格式
% - titletoc, tocloft           設定目錄格式
% - fancyhdr                    設定頁首頁尾
% - ulem, CJKulem               下劃線、雙下劃線與波浪紋效果
% - setspace                    設定行距（標題內文分別設定）
% - graphicx                    插入圖片
% - tikz                        繪圖
% - eso-pic                     插入圖片於文字下方
% - pdfpages                    插入 pdf 檔案
% - tabularx                    插入表格
% - booktabs                    改善表格設置
% - array                       調整表格高度
% - longtable                   支援跨頁長表格
% - diagbox                     插入表格反斜線
% - multirow                    合併儲存格
% - amsmath, amsthm, amssymb    引入 AMS 數學環境
% - datetime                    日期格式轉換
% - CJKnumb                     中文數字轉換
% - fp, calc                    計算功能
% - hyperref                    超連結
% - paralist                    列表環境
% - footmisc                    自訂腳註符號
% - caption, subcaption         插入圖片、表格標題
% - natbib                      參考文獻
%
\RequirePackage{xparse}
\RequirePackage{xeCJK}
\RequirePackage{indentfirst}
\RequirePackage{fix-cm}       % suppress Size substitutions with differences warning
\RequirePackage{fontspec}
\RequirePackage{xcolor}
\RequirePackage{titlesec}
\RequirePackage{titletoc, tocloft}
\RequirePackage{fancyhdr}
\RequirePackage{setspace}
\RequirePackage{graphicx}
\RequirePackage{tikz}
\RequirePackage{eso-pic}
\RequirePackage{pdfpages}
\RequirePackage{tabularx}
\RequirePackage{booktabs}
\RequirePackage{multirow}
\RequirePackage{diagbox}
\RequirePackage{array}
\RequirePackage{longtable}
\RequirePackage{datetime}
\RequirePackage{CJKnumb}
\RequirePackage{fp, calc}
\RequirePackage{hyperref}
\RequirePackage{paralist}
\RequirePackage{footmisc}
\RequirePackage{caption}
\RequirePackage{subcaption}

% --------------------------------------------------
% 10 套件設定 (Package Settings)
% --------------------------------------------------

% [文章排版]
%
\XeTeXlinebreaklocale "zh"
\XeTeXlinebreakskip = 0pt plus 1pt
\setlength{\parskip}{10pt}
\setlength{\parindent}{2em}

% [字體設定]
% - \setmainfont{}          	襯線字體
% - \setsansfont{}          	非襯字體
% - \setmonofont{}          	等寬字體
% - \setCJKmainfont{}			中文襯線字體
% - \setCJKsansfont{}			中文非襯字體
% - \setCJKmonofont{}			中文等寬字體
%

% fontset = default
%
% 臺大格式規範要求「中文以12號楷書、英文以12號 Times New Roman」。標楷體與
% Times New Roman 都是商業字型，不能隨模板散布，因此預設改用兩套可自由散布、
% 且 TeX Live（含 Overleaf）本身就會安裝的替代字型：
%
%   - TeX Gyre Termes：Times 的 metric-compatible 複製品，字寬與 Times 相同。
%   - AR PL KaitiM Big5：文鼎公眾授權的 Big5 楷體。
%
% 兩者都以「檔名」載入，由 kpathsea 在 texmf 樹中尋找，因此不依賴 fontconfig，
% 在 Overleaf 與本機 TinyTeX 的行為完全一致。需要真正的 Times New Roman 與
% 標楷體時改用 fontset = template 或 fontset = system。
%
% The NTU format rules name Times New Roman and 標楷體, both proprietary and so
% not redistributable with a template. The default set instead uses freely
% licensed stand-ins that ship with every TeX Live, including Overleaf's.
% Loading them by filename means kpathsea resolves them and fontconfig is never
% consulted, so local and Overleaf builds agree.
\ifthenelse{\equal{\ntu@fontset}{default}}{
  \setmainfont{texgyretermes-regular.otf}[
    BoldFont       = texgyretermes-bold.otf ,
    ItalicFont     = texgyretermes-italic.otf ,
    BoldItalicFont = texgyretermes-bolditalic.otf, ]
  \setCJKmainfont{bkai00mp.ttf}
  \setCJKmonofont{bkai00mp.ttf}
}

% fontset = system
%
% 字型已安裝在作業系統中時使用，由 fontconfig 以字族名稱解析。
% Resolves the named families through fontconfig; use when the real fonts are
% installed system-wide rather than copied into fonts/.
\ifthenelse{\equal{\ntu@fontset}{system}}{
  \setmainfont{Times New Roman}
  \setCJKmainfont{BiauKai}
  \setCJKmonofont{BiauKai}
}

% fontset = template
%
% 使用者自行放進 fonts/ 的字型檔。檔名必須與下列一致，詳見 fonts/README.md。
% User-supplied font files dropped into fonts/. Filenames must match exactly;
% see fonts/README.md. A missing file is a hard error, which is the point.
\ifthenelse{\equal{\ntu@fontset}{template}}{
  \setmainfont{Times New Roman}[
    Path = \ntu@path@font ,
    Extension = .ttf ,
    BoldFont = *-Bold ,
    ItalicFont = *-Italic ,
    BoldItalicFont = *-BoldItalic, ]
  \setCJKmainfont{BiauKai}[
    Path = \ntu@path@cjkfont ,
    Extension = .ttf ,
    BoldFont = Kaiti-Black, ]
  \setCJKmonofont{BiauKai}[
    Path = \ntu@path@cjkfont ,
    Extension = .ttf ,
    BoldFont = Kaiti-Black, ]
}


% fontset = overleaf
%
% 以字族名稱解析 Overleaf 影像中既有的字型。fontset = default 在 Overleaf 上
% 同樣可用且更可攜，此選項保留給偏好這組字型的使用者。
% Resolves fonts present in Overleaf's image by family name. fontset = default
% also works there and is more portable; this stays for anyone who prefers
% these faces.
\ifthenelse{\equal{\ntu@fontset}{overleaf}}{
  \setmainfont{Times New Roman}
  \setsansfont{Droid Sans}
  \setmonofont{Courier New}
  \setCJKmainfont{AR PL KaitiM Big5}
  \setCJKsansfont{AR PL KaitiM Big5}
  \setCJKmonofont{AR PL KaitiM Big5}
}

% [顏色設定]
%

% [版面大小]
%
\RequirePackage{geometry}
\geometry{
  top=3cm,
  bottom=2cm,
  left=3cm,               % inner=3cm
  right=3cm               % outer=3cm
}

% [連結設定]
%
\hypersetup{
  colorlinks,
  linkcolor=black,
  anchorcolor=blue,
  citecolor=green
}

% [目錄格式]
%
\addtocontents{toc}                                         % 修改目錄樣式
{~\hfill\textbf{Page}\par}
{}
{}
{}

% \titlecontents{標題名稱}[左間距]{標題格式}{標題內容}{無序號標題}{指引線與頁碼}[下間距]
\titlecontents{chapter}[0em]                                % 修改目錄樣式
{\addvspace{0.5em}\normalsize\bfseries\protect}
{\fboxrule=0pt\fboxsep=0pt\framebox[\ntu@tocchaptersize][l]{\ntu@titlechaptertoc}}
{}
{\hfill\contentspage}

\setlength{\cftbeforesecskip}{8pt}                          % 修改目錄間距
\setlength{\cftbeforesubsecskip}{8pt}

\setcounter{tocdepth}{3}                                    % 設定目錄深度
\setcounter{secnumdepth}{3}                                 % 設定編號深度

% \cftsetindents{entry}{indent}{numwidth}
\cftsetindents{section}{\ntu@tocsecindent}{\ntu@tocsecnumwidth}
\cftsetindents{subsection}{\ntu@tocsubsecindent}{\ntu@tocsubsecnumwidth}

% [頁首頁尾]
%

% [標題格式]
% 載入套件包 titlesec 設定各層標題格式
% \titleformat{command}[shape]{format}{label}{sep}{before}[after]
% - command: 代表欲重新定義之標題階層，包含 \part, \chapter, \section, \paragraph
% - shape: 設定段落形狀，可選參數有 hang, block, display
% - format: 定義標題外觀，如：位置、字體大小粗細…
% - label: 定義標籤前綴標號
% - sep: 定義標號與標題內容間隔距離
% - before: 標題內容前增加文字
% - after: 標題內容後增加文字
%
\titleformat{\chapter}                      % 設置 Chapter 格式
{\centering\Huge\bfseries}                  % 定義 format
{\ntu@titlechapter}              		    % 定義 label
{1em}                                       % 定義 sep
{}                                          % before

% [圖表標題]
%
\setlength{\intextsep}{12bp \@plus4pt \@minus2pt}
\captionsetup{}
\captionsetup[table]{position=top,belowskip={12bp-\intextsep},aboveskip=6bp}
\captionsetup[figure]{position=bottom,belowskip={12bp-\intextsep},aboveskip=6bp}
\captionsetup[sub]{skip=6bp}

% --------------------------------------------------
% 08 自訂命令（Custom Commands）
% --------------------------------------------------

% [中文縮進]
% - \Eindent                    縮進
% - \Enoindent                  不縮進
%

% 獲取並定義 CJK 字符寬度
\newcommand{\ntu@CJKChar@size}{\hskip \f@size \p@}
\newdimen{\ntu@CJKChar@size@dimen}
\settowidth{\ntu@CJKChar@size@dimen}{\ntu@CJKChar@size\CJKglue}

% 定義命令
\newcommand{\CJKsetfontspace}{
  \settowidth\ntu@CJKChar@size@dimen{\ntu@CJKChar@size\CJKglue}
  \ifthenelse{\parindent=0pt}{\relax}{\parindent2\ntu@CJKChar@size@dimen}
}

% 縮進
\newcommand{\Eindent}{
  \CJKsetfontspace\parindent2\ntu@CJKChar@size@dimen
}

% 不縮進
\newcommand{\Enoindent}{
  \parident\z@
}

% [插入浮水印]
% - \makewatermark{#1}{#2}      生成浮水印
%   #1 Opacity                  設置透明度
%   #2 Logo Path                校徽路徑
%
\newcommand{\ntu@watermark@opacity}{0.25}
\newcommand{\ntu@watermark@path}{figures/seal-grayscale.pdf}

\newcommand{\makewatermark}[2]{
  \AddToShipoutPictureBG{
    \put(0,0){
      \parbox[b][\paperheight]{\paperwidth}{
        \vfill
        \centering
        \begin{tikzpicture}[remember picture, overlay]
          \coordinate (WM) at ([xshift=-4.325cm, yshift=-4.325cm] current page.north east);
          \node [scale=1] at (WM) {\includegraphics[width=3.65cm, height=3.65cm]{#2}};
          \filldraw [fill=white, opacity=1-\the\numexpr#1] (current page.north east) rectangle (current page.south west);
        \end{tikzpicture}
      \vfill
}}}}

\newcommand{\ntu@makecoverwatermark}[1]{
  \AddToShipoutPictureBG*{
    \begin{tikzpicture}[remember picture, overlay]
      \coordinate (WM) at ([xshift=-4.325cm, yshift=-4.325cm] current page.north east);
      \node [inner sep=0pt] at (WM)
        {\includegraphics[width=3.65cm, height=3.65cm]{#1}};
      \begin{scope}
        \pgfsysprotocol@literal{/ntuCoverWatermarkOpacity gs}
        \path [fill=white, draw=none]
          ([xshift=-1.825cm, yshift=1.825cm] WM) rectangle ([xshift=1.825cm, yshift=-1.825cm] WM);
      \end{scope}
    \end{tikzpicture}
  }
}

\newsavebox{\ntu@watermark@opacitybox}
\newcommand{\ntu@registerwatermarkopacity}[1]{
  \sbox{\ntu@watermark@opacitybox}{
    \begin{tikzpicture}
      \filldraw [opacity=#1] (0,0) rectangle (0,0);
    \end{tikzpicture}
  }
}

\newcommand{\ntu@registercoverwatermarkopacity}[1]{
  \pgfmathparse{1-(#1)}
  \edef\ntu@coverwatermark@resource{
    /ntuCoverWatermarkOpacity << /CA \pgfmathresult\space /ca \pgfmathresult\space >>
  }
  \expandafter\pgfutil@addpdfresource@extgs\expandafter{\ntu@coverwatermark@resource}
}

% [插入前景浮水印]
% - \ntu@makeoverlaywatermark{#1}{#2}   在當前頁的最上層蓋一枚半透明校徽
%   #1 Opacity                          設置透明度
%   #2 Logo Path                        校徽路徑
%
% \makewatermark 把校徽畫在頁面背景，掃描檔不透明的底色會整片蓋掉它，
% 因此鋪滿掃描檔的頁面改用這個命令把校徽補回前景。位置與大小必須與
% \makewatermark 一致，兩者要一起改。
%
% 直接對校徽裡的每一條向量圖形設定透明度，重疊處會重複混色而變深。外層的
% overlay 圖只負責定位；內層有實際邊界的 tikzpicture 讓 PGF 建立隔離的
% transparency group，再對整枚校徽一次套用透明度，因此不會改動底下的掃描件。
%
% Applying opacity directly to the seal's vector paths darkens their overlaps.
% The finite inner picture lets PGF emit one isolated transparency group, so
% opacity is applied once to the complete seal without altering the scan.
% Keep the geometry in sync with \makewatermark.
\newcommand{\ntu@makeoverlaywatermark}[2]{
  \AddToShipoutPictureFG*{
    \begin{tikzpicture}[remember picture, overlay]
      \coordinate (WM) at ([xshift=-4.325cm, yshift=-4.325cm] current page.north east);
      \node [inner sep=0pt] at (WM) {%
        \begin{tikzpicture}
          \begin{scope}[transparency group, opacity=#1]
            \node [inner sep=0pt] at (0,0)
              {\includegraphics[width=3.65cm, height=3.65cm]{#2}};
          \end{scope}
        \end{tikzpicture}%
      };
    \end{tikzpicture}
  }
}

% [鋪滿掃描檔]
% - \ntu@makescanpage{#1}       將掃描檔置中鋪滿當前頁的紙張範圍
%   #1 Scan Path                掃描檔路徑（PDF 取第一頁，亦接受 PNG、JPG）
%
% 掃描檔畫在頁面背景，且 eso-pic 的單頁背景晚於全頁背景輸出，因此掃描檔
% 蓋得住 \makewatermark 的浮水印；頁碼、頁首頁尾與 DOI 屬於頁面內容與前景，
% 仍照常疊在掃描檔之上。
%
% Paint the scan across the whole paper in the page background, so the page
% number and the DOI keep printing on top of it.
\newcommand{\ntu@makescanpage}[1]{
  \AddToShipoutPictureBG*{
    \begin{tikzpicture}[remember picture, overlay]
      \node [inner sep=0pt] at (current page.center)
        {\includegraphics[width=\paperwidth, height=\paperheight, keepaspectratio]{#1}};
    \end{tikzpicture}
  }
}

% [插入數位識別]
% - \InsertDOI{#1}              生成數位識別碼
%   #1 DOI Code                 數位識別碼
%
\newcommand{\insertdoi}[1]{
  \AddToShipoutPictureFG{
    \AtPageUpperLeft{
      \fboxrule=0pt\fboxsep=0pt\framebox[\paperwidth][r]{
      \raisebox{-\paperheight}{
      \put(\LenToUnit{-1cm},\LenToUnit{1cm}){
      \fboxrule=0pt\fboxsep=0pt\framebox[0pt][r]{
        \href{http://dx.doi.org/#1}{doi:#1}
}}}}}}}

% [生成封面]
% Generate the cover page
%
\newcommand{\makecover}{
  \ntu@setgeometry{\ntu@geometry@cover}

  % XeLaTeX must register the opacity resource before the first page ships out.
  \ntu@registerwatermarkopacity{\ntu@watermark@opacity}

  % Match later pages' visible position and opacity; the starred hook limits it to the cover.
  \ifdefined\showcoverseal
    % Use a cover-only opacity resource so later watermark rendering is untouched.
    \ntu@registercoverwatermarkopacity{\ntu@watermark@opacity}
    \ntu@makecoverwatermark{\ntu@watermark@path}
  \fi

  \begin{titlepage}
    \begin{singlespace}
      \begin{center}
        % 中文校系名稱 (18, 27)
        \fontsize{18}{27}\selectfont
        \ntu@university\ntu@college\ntu@institute\par
        \ntu@degree\ntu@type\par

        % 英文系所名稱 (14, 21)
        \fontsize{14}{21}\selectfont
        \ntu@institute@en\par
        \ntu@college@en\par

        % 英文學校名稱 (16, 24)
        \fontsize{16}{24}\selectfont
        \ntu@university@en\par
        \ntu@degree@en~\ntu@type@en\par

        % 中英文論文題目 (18, 27)
        % 中英文作者姓名 (18, 27)
        % 中英文指導教授 (18, 27)
        % 論文撰寫日期   (18, 27)
        \vfill
        \fontsize{18}{27}\selectfont
        \ntu@title\par\ntu@title@en\par
        \vfill
        \ntu@author\par\ntu@author@en\par
        \vfill
        指導教授: \ntu@advisor~博士\par
        Advisor: \ntu@advisor@en~Ph.D.\par
        \vfill
        中華民國~\ntu@format@date{\ntu@date@zh@digit@short}{\ntu@date}\par
        \ntu@format@date{\ntu@date@en@short}{\ntu@date}
      \end{center}
    \end{singlespace}
  \end{titlepage}

  % Start the persistent watermark after the cover so \showcoverseal controls page one.
  \ifthenelse{\equal{\ntu@watermark}{true}}{\makewatermark{\ntu@watermark@opacity}{\ntu@watermark@path}}{}

  % 清除頁碼
  \clearpage
  \restoregeometry
}

% [生成口委審定書]
% Generate the verification letter page
%
% 掃描檔（\ntusetup{verification} 指定的路徑）存在時改放掃描檔，
% 不存在時排版空白簽名欄位的版本。兩者的頁碼、浮水印與 DOI 都相同。
%
% The scan replaces the typeset letter whenever the file exists; both carry the
% same page number, watermark, and DOI.
%
\newcommand{\makeverification}{
  \clearpage
  \phantomsection
  \ntu@setgeometry{\ntu@geometry@main}
  \pagenumbering{roman}
  \addcontentsline{toc}{chapter}{\ntu@verificationletter}
  \IfFileExists{\ntu@verificationscan}
    {\ntu@verification@scanned}
    {
      % 這行訊息與 LaTeX 找不到檔案時印出的格式相同，latexmk 會把它記成缺少的
      % 相依檔案。日後把掃描檔放進來，直接重跑 latexmk 就會改用掃描檔，
      % 不必先 clean。
      % latexmk treats files reported missing this way as dependencies, so
      % dropping the scan in later is enough to trigger a rebuild.
      \typeout{No file \ntu@verificationscan.}
      \ntu@verification@typeset
    }

  % 恢復預設板型
  \restoregeometry
}

% 掃描版：先鋪上掃描檔，再把浮水印補到前景，最後以 \null 讓這一頁真的輸出，
% 頁碼便由當前的頁面樣式照常印出。\clearpage 必須在 \restoregeometry 之前，
% 這一頁才會用審定書的版面設定輸出。
%
% Scanned letter. \null keeps the page non-empty so the page style still prints
% the page number.
\newcommand{\ntu@verification@scanned}{
  \ntu@makescanpage{\ntu@verificationscan}%
  \ifthenelse{\equal{\ntu@watermark}{true}}
    {\ntu@makeoverlaywatermark{\ntu@watermark@opacity}{\ntu@watermark@path}}{}%
  \null
  \clearpage
}

% 自動排版版本
% Typeset letter with blank signature rules.
\newcommand{\ntu@verification@typeset}{
  \begin{singlespace}
    %  口委審定書標題 (24, 36) (26, 39)
    %  論文題目 (20, 30)
    \begin{center}
      \fontsize{24}{36}\selectfont
      {\ntu@university}{\ntu@degree}學位{\ntu@type}\par
      \fontsize{26}{39}\selectfont
      口試委員會審定書\par
      \vfill
      \fontsize{20}{30}\selectfont
      {\ntu@title}\par
      {\ntu@title@en}\par
    \end{center}

    % 口委審定書內容 (16, 24)
    \vfill
    \fontsize{16}{24}\selectfont
    \Eindent
    本論文係{\ntu@author}君（\ntu@ID）在{\ntu@university}{\ntu@institute}完成之{\ntu@degree}學位{\ntu@type}，於{\ntu@format@date{\ntu@date@zh@digit}{\ntu@oraldate}}承下列考試委員審查通過及口試及格，特此證明\par
  \end{singlespace}

  \begin{doublespace}
    % 口委簽名表格 (16, 24)
    \begin{center}
      \vfill
      \fontsize{16}{24}\selectfont
      \begin{tabularx}{\textwidth}{Xl}
        {\hfill}口試委員：{\hfill}& \rule{11.5cm}{1pt}      \\
          & \multicolumn{1}{c}{（指導教授）}                \\
          & \rule{5cm}{1pt}\hspace{1.5cm}\rule{5cm}{1pt}  \\
          & \rule{5cm}{1pt}\hspace{1.5cm}\rule{5cm}{1pt}  \\
          & \rule{5cm}{1pt}\hspace{1.5cm}\rule{5cm}{1pt}  \\
          & \rule{5cm}{1pt}\hspace{1.5cm}\rule{5cm}{1pt}  \\
        所{\hfill}長：{\hfill}& \rule{9cm}{1pt}
      \end{tabularx}
    \end{center}
  \end{doublespace}
}

% [生成目錄]
% Generate table of contents page.
%
\renewcommand{\contentsname}{\centerline{\ntu@tableofcontents}}
\newcommand{\maketableofcontents}{
  \cleardoublepage
  \phantomsection
  \addcontentsline{toc}{chapter}{\ntu@tableofcontents}
  \tableofcontents
}

\renewcommand{\listfigurename}{\centerline{\ntu@listoffigures}}
\newcommand{\makelistoffigures}{
  \cleardoublepage
  \phantomsection
  \addcontentsline{toc}{chapter}{\ntu@listoffigures}
  \listoffigures
}

\renewcommand{\listtablename}{\centerline{\ntu@listoftables}}
\newcommand{\makelistoftables}{
  \cleardoublepage
  \phantomsection
  \addcontentsline{toc}{chapter}{\ntu@listoftables}
  \listoftables
}

% [正文開始]
% \mainmatter
%
\newcommand{\mainmatter}{
  \cleardoublepage
  \ntu@setgeometry{\ntu@geometry@main}
  \pagenumbering{arabic}
  \fontsize{12}{18}\selectfont
}

% [參考文獻]
% \refmatter
%
\newcommand{\refmatter}{
  \cleardoublepage
  \phantomsection
  \renewcommand{\bibname}{\ntu@bibliography}
  \addcontentsline{toc}{chapter}{\ntu@bibliography}
}

% [附錄]
% \appendix{NUM}{TITLE}
%
\renewcommand{\appendix}[2]{
  \chapter*{\ntu@appendix~{#1}~---~#2}
  \phantomsection
  \addcontentsline{toc}{chapter}{\ntu@appendix~{#1}~---~#2}
  \setcounter{section}{0}
  \renewcommand{\thechapter}{#1}
}

% --------------------------------------------------
% 09 自訂環境（Custom Environments）
% --------------------------------------------------

% [符號列表]
% Denotation Environment
%
\newenvironment{denotation}[1][2.5cm]{
\chapter*{\centering \ntu@denotation}
\addcontentsline{toc}{chapter}{\ntu@denotation}
\noindent
\begin{list}{}{
  \renewcommand\makelabel[1]{##1\hfill}
  \setlength{\labelwidth}{#1}                     % 符號欄寬度
  \setlength{\labelsep}{0.5cm}                    % 標籤與列表文字距離
  \setlength{\itemindent}{0cm}                    % 標籤縮進
  \setlength{\leftmargin}{\labelwidth+\labelsep}  % 標籤左邊界
  \setlength{\rightmargin}{0cm}                   % 標籤右邊界
  \setlength{\parsep}{0cm}                        % 段落間距
  \setlength{\itemsep}{18pt}                      % 標籤間距
  \setlength{\listparindent}{0cm}                 % 段落縮進
  \setlength{\topsep}{0pt}                        % 標籤與上文距離
}}{\end{list}}

% [誌謝環境]
% Acknowledgement Environment
%
\newenvironment{acknowledgement}{
  \chapter*{\centering \ntu@acknowledgement}
  \addcontentsline{toc}{chapter}{\ntu@acknowledgement}
  \fontsize{12}{18}\selectfont
}

% [摘要環境]
% Abstract Environment
%
\renewenvironment{abstract}{
  \fontsize{12}{18}\selectfont
  \chapter*{\centering \ntu@abstract@zh}
  \addcontentsline{toc}{chapter}{\ntu@abstract@zh}
}{
  \bigbreak
  \noindent \textbf{\ntu@keyword@zh}
  \ntu@clist@use{\ntu@keywords}{\ntu@kwsymbol@zh}
}

\newenvironment{abstract*}{
  \fontsize{12}{24}\selectfont
  \chapter*{\centering \ntu@abstract@en}
  \addcontentsline{toc}{chapter}{\ntu@abstract@en}
}{
  \bigbreak
  \noindent \textbf{\ntu@keyword@en}
  \ntu@clist@use{\ntu@keywords@en}{\ntu@kwsymbol@en}
}

% --------------------------------------------------
% 10 文檔處理（Document Processing）
% --------------------------------------------------

% 根據設定決定是否添加數位標識
% Insert DOI according to the config.
%
\ifthenelse{\equal{\ntu@doi}{true}}{\insertdoi{\ntu@DOI}}{}

% 設定行距
% 1.2：1.5 倍行距
% 1.6：2.0 倍行距
\setstretch{1.6}

% 中文化
% \newcommand{\loflabel}{圖}
% \newcommand{\lotlabel}{表}
