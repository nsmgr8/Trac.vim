# -*- encoding: utf-8 -*-

import os
import vim
import xmlrpclib
import re
import codecs
import datetime
from time import strftime
import urllib2


trac = None


def confirm(text):
    return int(vim.eval('confirm("{0}", "&Yes\n&No", 2)'.format(text))) != 2


def truncate_words(text, num_words=10):
    words = text.split()
    if len(words) <= num_words:
        return text
    return ' '.join(words[:num_words]) + '...'


class HTTPDigestTransport(xmlrpclib.SafeTransport):
    """
    Transport that uses urllib2 so that we can do Digest authentication.
    """
    def __init__(self, scheme, username, password, realm):
        self.username = username
        self.password = password
        self.realm = realm
        self.scheme = scheme
        self.verbose = False
        xmlrpclib.SafeTransport.__init__(self)

    def request(self, host, handler, request_body, verbose):
        url = '{scheme}://{host}{handler}'.format(scheme=self.scheme,
                                                  host=host, handler=handler)
        request = urllib2.Request(url)
        request.add_data(request_body)
        request.add_header("User-Agent", self.user_agent)
        request.add_header("Content-Type", "text/xml")

        authhandler = urllib2.HTTPDigestAuthHandler()
        authhandler.add_password(self.realm, url, self.username, self.password)
        opener = urllib2.build_opener(authhandler)

        f = opener.open(request)
        return self.parse_response(f)


class VimWindow(object):
    """ wrapper class of window of vim """
    def __init__(self, name='WINDOW'):
        self.name = name
        self.buffer = []

    def prepare(self):
        """ check window is OK, if not then create """
        if not all([self.buffer, self.get_winnr() > 0]):
            self.create()
        self.set_focus()

    def get_winnr(self):
        """ Returns the vim window number for wincmd calls """
        return int(vim.eval("bufwinnr('{0}')".format(self.name)))

    def write(self, msg, append=False):
        """ write to a vim buffer """
        if not isinstance(msg, basestring):
            msg = str(msg)
        msg = msg.encode('utf-8', 'ignore')
        self.prepare()
        if not append:
            self.buffer[:] = msg.split('\n')
        else:
            self.buffer.append(msg.split('\n'))
        self.command('normal gg')
        self.on_write()

    def on_write(self):
        """ for vim commands after a write is made to a buffer """

    def dump(self):
        """ returns the contents buffer as a string """
        return "\n".join(self.buffer)

    def create(self, method='new'):
        """ creates a  window """
        vim.command('silent {0} {1}'.format(method, self.name))
        vim.command("setlocal buftype=nofile")
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
        self.buffer = vim.current.buffer

        self.width = int(vim.eval("winwidth(0)"))
        self.height = int(vim.eval("winheight(0)"))
        self.on_create()

    def on_create(self):
        """ On Create is used  by the VimWindow subclasses to define vim
            mappings and buffer settings
        """

    def destroy(self):
        """ destroy window """
        if not self.buffer:
            return
        self.command('bdelete {0}'.format(self.name))

    def command(self, cmd):
        """ go to my window & execute command """
        self.prepare()
        vim.command(cmd)

    def set_focus(self):
        """ Set focus on the current window """
        vim.command('{0}wincmd w'.format(self.get_winnr()))

    def resize_width(self, size=False):
        """ resizes to default width or specified size """
        self.set_focus()
        if not size:
            size = self.width
        vim.command('vertical resize {0}'.format(size))


class NonEditableWindow(VimWindow):
    def on_write(self):
        vim.command("setlocal nomodifiable")


class UI(object):
    """ User Interface Base Class """
    mode = 0

    def open(self):
        """ change mode to a vim window view """
        if self.mode == 1:
            return
        self.mode = 1
        self.create()

    def normal_mode(self):
        """ restore mode to normal """
        if self.mode == 0:
            return
        self.destroy()
        self.mode = 0


