" Trac client: A interface to a Trac Wiki Repository
"
" Script Info and Documentation  {{{
"=============================================================================
"    Copyright: Copyright (C) 2008 Michael Brown
"      License: The MIT License
"
"               Permission is hereby granted, free of charge, to any person obtaining
"               a copy of this software and associated documentation files
"               (the "Software"), to deal in the Software without restriction,
"               including without limitation the rights to use, copy, modify,
"               merge, publish, distribute, sublicense, and/or sell copies of the
"               Software, and to permit persons to whom the Software is furnished
"               to do so, subject to the following conditions:
"
"               The above copyright notice and this permission notice shall be included
"               in all copies or substantial portions of the Software.
"
"               THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
"               OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
"               MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"               IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
"               CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
"               TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
"               SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
" Name Of File: trac.vim, trac.py
"  Description: Wiki Client to the Trac Project Manager(trac.edgewall.org)
"   Maintainer: Michael Brown <michael <at> ascetinteractive.com>
" Contributors: Brad Fritz
"  Last Change:
"          URL:
"      Version: 0.3.6
"
"        Usage:
"
"               You must have a working Trac repository version 0.10 or later
"               complete with the xmlrpc plugin and a user with suitable
"               access rights.
"
"               To use the summary view you need to have the Align plugin
"               installed for the layout.
"
"               http://www.vim.org/scripts/script.php?script_id=294
"
"               Fill in the server login details in the config section below.
"
"               Defatult key mappings:
"
"               <leader>to : Opens the Trac wiki view
"               <leader>tq : Closes the Trac wiki View
"               <leader>tw : Writes the Current Wiki Page (Uses default update
"               Comment)
"
"               or
"
"               :TServer <server name   - Sets the current trac Server
"               (use tab complete)
"               :TClose             - Close VimTrac to the normal View
"
"               """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"
"               Trac Wiki Commands
"
"               :TWOpen <WikiPage>    - Open the wiki View
"               :TWSave "<Comment>"   - Saves the Active Wiki Page
"
"               In the Wiki TOC View Pages can be loaded by hitting <enter>
"
"               In the Wiki View Window a Page Will go to the wiki page if
"               you hit ctrl+] but will throw an error if you arent on a
"               proper link.
"
"               Wikis can now be saved with :w and :wq.
"               In all Trac windows :q will return to the normal view
"
"               Wiki Syntax will work with this wiki syntax file
"               http://www.vim.org/scripts/script.php?script_id=725
"
"               """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"
"               Trac Ticket Commands
"
"               :TTOpen <Ticket ID> - Open Trac Ticket Browser
"
"               Trac current ticket option modifications (use tab complete)
"
"               :TTSetMilestone <Milestone>
"               :TTSetType <Type
"               :TTSetStatus <Status>
"               :TTSetResolution <Resolution>
"               :TTSetPriority <Priority >
"               :TTSetSeverity <Severity >
"               :TTSetComponent <Component>
"               :TTSetSummary <Summary >
"
"
"               :TTAddComment               - Add the comment to the current
"                                             ticket
"
"
"               In the Ticket List window j and k jump to next ticket
"               enter will select a ticket if it is hovering over a number
"
"         Bugs:
"
"               Ocassionally when a wiki page/ticket is loaded it will throw an error.
"               Just try and load it again
"
"               Please log any issues at http://www.ascetinteractive.com.au/vimtrac
"
"        To Do:
"               - Complete Error handling for missing Files/Trac Error States
"               - Add a new Wiki Page Option
"               - Improve the toc scrolling (highlight current line)
"               - Improve Ticket Viewing option
"               - Add support for multiple trac servers
"
"}}}
"Configuration
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

if exists("g:tracvim_loaded") || !exists('g:tracServerList') || g:tracServerList == {}
    finish
endif

if !has("python")
    call confirm('Trac.vim needs vim python 2.6 support. Wont load', 'OK')
    finish
endif

pyfile <sfile>:p:h/trac.py

python import sys
python if sys.version_info[:2] < (2, 6): vim.command('let g:tracPythonVersionFlag = 1')

if exists('g:tracPythonVersionFlag')
    call confirm("Trac.vim requires python 2.6 or later to work correctly")
    finish
endif

if !exists('g:tracDefaultComment')
let g:tracDefaultComment = 'VimTrac update' " DEFAULT COMMENT CHANGE
endif

