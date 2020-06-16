" I enable these settings in my .gvimrc
"set columns=120
"set lines=57
" this helps keep / rather than \ in file paths on windows
set shellslash
" I'd rather have vim functionality than vi compatibility
set nocompatible
"in normal mode, <DEL> will actually delete the character!
"nnoremap  x
"in insert mode, <DEL> will actually delete the character!
"inoremap  lxi
"in normal mode, <BS> will actually delete the previous character!
nnoremap  X
"in insert mode, # actually stays where you put itremap  x
inoremap # .#
" allow deletion of autoindents, line ends, and line begins
set backspace=2
" don't create ugly ~ files
set nobackup
" put my highlights and copies into my desktop's default clipboard
set clipboard=unnamed,autoselect
" operations that would normally fail because of unsaved changes e.g. ":q" and ":e",
" instead raise a dialog asking if you wish to save the current file(s)
set confirm
" all tabs are actually spaces
set expandtab
" keep all the files I've opened in memory until I quit
set hidden
" save 9999 each of :... /... and !... commands
set history=9999
" ignore case when searching
set ignorecase
" show me what's matching as I type my search
set incsearch
" always have file status line at bottom, even when there's only one file
set laststatus=2
" make sure SHIFT-motion key actually starts and stops selecting
set keymodel=startsel,stopsel
" add < > to the list of match pairs
set matchpairs+=<:>
" don't take so long showing me the matched pair
set matchtime=2
" uncomment to let my mouse move my vim cursor
"set mouse=a
" show line numbers
set number
" always report when something happens (not just when it happens to more than 2 lines)
set report=0
" show me what line,column my cursor is on
set ruler
" don't let my cursor hit the bottom before scrolling, give me 3 lines of buffer
set scrolloff=3
" jump into select mode (as opposed to visual mode) when highlighting with the mouse
" or SHIFT-motion key (act more like windows select mode)
set selectmode=mouse,key
" like snap-to-grid, only indent/outdent to a multiple of 'shiftwidth'
"set shiftround
" number of characters to shift in normal mode with >> or <<
set shiftwidth=2
" for lines that wrap, line them up with the other lines
" next line obsoleted by 6.0
"set showbreak=\ \ \ \ \ \ \ \\
" show me the command as I work on it
set showcmd
" when a bracket is added, briefly jump to matching bracket
set showmatch
" when my search contains a capital, match case sensitive
set smartcase
" indent and outdent according to { } blocks
set smartindent
set tabstop=2
" set the title that my terminal shows me
set title
" when I'm done, set the title to the hostname of the box
"let &titleold=hostname()
" this is a dummy just so viminfo is set to something
" necessary to get vim to remember commands/searches typed in other sessions
set viminfo='50
" when moving my cursor, wrap in all cases (don't get stuck at end of line, etc)
set whichwrap=b,s,h,l,<,>,[,]
" show me the matches on tab complete
set wildmenu
" make tab completion act like bash, but even better!
set wildmode=longest:list,full
" wrap lines
set wrap
" for now I'm ok with syntax highlighting
syntax on
" don't create ugly ~ files
set writebackup
" highlight matches to my search pattern
set hlsearch
" highlight tabs, trailing spaces, and show > when a line extends without wrapping
set list listchars=tab:>-,trail:_,extends:>
" don't forget for better diff highlighting to add this flag to rxvt startup: -tn rxvt-256color
" in vimdiff this disables syntax highlight in DiffAdd blocks
highlight DiffAdd ctermfg=black
" in vimdiff this sets a readable color for changed text
highlight! link DiffText MatchParen
" when on white, the normal yellow for line numbers sucks, so set it to blue
highlight LineNr ctermfg=4
" when on black, the normal blue for comments sucks, set it to yellow
" highlight Comment ctermfg=3
" nevermind, this does the trick for black background
"set background=dark
set background=light
" when on dark background my white cursor is hard to see on the Yellow 
" Search match highlights, so go pink
"hi Search ctermbg=5
"----- change make so it runs javac when we have java programs being edited
"autocmd BufRead BufNewFile *.java set makeprg=javac\ %
set makeprg=javac\ %
"----- set up the error format for vim, this works for javac
"autocmd BufRead BufNewFile *.java set errorformat=\"%f\"\\\,\ line\ %l.%c:%m\,\ %f:%l:%m
set errorformat=\"%f\"\\\,\ line\ %l.%c:%m\,\ %f:%l:%m
" block cursor under cygwin
let &t_ti.="\e[1 q"
let &t_SI.="\e[5 q"
let &t_EI.="\e[1 q"
let &t_te.="\e[0 q"