class TracWiki(object):
    """ Trac Wiki Class """
    def __init__(self):
        self.reset_attrs()

    def reset_attrs(self):
        self.pages = []
        self.revision = 1
        self.current_page = False
        self.visited_pages = []

    def get_all_pages(self):
        """ Gets a List of Wiki Pages """
        self.pages = trac.server.wiki.getAllPages()
        return "\n".join(self.pages)

    def get_page(self, name, revision=None):
        """ Get Wiki Page """
        try:
            name = name.strip()
            self.current_page = name
            if name not in self.visited_pages:
                self.visited_pages.append(name)
            if revision is not None:
                wikitext = trac.server.wiki.getPage(name, revision)
            else:
                wikitext = trac.server.wiki.getPage(name)
                self.get_page_info()
        except:
            if revision is None:
                wikitext = "Describe {0} here.".format(name)
            else:
                wikitext = ''
        return wikitext

    def save(self,  comment):
        """ Saves a Wiki Page """
        if not comment:
            comment = trac.default_comment
        trac.server.wiki.putPage(self.current_page,
                trac.uiwiki.wikiwindow.dump(), {"comment": comment})

    def get_page_info(self):
        """ Returns page revision info most recent author """
        try:
            info = trac.server.wiki.getPageInfo(self.current_page)
            self.revision = info['version']
            return '{name} v{version}, author: {author}'.format(**info)
        except:
            return 'Cannot get page info'

    def create_page(self, name, content, comment):
        """ Saves a Wiki Page """
        return trac.server.wiki.putPage(name, content, {"comment": comment})

    def add_attachment(self, file):
        """ Add attachment """
        file_name = os.path.basename(file)
        path = '{0}/{1}'.format(self.current_page, file_name)
        trac.server.wiki.putAttachment(path,
                                       xmlrpclib.Binary(open(file).read()))

    def get_attachment(self, file):
        """ Get attachment """
        buffer = trac.server.wiki.getAttachment(file)
        file_name = os.path.basename(file)

        if os.path.exists(file_name):
            print "Will not overwrite existing file {0}".format(file_name)
        else:
            with open(file_name, 'w') as fp:
                fp.write(buffer.data)

    def list_attachments(self):
        """ Look for attachments on the current page """
        self.attachments = trac.server.wiki.listAttachments(self.current_page)

    def get_wiki_html(self, wikitext):
        """ Converts the wikitext from a buffer to html for previews """
        return trac.server.wiki.wikiToHtml(wikitext)

    def html_view(self, page=None):
        """ Displays a wiki in a preview browser as set in trac.vim """
        if not page:
            page = vim.current.line

        html = trac.server.wiki.getPageHTML(page)
        file_name = vim.eval('g:tracTempHtml')
        with codecs.open(file_name, 'w', 'utf-8') as fp:
            fp.write(html)

        browser = vim.eval('g:tracBrowser')
        vim.command('!{0} file://{1}'.format(browser, file_name))

    def get_options(self):
        """ returns a list of a sites wiki pages for command completes """
        vim.command('let g:tracOptions="{0}"'.format("|".join(self.pages)))

    def vim_diff(self, revision=None):
        """ Creates a vimdiff of an earlier wiki revision """
        #default to previous revision
        if revision is None:
            revision = self.revision - 1

        wikitext = self.get_page(self.current_page, revision)
        if not wikitext:
            print 'No previous version available'
            return

        diffwindow = WikiVimDiffWindow()
        diffwindow.create('vertical belowright diffsplit')
        diffwindow.write(wikitext)

        trac.uiwiki.tocwindow.resize_width(30)
        trac.uiwiki.wikiwindow.set_focus()
        diffwindow.resize_width(80)


class TracWikiUI(UI):
    """ Trac Wiki User Interface Manager """
    def __init__(self):
        """ Initialize the User Interface """
        self.wikiwindow = WikiWindow()
        self.tocwindow = WikiTOContentsWindow()
        self.attachwindow = AttachmentWindow()

    def destroy(self):
        """ destroy windows """
        self.wikiwindow.destroy()
        self.tocwindow.destroy()
        self.attachwindow.destroy()

        vim.command("call UnloadWikiCommands()")

    def create(self):
        """ create windows  and load the internal Commands """
        vim.command("call LoadWikiCommands()")
        style = vim.eval('g:tracWikiStyle')

        if style == 'full':
            if int(vim.eval('g:tracUseTab')):
                vim.command('tabnew')
            self.wikiwindow.create(' 30 vnew')
            vim.command('call TracOpenViewCallback()')
            vim.command("only")
            self.tocwindow.create("vertical aboveleft new")
        elif style == 'top':
            self.wikiwindow.create("aboveleft new")
            self.tocwindow.create("vertical aboveleft new")
        else:  # bottom
            self.tocwindow.create("belowright new")
            self.wikiwindow.create("vertical belowright new")


class WikiWindow(VimWindow):
    """ Wiki Window """
    def __init__(self, name='WIKI_WINDOW'):
        VimWindow.__init__(self, name)

    def on_create(self):
        nmaps = [
            ('<c-]>', ':python trac.wiki_view("<C-R><C-W>")<cr>'),
            ('wo', 'F:lvt<space>"zy:python trac.wiki_view("<C-R>z")<cr>'),
            ('w]', 'F:lvt]"zy:python trac.wiki_view("<C-R>z")<cr>'),
            ('wb', ':python trac.wiki_view(direction=-1)<cr>'),
            ('wf', ':python trac.wiki_view(direction=1)<cr>'),
            ('<2-LeftMouse>', ':python trac.wiki_view("<C-R><C-W>")<cr>'),
            (':w<cr>', ':TWSave<cr>'),
        ]
        for m in nmaps:
            vim.command('nnoremap <buffer> {0} {1}'.format(*m))
        vim.command('vertical resize +70')
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal linebreak')
        vim.command('setlocal noswapfile')


class WikiTOContentsWindow(NonEditableWindow):
    """ Wiki Table Of Contents """
    def __init__(self, name='WIKITOC_WINDOW'):
        NonEditableWindow.__init__(self, name)

        if vim.eval('tracHideTracWiki') == 'yes':
            self.hide_trac_wiki = True
        else:
            self.hide_trac_wiki = False

    def on_create(self):
        nmaps = [
            ('<cr>', ':python trac.wiki_view("CURRENTLINE")<cr>'),
            ('<2-LeftMouse>', ':python trac.wiki_view("CURRENTLINE")<cr>'),
            ('<Space>', ':python trac.wiki.html_view()<cr><cr><cr>'),
        ]
        for m in nmaps:
            vim.command('nnoremap <buffer> {0} {1}'.format(*m))
        vim.command('setlocal winwidth=30')
        vim.command('vertical resize 30')
        vim.command('setlocal cursorline')
        vim.command('setlocal linebreak')
        vim.command('setlocal noswapfile')

    def on_write(self):
        if self.hide_trac_wiki:
            vim.command('silent g/^Trac/d _')
            vim.command('silent g/^Wiki/d _')
            vim.command('silent g/^InterMapTxt$/d _')
            vim.command('silent g/^InterWiki$/d _')
            vim.command('silent g/^SandBox$/d _')
            vim.command('silent g/^InterTrac$/d _')
            vim.command('silent g/^TitleIndex$/d _')
            vim.command('silent g/^RecentChanges$/d _')
            vim.command('silent g/^CamelCase$/d _')

        vim.command('sort')
        vim.command('silent norm ggOWikiStart')
        NonEditableWindow.on_write(self)