if !exists('g:tracHideTracWiki')
    let g:tracHideTracWiki = 'yes' " SET TO yes/no IF YOU WANT TO HIDE
                                   " ALL THE INTERNAL TRAC WIKI PAGES (^Wiki*/^Trac*)
endif

if !exists('g:tracTempHtml')
    let g:tracTempHtml = '/tmp/trac_wiki.html'
endif

if !exists('g:tracBrowser')
    let g:tracBrowser = 'lynx'         " For Setting up Browser view (terminal)
    "let g:tracBrowser = 'firefox'     " For Setting up Browser view (linux gui  - not tested)
    "let g:tracBrowser = '"C:\Program Files\Mozilla Firefox\firefox.exe"' "GVim on Windows not tested
endif

"This can be modified to speed up queries
if !exists('g:tracTicketClause')
    let g:tracTicketClause = 'status!=closed'
endif

"Set this to 1 if you wan the ticket view to ignore attribute changes which
"can clutter up the view
"
if !exists('g:tracTicketBriefDescription')
    let g:tracTicketBriefDescription = 1
endif


"Layouts can be modified here
if !exists('g:tracWikiStyle')
    let g:tracWikiStyle     = 'full'    " 'bottom' 'top' 'full'
endif
if !exists('g:tracSearchStyle')
    let g:tracSearchStyle   = 'left'   " 'right'
endif
if !exists('g:tracTimelineStyle')
    let g:tracTimelineStyle = 'bottom'   " 'left' 'right'
endif
" Ticket view styles note the summary style needs the Align plugin
if !exists('g:tracTicketStyle')
    let g:tracTicketStyle   = 'summary' " 'full'  'top' 'left' 'right' 'full'
endif

if !exists('g:tracUseTab')
    let g:tracUseTab = 1
endif

"Leader Short CUTS (Uncomment or add and customise to yout vimrc)
"Open Wiki
" map <leader>to :TWOpen<cr>
" Save Wiki
" map <leader>tw :TWSave<cr>
" Close wiki/ticket view
" map <leader>tq :TClose<cr>
" resize
" map <leader>tt :python trac_window_resize()<cr>
" preview window
" map <leader>tp :python trac_preview()<cr>
"
" map <leader>tp :python trac.summary_view()<cr>

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
"End Configuration

"
"


"Commmand Declarations
"
"NOTE: Due to the command list increasing as of version 0.3 of the plugin several command names
"have been renamed. The ':Trac' command prefix has been cut down to :T and the first inital of
"the module eg :TW... for TracWiki commands :TT... for Trac ticket commands
"
"The trac.py file no longer references these commands directly so you are free
"to change them if they clash with another plugin.
"
"WIKI MODULE COMMANDS

let g:tracDefaultView = 'wiki' " 'ticket' 'timeline'
com! -nargs=+ -complete=customlist,ComTracServers TracServer  python trac.set_server(<q-args>)

com! -nargs=? -complete=customlist,ComWiki TWOpen python trac.wiki_view(<f-args>)

fun LoadWikiCommands()
    "NOTE: TWSave is referenced in trac.py
    com! -nargs=*                                     TWSave          python trac.wiki.save(<q-args>)
    com! -nargs=? -complete=customlist,ComAttachments TWGetAttachment python trac.get_attachment(<f-args>)
    com! -nargs=? -complete=file                      TWAddAttachment python trac.add_attachment(<f-args>)
    "HTML Preview/Dumps
    com! -nargs=0                                     TWPreview       python trac.preview(False)
    com! -nargs=0                                     TWDump          python trac.preview(True)
    com! -nargs=?                                     TWVimDiff       python trac.wiki.vim_diff(<f-args>)
    com! -nargs=0                                     TWInfo          python print trac.wiki.get_page_info()
endfun

fun UnloadWikiCommands()
    try
        delc TWSave
        delc TWGetAttachment
        delc TWAddAttachment
        delc TWPreview
        delc TWDump
        delc TWVimDiff
        delc TWInfo
    endtry
endfun


"TICKET MODULE COMMANDS
com! -nargs=? TTOpen python trac.ticket_view(<f-args>)