" allow me to just hit ^D (ctrl-D) and have it initialize a debugging line for me
""don't clean up filename
map d mawybO0System.out.println("DEBUG: ["%pa] pa=[" + pa + "]");`a
vmap d ymaO0System.out.println("DEBUG: ["%pa] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + pa + "]");`a
imap d O0System.out.println("DEBUG: ["%pa] =[" +  + "]");F=i
""requre filename with path and extension to clean up 
map  mawybO0System.out.println("DEBUG: ["%pT/dT[$F.C] "0pa=[" + "0pa + "]");`a
vmap  ymaO0System.out.println("DEBUG: ["%pT/dT[$F.C] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + "0pa + "]");`a
imap  O0System.out.println("DEBUG: ["%pT/dT[$F.C] =[" +  + "]");F=i
"don't clean up filename
"map d mawybO0logger.log("DEBUG: ["%pa] pa=[" + pa + "]");`a
"vmap d ymaO0logger.log("DEBUG: ["%pa] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + pa + "]");`a
"imap d O0logger.log("DEBUG: ["%pa] =[" +  + "]");F=i
""requre filename with path and extension to clean up 
"map  mawybO0logger.log("DEBUG: ["%pT/dT[$F.C] "0pa=[" + "0pa + "]");`a
"vmap  ymaO0logger.log("DEBUG: ["%pT/dT[$F.C] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + "0pa + "]");`a
"imap  O0logger.log("DEBUG: ["%pT/dT[$F.C] =[" +  + "]");F=i
"don't clean up filename
"map d mawybO0console.log("DEBUG: ["%pa] pa=[" + pa + "]");`a
"vmap d ymaO0console.log("DEBUG: ["%pa] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + pa + "]");`a
"imap d O0console.log("DEBUG: ["%pa] =[" +  + "]");F=i
"requre filename with path and extension to clean up 
"map  mawybO0console.log("DEBUG: ["%pT/dT[$F.C] "0pa=[" + "0pa + "]");`a
"vmap  ymaO0console.log("DEBUG: ["%pT/dT[$F.C] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" + "0pa + "]");`a
"imap  O0console.log("DEBUG: ["%pT/dT[$F.C] =[" +  + "]");F=i
"don't clean up filename
"map d mawybO0let $_ := xdmp:log(concat("DEBUG: ["%pa] pa=[" , pa , "]"))`a
"vmap d ymaO0let $_ := xdmp:log(concat("DEBUG: ["%pa] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" , pa , "]"))`a
"imap d O0let $_ := xdmp:log(concat("DEBUG: ["%pa] =[" ,  , "]"))F=i
""requre filename with path and extension to clean up 
"map  mawybO0let $_ := xdmp:log(concat("DEBUG: ["%pT/dT[$F.C] "0pa=[" , "0pa , "]"))`a
"vmap  ymaO0let $_ := xdmp:log(concat("DEBUG: ["%pT/dT[$F.C] "=substitute(getreg(0), '"', '\\"', 'g')
pa=[" , "0pa , "]"))`a
"imap  O0let $_ := xdmp:log(concat("DEBUG: ["%pT/dT[$F.C] =[" ,  , "]"))F=i
"
"------------------------------
"---------- EXAMPLES ----------
"------------------------------
" use below command to compile something then run it
"------------------------------
":!javac -d WEB-INF/classes/ %;cd WEB-INF/classes/;java `echo %|perl -pe 's/src\/(.*)\.java$/\1/;y/\//./'`
"------------------------------
"
" use below commands to convert xml to sql insert
"------------------------------
"convert <SomeTag into 'INSERT INTO SomeTag ()\n  VALUES ();'
":%s/\([ \t]*\)<\(\w\+\)/\1INSERT INTO \2 ()^M\1  VALUES ();
"get rid of trailing />
":%s/\s*\/>\s*$//
"create first value
":%s/\(INSERT INTO \w\+ (.*\)\()\n[ \t]*VALUES (\)\(\([^;]\|\n\)*\)\();\)[\t\n]*\(\w\+\)="\(\([^"]\|\n\)*\)"/\1\6\2\3'\7'\4\5
"create all other values (run this one over and over until it finds no matches)
":%s/\(INSERT INTO \w\+ (.*\)\()\n[ \t]*VALUES (\)\(\([^;]\|\n\)*\)\();\)[\t\n]*\(\w\+\)="\(\([^"]\|\n\)*\)"/\1, \6\2\3, '\7'\5
"put underscores in table and column names
":%s/\(INSERT INTO.*[A-Za-z_]\+[a-z]\)\([A-Z]\)/\1_\2
"------------------------------
"
"------------------------------
" use below commands to convert sql insert to xml
"------------------------------
"***run once to escape all & signs
"%s/&/\&amp;/g
"***run once to escape all > signs
"%s/>/\&gt;/g
"***run once to escape all < signs
"%s/</\&lt;/g
"***run once to escape all " (double-quotes)
"%s/"/\&quot;/g
"***run once to escape all ' (single-quotes)
"%s/''/\&\#039;/g
"***convert 'INSERT INTO SomeTag ()\n  VALUES ();' into <SomeTag
"%s/insert into\s*/</
"***run once to do initial bumpy-case
"%s/<\(\w\)\([a-z]*\)\(_\(\w\)\([a-z]*\)\)\{0,1}/<\u\1\L\2\u\4\L\5/
"***run multiple times to do remaining element bumpy-cases
"%s/\(<\w\{-}\)_\(\w\)\([a-z]*\)/\1\u\2\L\3/g
"***run multiple times to do all but last attribute
"%s/\(<\w\+ \|" \)\@<=([, ]*\(\w*\)[, ]\+\(.\{-})\)\(\s*\n*\s*VALUES\s*(\)[, ]*\('\(\_[^']\{-}\)'\|\([0-9\.]\+\)\|null\),\s*/\2="\6\7" (\3\4/i
"***run once to do last attribute
"%s/([, ]*\(\w*\)\s*\()\)\(\s*\n*\s*VALUES\s*(\)[, ]*\('\(.\{-}\)'\|\([0-9\.]\+\)\|null\)\s*);*\s*/\1="\5\6"\/>/i
"***run once to do initial attribute bumpy-case
"%s/\([a-z]\)\([a-z]*\)=/\L\1\2=/g
"***run multiple times to do attribute bumpy-cases
"%s/\(\w*\)_\(\w\)\([a-z]*=\)/\L\1\u\2\3/g
"
"*** !!! Only run this if you suspect leftover bad double-quotes
"%s/\(\w\+="[^"]*\)"\(\/>\| \w\+="\)\@!/\1\&quot;/gc
"------------------------------
"
" use below as an example of incrementing a number in a replace
"------------------------------
" :s/\s*public String \(\S*\)/\='  public int ' . toupper(submatch(1)) . '_IDX
" = ' . w:a . ';^M' . ' submatch(0) . (setwinvar(winnr(), "a", (w:a+1)) ? '' : '')
"------------------------------
"
" run command below many times to turn get_variable_name into getVariableName
"------------------------------
" :'<,'>s/\(get[a-zA-Z]*\)_\(\w\)/\1\u\2 
"------------------------------
"
" following aligns equal signs!
"------------------------------
:command! -nargs=1 SetAlignPosition :perl $delimPosition = <args>; VIM::Msg("set \$delimPosition to [$delimPosition]")

:function! AlignFunction(line1, line2, delim)
":  perl VIM::Msg("\$delimPosition is [$delimPosition]")
" next line uses perl to figure out max delimPosition within given range
:  execute(a:line1 . ',' . a:line2 . 'perldo $delim = ' . a:delim .  ';/^(.*?\s?)\s*\Q$delim\E/;&countMe($1);sub countMe() {my $str=shift;$delimPosition = length($str) if ($delimPosition < length($str));};')
":  perl VIM::Msg("set \$delimPosition to [$delimPosition]")
" next line formats lines in range
:  execute(a:line1 . ',' . a:line2 . 'perldo $delim = ' . a:delim . ';$_ =~ s/^(.*?)\s*\Q$delim\E(.*)$/&formatMe($1,$2)/e;sub formatMe() {my $beg=shift;my $end=shift;$delimPosition = length($beg) if ($delimPosition < length($beg));my $spaces = " " x ($delimPosition - length($beg));return "$beg$spaces$delim$end"}')
:  perl $delimPosition = 0
":  perl VIM::Msg("\$delimPosition is [$delimPosition]")
:endfunction

:command! -range -nargs=1 AlignOn :call AlignFunction("<line1>", "<line2>", '<q-args>')

:map <F2> :AlignOn =

":command! -range -nargs=1 AlignOn :<line1>,<line2>perldo $delim = <q-args>;/^(.*?\s?)\s*$delim/;&countMe($1);sub countMe() {my $str=shift;$delimPosition = length($str) if ($delimPosition < length($str));};
":command! -range -nargs=1 AlignOn :<line1>,<line2>perldo $delim = <q-args>;$_ =~ s/^(.*?)\s*$delim(.*)$/&formatMe($1,$2)/e;sub formatMe() {my $beg=shift;my $end=shift;$delimPosition = length($beg) if ($delimPosition < length($beg));my $spaces = ' ' x ($delimPosition - length($beg) + 1);return "$beg$spaces$delim$end"}
"------------------------------

:function! WriteMethods(bang, ...)
:  " get the line number I want to end on
:  let @l=line(".") + 1
:
:  " get dataType and field from args or from prompts
:  if a:0 > 0
:    let dataType=a:1
:  else
:    let dataType=input("dataType: ")
:  endif
:
:  if a:0 > 1
:    let field=a:2
:  else
:    let field=input("field: ")
:  endif
:
:  " get a init-cap version of the field
:  let initCapField=substitute(field, "^.", "\\u\\0", "") 
:  call append(line(".")-1, "    private " . dataType . " " . field . ";")
:
:  " unless they gave me a bang, go to end of class to put getter/setter function
:  if a:bang != "!"
:    " go to the end of the class definition
:    normal ]}
:  endif
:
:  let accessorMethodName = "get" . initCapField
:  if dataType == "boolean"
:    let accessorMethodName = field
:  endif
:  call append(line(".")-1, "")
:  call append(line(".")-1, "    public " . dataType . " " . accessorMethodName . "() {")
:  call append(line(".")-1, "        return " . field . ";")
:  call append(line(".")-1, "    }")
:  call append(line(".")-1, "")
:  call append(line(".")-1, "    public void set" . initCapField . "(" . dataType . " " . field . ") {")
:  call append(line(".")-1, "        this." . field . " = " . field . ";")
:  call append(line(".")-1, "    }")
:  " move the cursur back to where we were
:  @l
:  echo "I have created a " . accessorMethodName . " and a set" . initCapField . " for you, sir!"
:endfunction

:command! -nargs=* -bang Methods :call WriteMethods("<bang>", <f-args>)

" required when matchit.vim is in ~/.vim/plugin/
:filetype plugin on

" make font readable on high-res screens
:set gfn=FixedSys:h11

" sample complex substitution
" '<,'>s#\(\d*\) \(.*\)#\=submatch(1) . printf('	%.1f%%	',str2float(submatch(1)) / 60.30) .  submatch(2)