class AttachmentWindow(NonEditableWindow):
    """ Wiki's attachments """
    def __init__(self, name='ATTACHMENT_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.get_attachment("CURRENTLINE")<cr>')
        vim.command('setlocal cursorline')
        vim.command('setlocal linebreak')
        vim.command('setlocal noswapfile')


class WikiVimDiffWindow(NonEditableWindow):
    """ For Earlier revisions """
    def __init__(self, name='WIKI_DIFF_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <c-]> '
                    ':python trac.wiki_view("<C-R><C-W>")<cr>')
        vim.command('nnoremap <buffer> :q!<cr> '
                    ':python trac.uiwiki.tocwindow.resize_width(30)<cr>')
        #map gf to a new buffer(switching buffers doesnt work with nofile)
        vim.command('nnoremap <buffer> gf <c-w><c-f><c-w>K')
        vim.command('vertical resize +70')
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal linebreak')
        vim.command('setlocal noswapfile')


class TracSearch(object):
    """ Search for tickets and Wiki's """
    def search(self, search_pattern):
        """ Perform a search call  """
        a_search = trac.server.search.performSearch(search_pattern)
        result = [
            "Results for {0}".format(search_pattern),
            "(Hit <enter> or <space> on a line containing :>>)",
            "",
        ]
        for search in a_search:
            if '/ticket/' in search[0]:
                prefix = "Ticket"
            if '/wiki/' in search[0]:
                prefix = "Wiki"
            if '/changeset/' in search[0]:
                prefix = "Changeset"
            title = '{0}:>> {1}'.format(prefix, os.path.basename(search[0]))
            result.extend([title, search[4], ""])
        return '\n'.join(result)


class TracSearchUI(UI):
    """ Search UI manager """
    def __init__(self):
        """ Initialize the User Interface """
        self.searchwindow = TracSearchWindow()

    def destroy(self):
        """ destroy windows """
        self.searchwindow.destroy()

    def create(self):
        """ create windows """
        style = vim.eval('g:tracSearchStyle')
        if style == 'right':
            self.searchwindow.create("vertical belowright new")
        else:
            self.searchwindow.create("vertical aboveleft new")