fun LoadTicketCommands()
    "Trac Ticket modifications
    com! -nargs=+                                     TTCreateTask        python trac.create_ticket('task', <q-args>)
    com! -nargs=+                                     TTCreateDefect      python trac.create_ticket('defect', <q-args>)
    com! -nargs=+                                     TTCreateEnhancement python trac.create_ticket('enhancement', <q-args>)

    com! -nargs=0                                     TTSetSummary        python trac.update_ticket('summary')
    com! -nargs=0                                     TTUpdateDescrption  python trac.update_ticket('description')
    com! -nargs=0                                     TTAddComment        python trac.update_ticket('comment')
    com! -nargs=? -complete=customlist,ComMilestone   TTSetMilestone      python trac.update_ticket('milestone', <f-args>)
    com! -nargs=? -complete=customlist,ComType        TTSetType           python trac.update_ticket('type', <f-args>)
    com! -nargs=? -complete=customlist,ComStatus      TTSetStatus         python trac.update_ticket('status', <f-args>)
    com! -nargs=? -complete=customlist,ComResolution  TTSetResolution     python trac.update_ticket('resolution', <f-args>)
    com! -nargs=? -complete=customlist,ComPriority    TTSetPriority       python trac.update_ticket('priority', <f-args>)
    com! -nargs=? -complete=customlist,ComSeverity    TTSetSeverity       python trac.update_ticket('severity', <f-args>)
    com! -nargs=? -complete=customlist,ComComponent   TTSetComponent      python trac.update_ticket('component', <f-args>)
    com! -nargs=?                                     TTSetOwner          python trac.update_ticket('owner', <f-args>)

    com! -nargs=? -complete=customlist,ComMilestone   TTFilterMilestone   python trac.filter_ticket('milestone', <f-args>)
    com! -nargs=? -complete=customlist,ComType        TTFilterType        python trac.filter_ticket('type', <f-args>)
    com! -nargs=? -complete=customlist,ComStatus      TTFilterStatus      python trac.filter_ticket('status', <f-args>)
    com! -nargs=? -complete=customlist,ComResolution  TTFilterResolution  python trac.filter_ticket('resolution', <f-args>)
    com! -nargs=? -complete=customlist,ComPriority    TTFilterPriority    python trac.filter_ticket('priority', <f-args>)
    com! -nargs=? -complete=customlist,ComSeverity    TTFilterSeverity    python trac.filter_ticket('severity', <f-args>)
    com! -nargs=? -complete=customlist,ComComponent   TTFilterComponent   python trac.filter_ticket('component', <f-args>)
    com! -nargs=? -complete=customlist,ComVersion     TTFilterVersion     python trac.filter_ticket('version', <f-args>)
    com! -nargs=?                                     TTFilterOwner       python trac.filter_ticket('owner', <f-args>)

    com! -nargs=?                                     TTFilterNoMilestone python trac.filter_ticket('milestone', '')
    com! -nargs=?                                     TTFilterNoOwner     python trac.filter_ticket('owner', '')

    com! -nargs=? -complete=customlist,ComMilestone   TTIgnoreMilestone   python trac.filter_ticket('milestone', <f-args>, True)
    com! -nargs=? -complete=customlist,ComType        TTIgnoreType        python trac.filter_ticket('type', <f-args>, True)
    com! -nargs=? -complete=customlist,ComStatus      TTIgnoreStatus      python trac.filter_ticket('status', <f-args>, True)
    com! -nargs=? -complete=customlist,ComResolution  TTIgnoreResolution  python trac.filter_ticket('resolution', <f-args>, True)
    com! -nargs=? -complete=customlist,ComPriority    TTIgnorePriority    python trac.filter_ticket('priority', <f-args>, True)
    com! -nargs=? -complete=customlist,ComSeverity    TTIgnoreSeverity    python trac.filter_ticket('severity', <f-args>, True)
    com! -nargs=? -complete=customlist,ComComponent   TTIgnoreComponent   python trac.filter_ticket('component', <f-args>, True)
    com! -nargs=?                                     TTIgnoreOwner       python trac.filter_ticket('owner', <f-args>, True)

    com! -nargs=0                                     TTIgnoreNoMilestone python trac.filter_ticket('milestone', '', True)
    com! -nargs=0                                     TTIgnoreNoOwner     python trac.filter_ticket('owner', '', True)

    com! -nargs=0                                     TTClearAllFilters   python trac.filter_clear()
    com! -nargs=? -complete=customlist,ComSort        TTClearFilter       python trac.filter_clear(<f-args>)
    com! -nargs=*                                     TTListFilters       python print trac.ticket.filters
    "Ticket Sorting
    com! -nargs=? -complete=customlist,ComSort        TTOrderBy           python trac.sort_ticket('order', <f-args>)
    com! -nargs=? -complete=customlist,ComSort        TTGroupBy           python trac.sort_ticket('group', <f-args>)

    " Ticket pagination
    com! -nargs=0                                     TTNextPage          python trac.ticket_paginate()
    com! -nargs=0                                     TTPreviousPage      python trac.ticket_paginate(-1)
    com! -nargs=0                                     TTFirstPage         python trac.ticket.page = 1; trac.ticket_view()
    com! -nargs=0                                     TTNumberTickets     python print trac.ticket.number_tickets()

    "Ticket Attachments
    com! -nargs=? -complete=customlist,ComAttachments TTGetAttachment     python trac.get_attachment(<f-args>)
    com! -nargs=? -complete=file                      TTAddAttachment     python trac.add_attachment(<f-args>)
    "Html Preview
    com! -nargs=0                                     TTPreview           python trac.preview()

    com! -nargs=+ -complete=customlist,ComAction      TTAction            python trac.act_ticket(<q-args>)
