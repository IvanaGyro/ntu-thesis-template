% --------------------------------------------------
% 國立臺灣大學碩博士論文模板
% National Taiwan University (NTU) Thesis Template
% --------------------------------------------------
% Version       : 1.0
% Author        : Hsins <hsinspeng@gmail.com>
% Repository    : https://github.com/Hsins/NTU-Thesis-LaTeX-Template
% Document      : https://hsins.github.io/NTU-Thesis/
% Last Updated  : 2020.05.01
% License       : MIT, Copyright (c) 2017 Hsin-Hsiang Peng — see LICENSE
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

% 隨模板散布的中文字型檔名。全字庫字型由數位發展部釋出，授權為
% 「政府資料開放授權條款－第1版」或 OFL-1.1，可自由散布。
% Shipped CJK font filenames. The 全字庫 fonts are released by 數位發展部 under
% the Open Government Data License v1 or OFL-1.1, so they can be redistributed.
\newcommand{\ntu@cjkfont@kai}{TW-Kai-98_1.ttf}
\newcommand{\ntu@cjkfont@sung}{TW-Sung-98_1.ttf}

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
      tinos,
      system,
      overleaf,
      template,
    },
    default = default,
  },
  cjkfont = {
    choices = {
      kai,
      sung,
    },
    default = kai,
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
  % 封面校徽。內頁浮水印由 watermark 控制，封面另外分開，草稿時可單獨關掉。
  % The cover seal, kept separate from the body watermark so a draft can drop
  % it on its own.
  coverseal = {
    choices = {
      true,
      false,
    },
    default = true,
  },
  % 審定書來源：auto 為有檔案就用檔案、沒有就自動排版；file 強制使用檔案，
  % 找不到就報錯；typeset 一律自動排版，忽略檔案。
  % Where the verification letter comes from: auto uses the file when it exists
  % and typesets one when it does not, file insists on the file and errors when
  % it is missing, typeset always sets its own and ignores the file.
  verification = {
    choices = {
      auto,
      file,
      typeset,
    },
    default = auto,
  },
  doi = {
    choices = {
      true,
      false,
    },
    default = true,
  },
  % 灰階列印：引用編號、網址與 DOI 改用內文顏色，供非圖片頁面以灰階印表機列印。
  % Grayscale printing: paint the citation labels, URLs, and DOI in the body
  % text color, for printing the non-picture pages on a grayscale printer.
  grayprint = {
    choices = {
      true,
      false,
    },
    default = false,
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
  % 審定書 PDF 的路徑，是否採用由類別選項 verification 決定。
  % Path to the verification letter PDF; the class option `verification`
  % decides whether it is used.
  verificationfile = {
    name    = verificationscan,
    default = {front/verification-letter.pdf},
  },
}

% [口試委員名單]
% - \ntucommittee{name = ..., name* = ..., email = ..., title = ..., ORCID = ...}
%
% 這個命令不排版任何東西。名單只給 generate_tdr_upload_script.py 讀取，用來填
% 寫 TDR 上傳表單的口試委員欄位；審定書上的簽名由委員親筆簽署，不由模板排版。
% 每位委員呼叫一次，順序即為表單上的順序。
%
% Typesets nothing. The list exists only for
% generate_tdr_upload_script.py, which reads it to fill in the TDR submission
% form; the signatures on the letter itself are handwritten. Call it once per
% member, in the order they should appear.
%
% 這裡只檢查身分（title）並發出警告，不中斷編譯：寫論文的過程中名單常常還沒
% 定案，不該因此排不出 PDF。真正把關的是 generate_tdr_upload_script.py，
% 它在產生上傳腳本時會直接報錯。
%
% Only the 身分 is checked here, and only as a warning: the list is often still
% unsettled while the thesis is being written, and that should not stop a PDF
% from building. generate_tdr_upload_script.py enforces the same rules as hard
% errors when it generates the upload script.
% \setkeys 的星號版本會把不認識的鍵留著而不報錯。少打一個字母（titel）或多加
% 一個只給產生器用的欄位，都不該讓論文編不出來——這裡只負責警告，真正的把關在
% generate_tdr_upload_script.py。
% The starred \setkeys keeps unknown keys instead of raising an error. A typo
% such as titel, or an extra field meant only for the generator, must not stop a
% thesis from compiling: this file only warns, and
% generate_tdr_upload_script.py is what enforces the rules.
\RequirePackage{xkeyval}
\define@key{ntu@cmt}{name}{}
\define@key{ntu@cmt}{name*}{}
\define@key{ntu@cmt}{email}{}
\define@key{ntu@cmt}{ORCID}{}
\define@key{ntu@cmt}{title}{\def\ntu@cmt@title{#1}}

\newcounter{ntu@cmt@count}
\newcommand{\ntucommittee}[1]{%
  \def\ntu@cmt@title{}%
  \setkeys*{ntu@cmt}{#1}%
  \stepcounter{ntu@cmt@count}%
  % TDR 只在第一個委員區塊提供「指導教授」，因此指導教授必須排在第一位。
  % TDR offers 指導教授 only in its first committee block, so the advisor has to
  % lead the list for the blocks and the entries to line up.
  \ifnum\value{ntu@cmt@count}=1
    \ifthenelse{\equal{\ntu@cmt@title}{指導教授}}{}{%
      \ntu@warning{%
        The first \string\ntucommittee\space entry is
        '\ntu@cmt@title', but it must be the 指導教授%
      }%
    }%
  \else
    \ifthenelse{\equal{\ntu@cmt@title}{共同指導教授}
            \OR \equal{\ntu@cmt@title}{口試委員}}{}{%
      \ntu@warning{%
        \string\ntucommittee\space entry \arabic{ntu@cmt@count} is
        '\ntu@cmt@title'; after the first it must be
        共同指導教授 or 口試委員%
      }%
    }%
  \fi
}

% [學術單位檢查]
% Academic unit checks
%
% ntu-academic-units.tex 由 scripts/fetch_academic_units.py 從臺大公布的
% 「學術單位一覽」產生。院名的中英文成對登記，系所名則各自登記在同語言的院名
% 之下——兩個頁面列出的系所並不完全一致，硬要配對反而會配錯。
% 檔案不存在時就跳過檢查，模板照樣編得出來。
%
% ntu-academic-units.tex is generated by scripts/fetch_academic_units.py from
% NTU's published list. College names are registered as bilingual pairs; unit
% names are registered under the college of their own language, because the two
% pages do not list identical units and pairing them would attach the wrong
% translation. The checks are skipped when the file is absent, so the template
% still builds without it.
% 單位名稱裡有 98 個含有 &（例如 College of Electrical Engineering \& Computer
% Science）。使用者在 ntusetup.tex 必須寫成 \&，否則封面排不出來；但 \& 是個巨集，
% 直接放進 \csname 會被展開而報 Missing \endcsname，整份論文就編不出來。
% 因此鍵值兩邊都先 \detokenize 成字元再比對，比的是使用者實際打的字面文字。
%
% 98 of the unit names contain an ampersand. Written into ntusetup.tex it has to
% be \&, or the cover will not typeset — but \& is a macro, and expanding it
% while building a control sequence name raises Missing \endcsname and takes the
% whole document down. Both sides are therefore detokenized into characters
% first, so the comparison is over the text as typed.
% 資料檔傳進來的是字面文字，檢查時傳進來的是巨集（\ntu@college 等），兩者取得
% 字串的方式不同：前者直接 \detokenize，後者要先展開一層。混用會讓鍵值變成
% 「\ntu@college」這串字，檢查便永遠通過。
%
% The declarations receive literal text while the checks receive macros
% (\ntu@college and friends), so they need different expansion: detokenize the
% literal directly, expand the macro once first. Mixing them up turns the key
% into the string "\ntu@college" and every check silently passes.
\newcommand{\ntu@setflag}{%
  \expandafter\global\expandafter\let\csname\ntu@unit@key\endcsname\@empty
}
\newcommand{\ntu@literalkey}[3]{%
  \edef\ntu@unit@key{#1>\detokenize{#2}>\detokenize{#3}}%
}
\newcommand{\ntu@macrokey}[2]{%
  \edef\ntu@unit@key{#1>\expandafter\detokenize\expandafter{#2}}%
}
\newcommand{\ntu@macrokeyii}[3]{%
  \edef\ntu@unit@key{%
    #1>\expandafter\detokenize\expandafter{#2}%
      >\expandafter\detokenize\expandafter{#3}%
  }%
}

\newcommand{\ntu@declarecollege}[2]{%
  \ntu@literalkey{ntu@college}{#1}{#2}\ntu@setflag
  \edef\ntu@unit@key{ntu@collegename>\detokenize{#1}}\ntu@setflag
  \edef\ntu@unit@key{ntu@collegename>\detokenize{#2}}\ntu@setflag
}
\newcommand{\ntu@declareinstitute}[2]{%
  \ntu@literalkey{ntu@institute}{#1}{#2}\ntu@setflag
}

\newcommand{\ntu@checkunit}[3]{%
  \ntu@macrokeyii{ntu@institute}{#1}{#2}%
  \expandafter\ifcsname\ntu@unit@key\endcsname\else
    \ntu@macrokey{ntu@collegename}{#1}%
    \expandafter\ifcsname\ntu@unit@key\endcsname
      \ntu@warning{%
        institute#3 '#2' is not listed under '#1' in NTU's academic
        units\MessageBreak
        See ntu-academic-units.tex%
      }%
    \fi
  \fi
}

\newcommand{\ntu@checkunits}{%
  \IfFileExists{ntu-academic-units.tex}{%
    % 這個檢查在 \AtBeginDocument 執行，此時 @ 已不是字母，資料檔裡的
    % \ntu@declare... 會被拆開，因此要自行切回 letter catcode。
    % This runs at \AtBeginDocument, where @ is no longer a letter, so the data
    % file's \ntu@declare... macros would not parse without switching it back.
    \makeatletter
    \input{ntu-academic-units}%
    \makeatother
    \ntu@macrokeyii{ntu@college}{\ntu@college}{\ntu@college@en}%
    \expandafter\ifcsname\ntu@unit@key\endcsname\else
      \ntu@warning{%
        college '\ntu@college' and college* '\ntu@college@en' are not a
        college pair in NTU's academic units\MessageBreak
        See ntu-academic-units.tex%
      }%
    \fi
    \ntu@checkunit{\ntu@college}{\ntu@institute}{}%
    \ntu@checkunit{\ntu@college@en}{\ntu@institute@en}{*}%
  }{}%
}
\AtBeginDocument{\ntu@checkunits}

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

% 由 cjkfont 選項決定隨附的中文字型：kai 為全字庫正楷體，sung 為全字庫正宋體。
% 臺大格式規範寫的是「中文以12號楷書（細明體及標楷體為主）」，因此預設楷體。
% cjkfont picks the shipped CJK face: kai (楷體, the default) or sung (宋體).
\ifthenelse{\equal{\ntu@cjkfont}{sung}}
  {\newcommand{\ntu@cjkfontfile}{\ntu@cjkfont@sung}}
  {\newcommand{\ntu@cjkfontfile}{\ntu@cjkfont@kai}}

% fontset = default
%
% 英文用系統安裝的 Times New Roman，不隨模板散布字型檔：Times New Roman 是
% Monotype 的商業字型，但 Windows 與 macOS 都內建，多數使用者本來就有。
% 中文用隨附的全字庫字型，以檔名載入，不必另外安裝。
%
% 找不到 Times New Roman 時直接報錯，不會默默改用別的字型。fontconfig 會把
% Times New Roman 對應到 Tinos、Liberation Serif 這類 metric-compatible 的替代
% 字型（本機執行 fc-match "Times New Roman" 即可看到），排出來的 PDF 看起來正常，
% 卻不是格式規範指定的字型。\IfFontExistsTF 不受這種替換影響，會如實回報字型
% 不存在，因此在這裡先檢查再載入。沒有 Times New Roman 的人請改用
% fontset = tinos。
%
% English uses the system's Times New Roman; the file is not shipped because it
% is proprietary but present on Windows and macOS. CJK uses the bundled 全字庫
% face, loaded by filename so nothing has to be installed.
%
% A missing Times New Roman is a hard error rather than a silent substitution.
% fontconfig happily answers a request for Times New Roman with a
% metric-compatible stand-in such as Tinos — run fc-match "Times New Roman" to
% see it — which produces a plausible-looking PDF set in the wrong typeface.
% \IfFontExistsTF is not fooled by that substitution, so the check below is
% what makes the failure visible. Use fontset = tinos when the font is absent.
\ifthenelse{\equal{\ntu@fontset}{default}}{
  \IfFontExistsTF{Times New Roman}{
    \setmainfont{Times New Roman}
  }{
    \ntu@error{%
      fontset=default needs Times New Roman, which is not installed on this
      system.\MessageBreak
      Install it, or switch to fontset=tinos in main.tex to use the bundled
      metric-compatible Tinos instead.\MessageBreak
      See fonts/README.md%
    }
  }
  \setCJKmainfont{\ntu@cjkfontfile}[Path = \ntu@path@cjkfont]
  \setCJKmonofont{\ntu@cjkfontfile}[Path = \ntu@path@cjkfont]
}

% fontset = tinos
%
% 完全使用隨模板散布的字型，不需要系統安裝任何東西，Overleaf 上也一定能編譯。
% Tinos 的字寬與 Times New Roman 相同（metric-compatible），版面配置一致，
% 但字型名稱不是規範所寫的 Times New Roman，正式送印前請確認系所是否接受。
%
% Fully self-contained: every font comes from fonts/, so nothing needs to be
% installed and Overleaf always compiles. Tinos is metric-compatible with Times
% New Roman, so line breaks and page counts match, but it is not literally the
% typeface the format rules name — check with your department before submitting.
\ifthenelse{\equal{\ntu@fontset}{tinos}}{
  \setmainfont{Tinos-Regular.ttf}[
    Path           = \ntu@path@font ,
    BoldFont       = Tinos-Bold.ttf ,
    ItalicFont     = Tinos-Italic.ttf ,
    BoldItalicFont = Tinos-BoldItalic.ttf, ]
  \setCJKmainfont{\ntu@cjkfontfile}[Path = \ntu@path@cjkfont]
  \setCJKmonofont{\ntu@cjkfontfile}[Path = \ntu@path@cjkfont]
}

% fontset = system
%
% 中英文都由作業系統以字族名稱解析，適合已經安裝 Times New Roman 與標楷體的
% 機器。同樣先檢查再載入，避免 fontconfig 默默替換。
% Both scripts resolved from installed system families. Checked before loading,
% for the same reason as fontset=default.
\ifthenelse{\equal{\ntu@fontset}{system}}{
  \IfFontExistsTF{Times New Roman}{
    \setmainfont{Times New Roman}
  }{
    \ntu@error{fontset=system needs Times New Roman installed system-wide}
  }
  \IfFontExistsTF{BiauKai}{
    \setCJKmainfont{BiauKai}
    \setCJKmonofont{BiauKai}
  }{
    \ntu@error{fontset=system needs 標楷體 (BiauKai) installed system-wide}
  }
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
% 內文顏色。連結設定以它為基準，grayprint = true 時把引用編號、網址與 DOI 都塗成
% 這個顏色；改內文顏色時只需要改這一行。
%
% The body text color. The link settings refer to it, so grayprint = true paints
% the citation labels, the URLs, and the DOI in exactly the color the body text
% uses. Changing the body text color means changing this one line.
%
\colorlet{ntu@color@text}{black}

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
% grayprint = false（預設）維持模板原本的顏色：引用編號為綠色，網址與 DOI 為洋紅色
% （magenta，cmyk 0,1,0,0）。
%
% grayprint = true 供灰階列印非圖片頁面使用：引用編號、網址與 DOI 全部改成與內文
% 相同的顏色，避免灰階印表機把綠色與洋紅色印成比內文淺的灰。連結仍然可以點選，
% 圖片顏色也不受影響。
%
% Link colors. With grayprint = false (the default) they stay as the template
% draws them: green citation labels, magenta URLs and DOIs.
%
% grayprint = true is for printing the text pages on a grayscale printer: the
% citation labels, the URLs, and the DOI all take the text color, so a grayscale
% printer cannot render them lighter than the surrounding text. The links stay
% clickable and the figures keep their colors.
%
\ifthenelse{\equal{\ntu@grayprint}{true}}{
  \colorlet{ntu@color@cite}{ntu@color@text}
  \colorlet{ntu@color@url}{ntu@color@text}
}{
  \colorlet{ntu@color@cite}{green}
  \colorlet{ntu@color@url}{magenta}
}

\hypersetup{
  colorlinks,
  linkcolor=ntu@color@text,
  citecolor=ntu@color@cite,
  urlcolor=ntu@color@url
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
      % 先鋪一層不透明白底，再放審定書。向量 PDF（例如教務處發布的空白審定書）
      % 不會自己畫背景，少了白底，\makewatermark 畫在頁面背景的校徽會透出來，
      % 與前景 \ntu@makeoverlaywatermark 疊成兩層：0.25 的透明度疊兩次等於
      % 1-(1-0.25)^2 = 0.4375，看起來就比其他頁深。點陣掃描檔本身不透明，
      % 補上白底對它沒有任何影響。keepaspectratio 留下的邊也一併蓋成白色。
      %
      % Vector PDFs (such as the blank forms published by 教務處) paint no
      % background of their own. Without this rectangle the background seal
      % from \makewatermark shows through and compounds with the foreground
      % overlay — two passes at 0.25 give 1-(1-0.25)^2 = 0.4375 — leaving this
      % page's watermark visibly darker than every other page. Raster scans are
      % opaque, so this is a no-op for them. It also whitens the letterbox
      % margins keepaspectratio may leave.
      \fill [white] (current page.south west) rectangle (current page.north east);
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
  \ifthenelse{\equal{\ntu@coverseal}{true}}{
    % Use a cover-only opacity resource so later watermark rendering is untouched.
    \ntu@registercoverwatermarkopacity{\ntu@watermark@opacity}
    \ntu@makecoverwatermark{\ntu@watermark@path}
  }{}

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
% 來源由類別選項 verification 決定：
%   auto     檔案存在就用檔案，不存在則自動排版（預設）
%   file     一律使用 \ntusetup{verificationfile} 指定的檔案，找不到就報錯
%   typeset  一律自動排版空白簽名欄位的版本，忽略檔案
% 三種來源的頁碼、浮水印與 DOI 都相同。
%
% The class option `verification` picks the source: auto falls back to the
% typeset letter when the file is absent, file insists on the file, typeset
% ignores it. All three carry the same page number, watermark, and DOI.
%
\newcommand{\makeverification}{
  \clearpage
  \phantomsection
  \ntu@setgeometry{\ntu@geometry@main}
  \pagenumbering{roman}
  \addcontentsline{toc}{chapter}{\ntu@verificationletter}
  \ifthenelse{\equal{\ntu@verification}{typeset}}{
    \ntu@verification@typeset
  }{
    \IfFileExists{\ntu@verificationscan}
      {\ntu@verification@scanned}
      {
        \ifthenelse{\equal{\ntu@verification}{file}}{
          \ntu@error{%
            verification=file, but \ntu@verificationscan\space does not
            exist.\MessageBreak
            Put the letter there, correct \string\ntusetup{verificationfile},
            or use verification=auto%
          }
        }{
          % 這行訊息與 LaTeX 找不到檔案時印出的格式相同，latexmk 會把它記成缺少的
          % 相依檔案。日後把掃描檔放進來，直接重跑 latexmk 就會改用掃描檔，
          % 不必先 clean。
          % latexmk treats files reported missing this way as dependencies, so
          % dropping the scan in later is enough to trigger a rebuild.
          \typeout{No file \ntu@verificationscan.}
          \ntu@verification@typeset
        }
      }
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