class TracSearchWindow(NonEditableWindow):
    """ for displaying search results """
    def __init__(self, name='SEARCH_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        """ Buffer Specific Mappings for The Search Window """
        vim.command('nnoremap <buffer> <c-]> '
                    ':python trac.wiki_view("<cword>")<cr>')
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.search_open(False)<cr>')
        #vim.command('nnoremap <buffer> <space> '
        #            ':python trac.search_open(True)<cr>') This messes folds
        vim.command('setlocal syntax=text')
        vim.command('setlocal foldmethod=indent')
        vim.command('setlocal linebreak')
        vim.command('setlocal noswapfile')

    def on_write(self):
        """ Basic Highlighting """
        NonEditableWindow.on_write(self)
        vim.command('syntax reset')
        vim.command('syn match Keyword /\w*:>> .*$/ contains=Title')
        vim.command('syn match Title /\w*:>>/ contained')
        #vim.command('highlight Title ctermbg=255 guibg=255')
        vim.command('syn match SpecialKey /^-*$/')


class TracTicket(object):
    """ Trac Ticket Class """
    def __init__(self):
        self.reset_attrs()

    def reset_attrs(self):
        self.current_ticket_id = None
        self.visited_tickets = []
        self.actions = []
        self.attribs = []
        self.tickets = []
        self.sorter = {'order': 'priority', 'group': 'milestone'}
        self.filters = {}
        self.page = 1
        self.attachments = []

    def get_attribs(self):
        """ Get all milestone/ priority /status options """
        multicall = xmlrpclib.MultiCall(trac.server)
        multicall.ticket.milestone.getAll()
        multicall.ticket.type.getAll()
        multicall.ticket.status.getAll()
        multicall.ticket.resolution.getAll()
        multicall.ticket.priority.getAll()
        multicall.ticket.severity.getAll()
        multicall.ticket.component.getAll()
        multicall.ticket.version.getAll()
        self.attribs = [option for option in multicall()]

    def set_sort_attr(self, attrib, value):
        self.sorter[attrib] = value

    def query_string(self, f_all=False):
        query = 'order={order}&group={group}&page={page}'
        query = query.format(page=self.page, **self.sorter)
        query = '{0}&{1}'.format(query, vim.eval('g:tracTicketClause'))
        filters = ['{0}={1}'.format(k, v) for k, v in self.filters.iteritems()]
        if filters:
            query = '{0}&{1}'.format(query, '&'.join(filters))
        if f_all:
            query = '{0}&max=0'.format(query)
        return query

    def number_tickets(self):
        return len(trac.server.ticket.query(self.query_string(True)))

    def get_all(self, summary=True, cached=False):
        """ Gets a List of Ticket Pages """
        if not self.attribs:
            self.get_attribs()

        if cached and self.tickets:
            tickets = self.tickets
        else:
            multicall = xmlrpclib.MultiCall(trac.server)
            for ticket in trac.server.ticket.query(self.query_string()):
                multicall.ticket.get(ticket)
            tickets = multicall()
            self.tickets = tickets

        columns = ['#', 'summary', 'status', 'type', 'priority', 'component',
                   'milestone', 'version', 'owner', 'reporter']
        if summary:
            ticket_list = [' || '.join([c.title() for c in columns])]
        else:
            ticket_list = ["Hit <enter> or <space> on a line containing :>>"]
            arranged = 'Group: {group}, Order: {order}, Page: {page}'
            ticket_list.append(arranged.format(page=self.page, **self.sorter))
            filters = ', '.join(['{0}={1}'.format(k, v) for k, v
                                    in self.filters.iteritems()])
            ticket_list.append('Filters: {0}'.format(filters))
            ticket_list.append('No. of tickets: {0}'.format(
                                self.number_tickets()))

        for ticket in tickets:
            if summary:
                str_ticket = [str(ticket[0]),
                              truncate_words(ticket[3]['summary'])]
            else:
                str_ticket = ["", "Ticket:>> {0}".format(ticket[0]),
                              ticket[3]['summary']]
            for f in columns[2:]:
                v = truncate_words(ticket[3].get(f, ''))
                if not summary:
                    v = "   * {0}: {1}".format(f.title(), v)
                str_ticket.append(v)

            separator = ' || ' if summary else '\n'
            ticket_list.append(separator.join(str_ticket))

        return "\n".join(ticket_list)

    def get(self, tid):
        """ Get Ticket Page """
        try:
            tid = int(tid)
            ticket = trac.server.ticket.get(tid)
            self.current_ticket_id = tid
            if tid not in self.visited_tickets:
                self.visited_tickets.append(tid)
            ticket_changelog = trac.server.ticket.changeLog(tid)
            self.current_component = ticket[3].get("component")
            actions = self.get_actions()
            self.list_attachments()
        except:
            return 'Please select a ticket'

        str_ticket = ["= Ticket Summary =", "",
                "Ticket #{0}: {1}".format(ticket[0], ticket[3]['summary']), ""]
        for f in ('owner', 'reporter', 'status', 'type', 'priority',
                  'component', 'milestone', 'version'):
            v = ticket[3].get(f, '')
            str_ticket.append(" *{0:>12}: {1}".format(f.title(), v))

        str_ticket.append("")
        str_ticket.append("= Description: =")
        str_ticket.append("")
        str_ticket.append(ticket[3]["description"])
        str_ticket.append("")
        str_ticket.append("= Changelog =")

        submission = [None, None]
        for change in ticket_changelog:
            if not change[4]:
                continue
            if isinstance(change[0], xmlrpclib.DateTime):
                dt = datetime.datetime.strptime(change[0].value,
                                                "%Y%m%dT%H:%M:%S")
            else:
                dt = datetime.datetime.fromtimestamp(change[0])

            my_time = dt.strftime("%a %d/%m/%Y %H:%M")
            new_submission = [my_time, change[1]]
            if submission != new_submission:
                str_ticket.append("")
                str_ticket.append('== {0} ({1}) =='.format(my_time,
                                                            change[1]))
                submission = new_submission
            if change[2] in ('comment', 'description'):
                str_ticket.append(' * {0}:'.format(change[2]))
                str_ticket.append(change[4])
            else:
                if change[3]:
                    str_ticket.append(" * '''{0}''': ''{1}'' > ''{2}''".format(
                        change[2], change[3], change[4]))
                else:
                    str_ticket.append(" * '''{0}''': ''{1}''".format(change[2],
                        change[4]))
            # TODO: just mention if a ticket has been changed
            # brief = vim.eval('g:tracTicketBriefDescription')

        str_ticket.append("")
        str_ticket.append('== Action ==')
        str_ticket.append("")
        for action in actions:
            str_ticket.append(' - {action[0]}'.format(action=action))

        return '\n'.join(str_ticket)

    def update(self, comment, attribs={}, notify=False):
        """ add ticket comments change attributes """
        return trac.server.ticket.update(self.current_ticket_id, comment,
                                         attribs, notify)

    def create(self, description, summary, attributes={}):
        """ create a trac ticket """
        self.current_ticket_id = trac.server.ticket.create(summary,
                description, attributes, False)

    def get_attachment(self, file):
        """ Get attachment """
        buffer = trac.server.ticket.getAttachment(self.current_ticket_id, file)
        file_name = os.path.basename(file)

        if os.path.exists(file_name):
            print "Will not overwrite existing file", file_name
        else:
            with open(file_name, 'w') as fp:
                fp.write(buffer.data)

    def add_attachment(self, file, comment=''):
        """ Add attachment """
        file_name = os.path.basename(file)
        trac.server.ticket.putAttachment(self.current_ticket_id, file_name,
                comment, xmlrpclib.Binary(open(file).read()))

    def list_attachments(self):
        a_attach = trac.server.ticket.listAttachments(self.current_ticket_id)
        self.attachments = []
        for attach in a_attach:
            self.attachments.append(attach[0])

    def get_actions(self):
        """ Get available actions for a ticket """
        actions = trac.server.ticket.getActions(self.current_ticket_id)
        self.actions = []
        for action in actions:
            if action[3]:
                for options in action[3]:
                    if options[2]:
                        for a in options[2]:
                            self.actions.append('{0} {1}'.format(action[0], a))
                    else:
                        self.actions.append('{0} {1}'.format(action[0],
                                                             options[1]))
            else:
                self.actions.append(action[0])
        return actions

    def act(self, action, comment=''):
        """ Perform an action on current ticket """
        action = action.split()
        try:
            name, options = action[0], action[1:]
        except IndexError:
            print 'No action requested'
            return
        actions = self.get_actions()
        action = None
        for a in actions:
            if a[0] == name:
                action = a
                break
        else:
            print 'action is not valid'
            return
        attribs = {'action': name}
        for i, opt in enumerate(options):
            ac = action[3][i]
            if opt in ac[2]:
                attribs[ac[0]] = opt
            elif opt == ac[1]:
                attribs[ac[0]] = opt
            else:
                print 'invalid option'
                return
        self.update(comment, attribs)

    def get_options(self, op_id=0, type_='attrib'):
        options = {
            'attrib': self.attribs[op_id],
            'field': ['component', 'milestone', 'owner', 'priority',
                      'reporter', 'status', 'type', 'version'],
            'action': self.actions,
        }.get(type_, [])
        vim.command('let g:tracOptions="{0}"'.format("|".join(options)))


class TracTicketUI(UI):
    """ Trac Wiki User Interface Manager """
    def __init__(self):
        """ Initialize the User Interface """
        self.ticketwindow = TicketWindow()
        self.tocwindow = TicketTOContentsWindow()
        self.commentwindow = TicketCommentWindow()
        self.summarywindow = TicketSummaryWindow()
        self.attachwindow = AttachmentWindow()

    def normal_mode(self):
        """ restore mode to normal """
        if self.mode == 0:
            return

        self.destroy()
        self.mode = 0

    def destroy(self):
        """ destroy windows """
        vim.command("call UnloadTicketCommands()")

        self.ticketwindow.destroy()
        self.tocwindow.destroy()
        self.commentwindow.destroy()
        self.summarywindow.destroy()
        self.attachwindow.destroy()

    def create(self):
        """ create windows """
        style = vim.eval('g:tracTicketStyle')
        if style == 'right':
            self.tocwindow.create("vertical belowright new")
            self.ticketwindow.create("belowright new")
            self.commentwindow.create("belowright new")
        elif style == 'left':
            self.commentwindow.create("vertical aboveleft new")
            self.ticketwindow.create("aboveleft new")
            self.tocwindow.create(" aboveleft new")
        elif style == 'top':
            self.commentwindow.create("aboveleft new")
            self.ticketwindow.create("vertical aboveleft new")
            self.tocwindow.create("vertical aboveleft new")
        elif style == 'bottom':
            self.tocwindow.create("belowright new")
            self.ticketwindow.create("vertical belowright new")
            self.commentwindow.create("vertical belowright new")
        elif style == 'summary':
            if int(vim.eval('g:tracUseTab')):
                vim.command('tabnew')
            self.ticketwindow.create('vertical belowright new')
            vim.command('call TracOpenViewCallback()')
            vim.command('only')
            self.summarywindow.create('belowright 9 new')
            vim.command('wincmd k')
            self.commentwindow.create('belowright 7 new')
            self.summarywindow.set_focus()
        else:
            self.tocwindow.create("belowright new")
            vim.command('call TracOpenViewCallback()')
            vim.command('only')
            self.ticketwindow.create("vertical  belowright 150 new")
            self.commentwindow.create("belowright 15 new")

        vim.command("call LoadTicketCommands()")


class TicketSummaryWindow(NonEditableWindow):
    """ Ticket Table Of Contents """
    def __init__(self, name='TICKETSUMMARY_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.ticket_view("SUMMARYLINE")<cr>')
        vim.command('nnoremap <buffer> <2-LeftMouse> '
                    ':python trac.ticket_view("SUMMARYLINE")<cr>')
        vim.command('nnoremap <buffer> wt '
                    ':above split<cr>:resize 1<cr>:wincmd j<cr>')
        vim.command('setlocal cursorline')
        vim.command('setlocal linebreak')
        vim.command('setlocal syntax=text')
        vim.command('setlocal foldmethod=indent')
        vim.command('setlocal nowrap')
        vim.command('silent norm gg')
        vim.command('setlocal noswapfile')
        vim.command('setlocal colorcolumn=0')

    def on_write(self):
        try:
            vim.command('AlignCtrl rl+')
            vim.command('%Align ||')
        except:
            vim.command('echo install Align for the best view of summary')
        vim.command('syn match Ignore /||/')
        vim.command('syn match Keyword /enhancement/')
        vim.command('syn match Identifier /task/')
        vim.command('syn match Todo /defect/')
        vim.command('syn match Type /blocker/')
        vim.command('syn match Special /critical/')
        vim.command('syn match PreProc /major/')
        vim.command('syn match PreProc /major/')
        vim.command('syn match Constant /minor/')
        vim.command('syn match Underlined /^\s*#.*$/')
        vim.command('syn match Constant /new/')
        vim.command('syn match Keyword /accepted/')
        vim.command('syn match Identifier /assigned/')
        vim.command('syn match Type /reopened/')
        vim.command('syn match Todo /ready/')
        vim.command('setlocal nomodifiable')


class TicketWindow(NonEditableWindow):
    """ Ticket Window """
    def __init__(self, name='TICKET_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> wb '
                    ':python trac.ticket_view(direction=-1)<cr>')
        vim.command('nnoremap <buffer> wf '
                    ':python trac.ticket_view(direction=1)<cr>')
        vim.command('nnoremap <buffer> ws '
                    ':python print trac.ticket.visited_tickets<cr>')
        vim.command('setlocal noswapfile')
        vim.command('setlocal textwidth=100')
        vim.command('setlocal syntax=tracwiki')


class TicketCommentWindow(VimWindow):
    """ For adding Comments to tickets """
    def __init__(self, name='TICKET_COMMENT_WINDOW'):
        VimWindow.__init__(self, name)

    def on_create(self):
        nmaps = [
            (':w<cr>', ':TTAddComment<cr>'),
            (':wq<cr>', ':TTAddComment<cr>'
                        ':python trac.normal_view()<cr>'),
        ]
        for m in nmaps:
            vim.command('nnoremap <buffer> {0} {1}'.format(*m))
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal noswapfile')


class TicketTOContentsWindow(NonEditableWindow):
    """ Ticket Table Of Contents """
    def __init__(self, name='TICKETTOC_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.ticket_view("CURRENTLINE")<cr>')
        vim.command('nnoremap <buffer> <2-LeftMouse> '
                    ':python trac.ticket_view("CURRENTLINE")<cr>')
        vim.command('setlocal cursorline')
        vim.command('setlocal linebreak')
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal foldmethod=indent')
        vim.command('setlocal nowrap')
        vim.command('silent norm ggf: <esc>')
        vim.command('setlocal noswapfile')
        vim.command('setlocal winwidth=50')
        vim.command('vertical resize 50')


class TracServerUI(UI):
    """ Server User Interface View """
    def __init__(self):
        self.serverwindow = ServerWindow()

    def server_mode(self):
        """ Displays server mode """
        self.create()
        vim.command('2wincmd w')  # goto srcview window(nr=1, top-left)

    def create(self):
        """ create windows """
        self.serverwindow.create("belowright new")

    def destroy(self):
        """ destroy windows """
        self.serverwindow.destroy()


class ServerWindow(NonEditableWindow):
    """ Server Window """
    def __init__(self, name='SERVER_WINDOW'):
        NonEditableWindow.__init__(self, name)


class TracTimeline:
    def read_timeline(self, server):
        """ Call the XML Rpc list """
        try:
            import feedparser
        except ImportError:
            print "Please install feedparser.py!"
            return

        query = 'ticket=on&changeset=on&wiki=on&max=50&daysback=90&format=rss'
        feed = '{scheme}://{server}/timeline?{q}'.format(q=query, **server)
        d = feedparser.parse(feed)
        str_feed = ["Hit <enter> or <space> on a line containing :>>", ""]
        for item in d['items']:
            #Each item is a dictionary mapping properties to values
            str_feed.append(strftime("%Y-%m-%d %H:%M:%S", item.updated_parsed))

            m = re.match(r"^Ticket #(\d+) (.*)$", item.title)
            if m:
                str_feed.append("Ticket:>> " + m.group(1))
                str_feed.append(m.group(2))
            m = re.match(r"^([\w\d]+) (edited by .*)$", item.title)
            if m:
                str_feed.append("Wiki:>> " + m.group(1))
                str_feed.append(m.group(2))
            m = re.match(r"^Changeset \[([\w]+)\]: (.*)$", item.title)
            if m:
                str_feed.append("Changeset:>> " + m.group(1))
                str_feed.append(m.group(2))

            str_feed.append("Link: " + item.link)
            str_feed.append('')

        return '\n'.join(str_feed)


class TracTimelineUI(UI):
    """ UI Manager for Timeline View """
    def __init__(self):
        self.timeline_window = TracTimelineWindow()

    def create(self):
        style = vim.eval('g:tracTimelineStyle')

        if style == 'right':
            self.timeline_window.create("vertical belowright new")
        elif style == 'bottom':
            self.timeline_window.create("belowright new")
        else:
            self.timeline_window.create("vertical aboveleft new")

    def destroy(self):
        self.timeline_window.destroy()


class TracTimelineWindow(NonEditableWindow):
    """ RSS Feed Window """
    def __init__(self, name='TIMELINE_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <c-]> '
                    ':python trac.wiki_view("<cword>")<cr>')
        #vim.command('vertical resize +70')
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal linebreak')
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.search_open(False)<cr>')
        vim.command('nnoremap <buffer> <space> '
                    ':python trac.search_open(True)<cr>')
        vim.command('setlocal noswapfile')


class Trac(object):
    """ Main Trac class """
    def __init__(self):
        """ initialize Trac """
        self.wiki = TracWiki()
        self.search = TracSearch()
        self.ticket = TracTicket()
        self.timeline = TracTimeline()

        self.uiwiki = TracWikiUI()
        self.uiserver = TracServerUI()
        self.uiticket = TracTicketUI()
        self.uisearch = TracSearchUI()
        self.uitimeline = TracTimelineUI()

        self.server_list = vim.eval('g:tracServerList')
        default_server = vim.eval('g:tracDefaultServer')
        comment = vim.eval('tracDefaultComment')
        if not comment:
            comment = 'VimTrac update'

        self.set_server(default_server)
        self.default_comment = comment

    def set_server(self, server):
        url = self.server_list[server]
        self.server_name = server
        self.server_url = {
            'scheme': url.get('scheme', 'http'),
            'server': url['server'],
            'rpc_path': url.get('rpc_path', 'login/rpc'),
            'auth': url.get('auth', ''),
        }
        scheme = url.get('scheme', 'http')
        auth = url.get('auth', '').split(':')

        if len(auth) == 2:  # Basic authentication
            url = '{scheme}://{auth}@{server}{rpc_path}'.format(**url)
        else:   # Anonymous or Digest authentication
            url = '{scheme}://{server}{rpc_path}'.format(**url)
        if len(auth) == 3:  # Digest authentication
            transport = HTTPDigestTransport(scheme, *auth)
            self.server = xmlrpclib.ServerProxy(url, transport=transport)
        else:
            self.server = xmlrpclib.ServerProxy(url)

        self.wiki.reset_attrs()
        self.ticket.reset_attrs()
        self.user = self.get_user()

    def wiki_view(self, page=False, direction=None):
        """ Creates The Wiki View """
        print 'Connecting...'
        if direction:
            current = self.wiki.visited_pages.index(self.wiki.current_page)
            try:
                page = self.wiki.visited_pages[current + direction]
            except IndexError:
                print 'Error: History out of range'
                return
        if page == 'CURRENTLINE':
            page = vim.current.line
        if not page:
            if self.wiki.current_page:
                page = self.wiki.current_page
            else:
                page = 'WikiStart'

        self.normal_view()

        self.uiwiki.open()
        self.uiwiki.tocwindow.write(self.wiki.get_all_pages())
        self.uiwiki.wikiwindow.write(self.wiki.get_page(page))

        self.wiki.list_attachments()

        if self.wiki.attachments:
            self.uiwiki.attachwindow.create('belowright 3 new')
            self.uiwiki.attachwindow.write("\n".join(self.wiki.attachments))
        self.uiwiki.wikiwindow.set_focus()

    def ticket_view(self, tid=False, cached=False, direction=None):
        """ Creates The Ticket View """
        print 'Connecting...'
        if tid == 'CURRENTLINE':
            tid = vim.current.line
            if 'Ticket:>>' in tid:
                tid = tid.replace('Ticket:>> ', '')
            else:
                print "Click within a tickets area"
                return

        if tid == 'SUMMARYLINE':
            m = re.search(r'^\s*([0123456789]+)', vim.current.line)
            try:
                tid = int(m.group(0))
            except:
                print 'no ticket selected'
                return

        if not tid:
            tid = self.ticket.current_ticket_id
        if direction:
            index = self.ticket.visited_tickets.index(tid)
            try:
                tid = self.ticket.visited_tickets[index + direction]
            except IndexError:
                print 'Error: History out of range'
                return

        self.normal_view()
        self.uiticket.open()

        self.uiticket.ticketwindow.write(self.ticket.get(tid))
        if self.ticket.attachments:
            self.uiticket.attachwindow.create('belowright 3 new')
            self.uiticket.attachwindow.write("\n".join(
                                             self.ticket.attachments))

        style = vim.eval('g:tracTicketStyle')
        if style == 'summary':
            self.uiticket.summarywindow.write(self.ticket.get_all(True,
                                                                  cached))
        else:
            self.uiticket.tocwindow.write(self.ticket.get_all(False, cached))

        if self.ticket.current_ticket_id:
            self.uiticket.ticketwindow.set_focus()

    def sort_ticket(self, sorter, attr):
        self.ticket.set_sort_attr(sorter, attr)
        self.ticket_view()

    def filter_ticket(self, attrib, value, ignore=False):
        self.ticket.filters[attrib] = '{0}{1}'.format('!' if ignore else '',
                                                      value)
        self.ticket_view()

    def filter_clear(self, attrib=None):
        if attrib:
            del self.ticket.filters[attrib]
        else:
            self.ticket.filters = {}
        self.ticket_view()

    def ticket_paginate(self, direction=1):
        try:
            self.ticket.page += direction
            self.ticket_view()
        except:
            self.ticket.page -= direction
            self.ticket_view()
            print 'cannot go beyond current page'

    def create_ticket(self, summary='new ticket', type_=False):
        """ writes comment window to a new  ticket  """
        if self.uiticket.mode == 0:
            print "Can't create a ticket when not in Ticket View"
            return

        description = self.uiticket.commentwindow.dump()
        if not description:
            print "Description is empty. Ticket needs more info"
            return

        if not confirm('Create ticket at {0}?'.format(self.server_name)):
            print 'Ticket creation cancelled.'
            return

        attribs = {'type': type_} if type_ else {}
        self.ticket.create(description, summary, attribs)
        self.ticket_view(trac.ticket.current_ticket_id)

    def update_ticket(self, option, value=None):
        tid = self.ticket.current_ticket_id
        if self.uiticket.mode == 0 or not tid:
            print "Cannot make changes when there is no current ticket open"
            return

        text = self.uiticket.commentwindow.dump()
        if option in ('summary', 'description'):
            value = text
            comment = ''
        else:
            comment = text
        attribs = {option: value} if value else {}
        if not any((comment, attribs)):
            print 'nothing to change'
            return

        if not confirm('Update ticket #{0}?'.format(tid)):
            print 'Update cancelled.'
            return

        self.ticket.update(comment, attribs, False)
        self.ticket_view(tid, True)

    def act_ticket(self, action):
        tid = self.ticket.current_ticket_id
        if self.uiticket.mode == 0 or not tid:
            print "Cannot make changes when there is no current ticket open"
            return
        if not confirm('Perform action on ticket #{0}?'.format(tid)):
            print 'Action cancelled.'
            return

        self.ticket.act(action, self.uiticket.commentwindow.dump())
        self.ticket_view(tid, True)

    def summary_view(self):
        self.uiticket.summarywindow.create('belowright 10 new')
        self.uiticket.summarywindow.write(self.ticket.get_all(True, False))

    def server_view(self):
        """ Display's The Server list view """
        self.uiserver.server_mode()
        servers = "\n".join(['{0}: {1}'.format(key, val['server']) for key, val
                             in self.server_list.iteritems()])
        self.uiserver.serverwindow.write(servers)

    def search_open(self, keyword, b_preview=False):
        line = vim.current.line

        if 'Ticket:>>' in line:
            self.ticket_view(line.replace('Ticket:>> ', ''))
        elif 'Wiki:>>' in line:
            if b_preview:
                self.html_view(line.replace('Wiki:>> ', ''))
            else:
                self.wiki_view(line.replace('Wiki:>> ', ''))
        elif 'Changeset:>>' in line:
            self.changeset_view(line.replace('Changeset:>> ', ''))

    def search_view(self, keyword):
        """  run a search """
        print 'Connecting...'
        self.normal_view()
        output_string = self.search.search(keyword)
        self.uisearch.open()
        self.uisearch.searchwindow.write(output_string)

    def timeline_view(self):
        print 'Connecting...'
        self.normal_view()
        output_string = self.timeline.read_timeline(self.server_url)
        self.uitimeline.open()
        self.uitimeline.timeline_window.write((output_string))

    def get_user(self, server_url=None):
        if not server_url:
            server_url = self.server_url
        return server_url.get('auth', '').split(':')[0]

    def normal_view(self):
        self.uiserver.normal_mode()
        self.uiwiki.normal_mode()
        self.uiticket.normal_mode()
        self.uisearch.normal_mode()
        self.uitimeline.normal_mode()

    def add_attachment(self, file):
        """ add an attachment to current wiki / ticket """
        if self.uiwiki.mode == 1:
            print "Adding attachment to wiki", self.wiki.current_page
            self.wiki.add_attachment(file)
            self.wiki_view()
            print 'Done.'
        elif self.uiticket.mode == 1:
            print "Adding attachment to ticket", self.ticket.current_ticket_id
            comment = self.uiticket.commentwindow.dump()
            self.ticket.add_attachment(file, comment)
            self.ticket_view()
            print 'Done.'
        else:
            print "You need an active ticket or wiki open!"
            return

    def get_attachment(self, file):
        """ retrieves attachment """
        if file == 'CURRENTLINE':
            file = vim.current.line

        if self.uiwiki.mode == 1:
            print "Retrieving attachment from wiki", self.wiki.current_page
            self.wiki.get_attachment(file)
            print 'Done.'
        elif self.uiticket.mode == 1:
            print "Retrieving attachment from ticket",
            print self.ticket.current_ticket_id
            self.ticket.get_attachment(file)
            print 'Done.'
        else:
            print "You need an active ticket or wiki open!"

    def list_attachments(self):
        if self.uiwiki.mode == 1:
            option = self.wiki.attachments
            print self.wiki.attachments
        elif self.uiticket.mode == 1:
            option = self.ticket.attachments
        else:
            print "You need an active ticket or wiki open!"

        vim.command('let g:tracOptions = "' + "|".join(option) + '"')

    def preview(self, b_dump=False):
        """ browser view of current wiki buffer """
        if self.uiwiki.mode == 1 and self.wiki.current_page:
            print "Retrieving preview from wiki", self.wiki.current_page
            wikitext = self.uiwiki.wikiwindow.dump()
        elif self.uiticket.mode == 1 and self.ticket.current_ticket_id:
            print "Retrieving preview from ticket",
            print self.ticket.current_ticket_id
            wikitext = self.uiticket.commentwindow.dump()
        else:
            print "You need an active ticket or wiki open!"
            return

        html = self.wiki.get_wiki_html(wikitext)
        file_name = vim.eval('g:tracTempHtml')
        with codecs.open(file_name, 'w', 'utf-8') as fp:
            fp.write(html)

        if b_dump:
            #self.normal_view()
            #vim.command('split')
            vim.command('enew')
            vim.command('setlocal buftype=nofile')
            vim.command('r!lynx -dump ' + file_name)
            vim.command('set ft=text')
            vim.command('norm gg')
        else:
            browser = vim.eval('g:tracBrowser')
            vim.command('!{0} file://{1}'.format(browser, file_name))

    def changeset_view(self, changeset):
        print 'Connecting...'
        changeset = '{scheme}://{server}/changeset/{changeset}'.format(
                changeset=changeset, **self.server_url)

        self.normal_view()
        vim.command('belowright split')
        vim.command('enew')
        vim.command("setlocal buftype=nofile")
        vim.command('silent Nread ' + changeset + '?format=diff')
        vim.command('set ft=diff')


def trac_init():
    """ Initialize Trac Environment """
    global trac
    trac = Trac()