endfun

fun UnloadTicketCommands()
    "Trac Ticket modifications
    try
        delc TTCreateTask
        delc TTCreateDefect
        delc TTCreateEnhancement
        delc TTAddComment
        "Ticket Attributes
        delc TTSetMilestone
        delc TTSetStatus
        delc TTSetType
        delc TTSetResolution
        delc TTSetPriority
        delc TTSetSeverity
        delc TTSetComponent
        delc TTSetOwner
        delc TTSetSummary

        delc TTUpdateDescrption

        delc TTFilterMilestone
        delc TTFilterType
        delc TTFilterStatus
        delc TTFilterResolution
        delc TTFilterPriority
        delc TTFilterSeverity
        delc TTFilterComponent
        delc TTFilterOwner
        delc TTClearFilter
        delc TTClearAllFilters

        delc TTOrderBy
        delc TTGroupBy

        delc TTIgnoreMilestone
        delc TTIgnoreType
        delc TTIgnoreStatus
        delc TTIgnoreResolution
        delc TTIgnorePriority
        delc TTIgnoreSeverity
        delc TTIgnoreComponent
        delc TTIgnoreOwner

        delc TTIgnoreNoMilestone
        delc TTIgnoreNoOwner

        "Ticket Attachments
        delc TTGetAttachment
        delc TTAddAttachment
        "Html Preview
        delc TTPreview

        delc TTAction
    endtry
endfun

"MISCELLANEOUS
com! -nargs=+ TSearch         python trac.search_view(<q-args>)
com! -nargs=1 TChangesetOpen  python trac.changeset_view(<f-args>)
com! -nargs=0 TTimelineOpen   python trac.timeline_view()
com! -nargs=0 TClose          python trac.normal_view(<f-args>)

"FUNCTION COMPLETES
fun ComTracServers(A, L, P)
    return filter(keys(g:tracServerList), 'v:val =~ "^' . a:A . '"')
endfun

let g:tracOptions = 1

fun ComAttachments(A, L, P)
    python trac.list_attachments()
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComWiki(A, L, P)
    python trac.wiki.get_options()
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

"COMMAND COMPLETES
fun ComMilestone(A, L, P)
    python trac.ticket.get_options(0)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComType(A, L, P)
    python trac.ticket.get_options(1)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComStatus(A, L, P)
    python trac.ticket.get_options(2)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComResolution(A, L, P)
    python trac.ticket.get_options(3)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComPriority(A, L, P)
    python trac.ticket.get_options(4)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComSeverity(A, L, P)
    python trac.ticket.get_options(5)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComComponent(A, L, P)
    python trac.ticket.get_options(6)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComVersion(A, L, P)
    python trac.ticket.get_options(7)
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComSort(A, L, P)
    python trac.ticket.get_options(type_='field')
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun

fun ComAction(A, L, P)
    python trac.ticket.get_options(type_='action')
    return filter(split(g:tracOptions, '|'), 'v:val =~ "^' . a:A . '"')
endfun


"Callback Function for Minibufexplorer et al windows that dont like being
"closed by the :only command
"TODO add other common plugins that may be affected 
"see OpenCloseCallbacks in the wiki
fun TracOpenViewCallback()
    try
        CMiniBufExplorer
    catch
        return 0
    endt

    return 1
endfun

fun TracCloseViewCallback()
    try
        MiniBufExplorer
    catch
        return 0
    endt
    return 1
endfun

python trac_init()

let g:tracvim_loaded = 1
