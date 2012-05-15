# -*- encoding: utf-8 -*-

import os
import vim
import xmlrpclib
import re
import codecs


trac, browser, mode = [None] * 3


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
        import urllib2
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


class TracRPC(object):
    """ General xmlrpc RPC routines """
    def __init__(self, server_url):
        if 'server' in server_url:
            self.set_server(server_url)
        else:
            print 'Please provide your trac server address'

    def set_server(self, url):
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


class VimWindow(object):
    """ wrapper class of window of vim """
    def __init__(self, name='WINDOW'):
        self.name = name
        self.buffer = []
        self.firstwrite = True

    def prepare(self):
        """ check window is OK, if not then create """
        if not all([self.buffer, self.get_winnr() > 0]):
            self.create()
        self.set_focus()

    def on_create(self):
        """ On Create is used  by the VimWindow subclasses to define vim
            mappings and buffer settings
        """

    def get_winnr(self):
        """ Returns the vim window number for wincmd calls """
        return int(vim.eval("bufwinnr('{0}')".format(self.name)))

    def write(self, msg):
        """ write to a vim buffer """
        if not isinstance(msg, basestring):
            msg = str(msg)
        self.prepare()
        if self.firstwrite:
            self.firstwrite = False
            msg = msg.encode('utf-8', 'ignore')
            self.buffer[:] = msg.split('\n')
        else:
            self.buffer.append(msg.split('\n'))
        self.command('normal gg')
        self.on_write()

    def on_before_write(self):
        """ for vim commands before a write is made to a buffer """

    def on_write(self):
        """ for vim commands after a write is made to a buffer """

    def dump(self):
        """ returns the contents buffer as a string """
        return "\n".join(self.buffer)

    def create(self, method='new'):
        """ creates a  window """
        vim.command('silent {0} {1}'.format(method, self.name))
        vim.command("setlocal buftype=nofile")
        self.buffer = vim.current.buffer

        self.width = int(vim.eval("winwidth(0)"))
        self.height = int(vim.eval("winheight(0)"))
        self.on_create()

    def destroy(self):
        """ destroy window """
        if not self.buffer:
            return
        self.command('bdelete {0}'.format(self.name))
        self.firstwrite = True

    def clean(self):
        """ clean all datas in buffer """
        self.prepare()
        self.buffer[:] = []
        self.firstwrite = True

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
    def on_before_write(self):
        vim.command("setlocal modifiable")

    def on_write(self):
        vim.command("setlocal nomodifiable")

    def clean(self):
        """ clean all datas in buffer """
        self.prepare()
        vim.command('setlocal modifiable')
        self.buffer[:] = []
        self.firstwrite = True


class UI(object):
    """ User Interface Base Class """
    def open(self):
        """ change mode to a vim window view """
        if self.mode == 1:  # is wiki mode ?
            return
        self.mode = 1
        self.create()

    def normal_mode(self):
        """ restore mode to normal """
        if self.mode == 0:  # is normal mode ?
            return
        self.destroy()
        self.mode = 0
        self.cursign = None


class TracWiki(TracRPC):
    """ Trac Wiki Class """
    def __init__(self, server_url):
        TracRPC.__init__(self, server_url)
        self.pages = []
        self.revision = 1
        self.current_page = False
        self.visited_pages = []

    def get_all_pages(self):
        """ Gets a List of Wiki Pages """
        self.pages = self.server.wiki.getAllPages()
        return "\n".join(self.pages)

    def get_page(self, name, revision=None):
        """ Get Wiki Page """
        try:
            name = name.strip()
            self.current_page = name
            if name not in self.visited_pages:
                self.visited_pages.append(name)
            if revision is not None:
                wikitext = self.server.wiki.getPage(name, revision)
            else:
                wikitext = self.server.wiki.getPage(name)
        except:
            wikitext = "Describe {0} here.".format(name)
        return wikitext

    def save(self,  comment):
        """ Saves a Wiki Page """
        global trac
        if not comment:
            comment = trac.default_comment
        self.server.wiki.putPage(self.current_page,
                trac.uiwiki.wikiwindow.dump(), {"comment": comment})

    def get_page_info(self):
        """ Returns page revision info most recent author """
        try:
            info = self.server.wiki.getPageInfo(self.current_page)
            self.revision = info['version']
            return '{name} v{version}, author: {author}'.format(**info)
        except:
            return 'Cannot get page info'

    def create_page(self, name, content, comment):
        """ Saves a Wiki Page """
        return self.server.wiki.putPage(name, content, {"comment": comment})

    def add_attachment(self, file):
        """ Add attachment """
        file_name = os.path.basename(file)
        path = '{0}/{1}'.format(self.current_page, file_name)
        self.server.wiki.putAttachment(path,
                xmlrpclib.Binary(open(file).read()))

    def get_attachment(self, file):
        """ Get attachment """
        buffer = self.server.wiki.getAttachment(file)
        file_name = os.path.basename(file)

        if os.path.exists(file_name):
            print "Will not overwrite existing file {0}".format(file_name)
        else:
            with open(file_name, 'w') as fp:
                fp.write(buffer.data)

    def list_attachments(self):
        """ Look for attachments on the current page """
        self.attachments = self.server.wiki.listAttachments(self.current_page)

    def get_wiki_html(self, wikitext):
        """ Converts the wikitext from a buffer to html for previews """
        return self.server.wiki.wikiToHtml(wikitext)

    def html_view(self, page=None):
        """ Displays a wiki in a preview browser as set in trac.vim """
        if not page:
            page = vim.current.line

        html = self.server.wiki.getPageHTML(page)
        file_name = vim.eval('g:tracTempHtml')
        with codecs.open(file_name, 'w', 'utf-8') as fp:
            fp.write(html)

        global browser
        vim.command('!{0} file://{1}'.format(browser, file_name))

    def get_options(self):
        """ returns a list of a sites wiki pages for command completes """
        vim.command('let g:tracOptions="{0}"'.format("|".join(self.pages)))

    def vim_diff(self, revision=None):
        """ Creates a vimdiff of an earlier wiki revision """
        global trac
        #default to previous revision
        if revision is None:
            revision = self.revision - 1

        diffwindow = WikiVimDiffWindow()
        diffwindow.create('vertical belowright diffsplit')

        wikitext = self.get_page(self.current_page, revision)
        if wikitext:
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
        self.wiki_attach_window = WikiAttachmentWindow()
        self.mode = 0  # Initialised to default

    def destroy(self):
        """ destroy windows """
        self.wikiwindow.destroy()
        self.tocwindow.destroy()
        self.wiki_attach_window.destroy()

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
            (':q<cr>', ':python trac.normal_view()<cr>'),
            ('<2-LeftMouse>', ':python trac.wiki_view("<C-R><C-W>")<cr>'),
            ('gf', '<c-w><c-f><c-w>K'),
        ]
        for m in nmaps:
            vim.command('nnoremap <buffer> {0} {1}'.format(*m))
        vim.command('vertical resize +70')
        vim.command('nnoremap <buffer> :w<cr> :TWSave<cr>')
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
            (':q<cr>', ':python trac.normal_view()<cr>'),
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


class WikiAttachmentWindow(NonEditableWindow):
    """ Wiki's attachments """
    def __init__(self, name='WIKIATT_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.get_attachment("CURRENTLINE")<cr>')
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
        #vim.command('setlocal winwidth=30')
        #vim.command('vertical resize 30')
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


class TracSearch(TracRPC):
    """ Search for tickets and Wiki's """
    def __init__(self, server_url):
        TracRPC.__init__(self, server_url)

    def search(self, search_pattern):
        """ Perform a search call  """
        a_search = self.server.search.performSearch(search_pattern)
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
        self.mode = 0

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
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
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


class TracTicket(TracRPC):
    """ Trac Ticket Class """
    def __init__(self, server_url):
        TracRPC.__init__(self, server_url)
        self.current_ticket_id = False
        self.attribs = []
        self.tickets = []
        self.sorter = {'order': 'priority', 'group': 'milestone'}
        self.page = 1
        self.filter = TracTicketFilter()

    def get_attribs(self):
        """ Get all milestone/ priority /status options """
        multicall = xmlrpclib.MultiCall(self.server)
        multicall.ticket.milestone.getAll()
        multicall.ticket.type.getAll()
        multicall.ticket.status.getAll()
        multicall.ticket.resolution.getAll()
        multicall.ticket.priority.getAll()
        multicall.ticket.severity.getAll()
        multicall.ticket.component.getAll()
        multicall.ticket.version.getAll()

        attribs = []
        for option in multicall():
            attribs.append(option)

        for milestone in attribs[0]:
            multicall.ticket.milestone.get(milestone)

        attribs.append(multicall())
        self.attribs = attribs

    def set_sort_attr(self, attrib, value):
        self.sorter[attrib] = value

    def number_tickets(self):
        clause = 'max=0&order={order}&group={group}&page={page}'
        clause = clause.format(page=self.page, **self.sorter)
        clause = '{0}&{1}'.format(clause, vim.eval('g:tracTicketClause'))
        return len(self.server.ticket.query(clause))

    def get_all_tickets(self, summary=True, b_use_cache=False):
        """ Gets a List of Ticket Pages """
        if not self.attribs:
            self.get_attribs()

        if b_use_cache:
            tickets = self.tickets
        else:
            multicall = xmlrpclib.MultiCall(self.server)
            clause = 'order={order}&group={group}&page={page}'
            clause = clause.format(page=self.page, **self.sorter)
            clause = '{0}&{1}'.format(clause, vim.eval('g:tracTicketClause'))
            for ticket in self.server.ticket.query(clause):
                multicall.ticket.get(ticket)
            tickets = multicall()
            self.tickets = tickets

        if summary:
            ticket_list = []
        else:
            ticket_list = ["Hit <enter> or <space> on a line containing :>>"]
            if self.filter.filters:
                ticket_list.append("(filtered)")
                ticket_list.append(self.filter.list())

        for ticket in tickets:
            if ticket[3]["status"] != "closed" and self.filter.check(ticket):
                if summary:
                    str_ticket = [str(ticket[0])]
                else:
                    str_ticket = [""]
                    str_ticket.append("Ticket:>> {0}".format(ticket[0]))
                for f in ('summary', 'priority', 'status', 'component',
                          'milestone', 'type', 'version', 'owner'):
                    v = truncate_words(ticket[3].get(f, ''))
                    if not summary:
                        v = "   * {0}: {1}".format(f.title(), v)
                    str_ticket.append(v)

                if not summary and self.session_is_present(ticket[0]):
                    str_ticket.append("   * Session: PRESENT")
                separator = ' || ' if summary else '\n'
                ticket_list.append(separator.join(str_ticket))

        return "\n".join(ticket_list)

    def get_ticket(self, id):
        """ Get Ticket Page """
        try:
            id = int(id)
            ticket = self.server.ticket.get(id)
            ticket_changelog = self.server.ticket.changeLog(id)
            actions = self.server.ticket.getActions(id)
        except:
            return 'Please select a ticket'

        self.current_ticket_id = id
        self.current_component = ticket[3].get("component")
        self.list_attachments()

        str_ticket = ["= Ticket Summary =", ""]
        str_ticket.append(" *   Ticket ID: {0}".format(ticket[0]))
        for f in ('owner', 'reporter', 'status', 'summary', 'type', 'priority',
                  'component', 'milestone', 'version'):
            v = ticket[3].get(f, '')
            str_ticket.append(" *{0:>12}: {1}".format(f.title(), v))

        if self.session_is_present():
            str_ticket.append(" *     Session: PRESENT")

        str_ticket.append(" * Attachments: ")
        str_ticket.append(', '.join(self.attachments))

        str_ticket.append("")
        str_ticket.append("= Description: =")
        str_ticket.append("")
        str_ticket.append(ticket[3]["description"])
        str_ticket.append("")
        str_ticket.append("= Changelog =")

        import datetime
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
            str_ticket.append(' > {action[0]}'.format(action=action))

        return '\n'.join(str_ticket)

    def update_ticket(self, comment, attribs={}, notify=False):
        """ add ticket comments change attributes """
        return self.server.ticket.update(self.current_ticket_id, comment,
                                         attribs, notify)

    def create_ticket(self, description, summary, attributes={}):
        """ create a trac ticket """
        self.current_ticket_id = self.server.ticket.create(summary,
                description, attributes, False)

    def add_attachment(self, file):
        """ Add attachment """
        file_name = os.path.basename(file)
        self.server.ticket.putAttachment(self.current_ticket_id, file_name,
                'attachment', xmlrpclib.Binary(open(file).read()))

    def list_attachments(self):
        a_attach = self.server.ticket.listAttachments(self.current_ticket_id)
        self.attachments = []
        for attach in a_attach:
            self.attachments.append(attach[0])

    def get_options(self, op_id):
        vim.command('let g:tracOptions="{0}"'.format("|".join(
                                                     self.attribs[op_id])))

    def get_attachment(self, file):
        """ Get attachment """
        buffer = self.server.ticket.getAttachment(self.current_ticket_id, file)
        file_name = os.path.basename(file)

        if os.path.exists(file_name):
            print "Will not overwrite existing file", file_name
        else:
            with open(file_name, 'w') as fp:
                fp.write(buffer.data)

    def set_attr(self, option, value):
        global trac
        if not value:
            print option, "was empty. No changes made."
            return

        if trac.uiticket.mode == 0 or not trac.ticket.current_ticket_id:
            print "Cannot make changes when there is no current ticket open"
            return

        comment = trac.uiticket.commentwindow.dump()
        trac.uiticket.commentwindow.clean()
        attribs = {value: option}
        trac.ticket.update_ticket(comment, attribs, False)
        trac.ticket_view(trac.ticket.current_ticket_id, True)

    def add_comment(self):
        """ Adds Comment window comments to the current ticket """
        global trac
        if trac.uiticket.mode == 0 or not trac.ticket.current_ticket_id:
            print "Cannot make changes when there is no current ticket is open"
            return

        comment = trac.uiticket.commentwindow.dump()
        attribs = {}

        if not comment:
            print "Comment window is empty. Not adding to ticket"

        trac.ticket.update_ticket(comment, attribs, False)
        trac.uiticket.commentwindow.clean()
        trac.ticket_view(trac.ticket.current_ticket_id)

    def update_description(self):
        """ Adds Comment window as a description to the current ticket """
        global trac
        confirm = vim.eval(
                'confirm("Overwrite Description?", "&Yes\n&No\n", 2)')
        if int(confirm) == 2:
            print "Cancelled."
            return

        if trac.uiticket.mode == 0 or not trac.ticket.current_ticket_id:
            print "Cannot make changes when there is no current ticket is open"
            return

        comment = trac.uiticket.commentwindow.dump()
        attribs = {'description': comment}
        if not comment:
            print "Comment window is empty. Not adding to ticket"

        trac.ticket.update_ticket('', attribs, False)
        trac.uiticket.commentwindow.clean()
        trac.ticket_view(trac.ticket.current_ticket_id)

    def create(self, summary='new ticket', type=False, server=False):
        """ writes comment window to a new  ticket  """
        global trac
        #Used in quick tickets
        if server:
            trac.set_current_server(server, True, 'ticket')
            description = ''
        else:
            description = trac.uiticket.commentwindow.dump()

        if trac.uiticket.mode == 0 and not server:
            print "Can't create a ticket when not in Ticket View"
            return

        confirm = vim.eval('confirm("Create Ticket on ' + trac.server_name +
                           '?", "&Yes\n&No\n", 2)')
        if int(confirm) == 2:
            print "Cancelled."
            return

        if type:
            attribs = {'type': type}
        else:
            attribs = {}

        if not description:
            print "Description is empty. Ticket needs more info"

        trac.ticket.create_ticket(description, summary, attribs)
        trac.uiticket.commentwindow.clean()
        trac.ticket_view(trac.ticket.current_ticket_id)

    def close_ticket(self, comment):
        self.update_ticket(comment, {'status': 'closed'})

    def resolve_ticket(self, comment, resolution):
        self.update_ticket(comment, {'status': 'closed',
                                    'resolution': resolution})

    def session_save(self):
        global trac
        if not self.current_ticket_id:
            print "You need to have an active ticket"
            return

        directory = vim.eval('g:tracSessionDirectory')
        if os.path.isfile(directory):
            print "Cant create session directory"
            return

        if not os.path.isdir(directory):
            os.mkdir(directory)

        serverdir = re.sub(r'[^\w]', '', trac.server_name)

        if not os.path.isdir(directory + '/' + serverdir):
            os.mkdir(directory + '/' + serverdir)

        sessfile = directory + '/' + serverdir + "/vimsess." \
                + str(self.current_ticket_id)
        vim.command('mksession! ' + sessfile)
        print "Session file Created: " + sessfile

    def session_load(self):
        global trac
        if not self.current_ticket_id:
            print "You need to have an active ticket"
            return

        serverdir = re.sub(r'[^\w]', '', trac.server_name)
        directory = vim.eval('g:tracSessionDirectory')
        sessfile = directory + '/' + serverdir + "/vimsess." \
                + str(self.current_ticket_id)

        if not os.path.isfile(sessfile):
            print "This ticket does not have a session: " + sessfile
            return

        vim.command("bdelete TICKETTOC_WINDOW")
        vim.command("bdelete TICKET_WINDOW")
        vim.command("bdelete TICKET_COMMENT_WINDOW")
        vim.command('source ' + sessfile)
        vim.command("bdelete TICKETTOC_WINDOW")
        vim.command("bdelete TICKET_WINDOW")
        vim.command("bdelete TICKET_COMMENT_WINDOW")
        trac.ticket_view(self.current_ticket_id)

    def session_component_save(self, component=False):
        """ Save a session based on the component supplied or the current
        ticket """
        global trac
        if not component:
            if not self.current_component:
                print "You need an active ticket or a component as an argument"
                return
            else:
                component = self.current_component

        directory = vim.eval('g:tracSessionDirectory')
        if os.path.isfile(directory):
            print "Cant create session directory"
            return

        if not os.path.isdir(directory):
            os.mkdir(directory)

        serverdir = re.sub(r'[^\w]', '', trac.server_name)
        component = re.sub(r'[^\w]', '', component)

        if not os.path.isdir(directory + '/' + serverdir):
            os.mkdir(directory + '/' + serverdir)

        sessfile = directory + '/' + serverdir + "/vimsess." + str(component)
        vim.command('mksession! ' + sessfile)
        print "Session file Created: " + sessfile

    def session_component_load(self, component):
        """ Loads a session based on the component supplied or the current
        ticket """
        global trac
        if not component:
            if not self.current_componentd:
                print "You need an active ticket or a component as an argument"
                return
            else:
                component = self.current_component

        serverdir = re.sub(r'[^\w]', '', trac.server_name)
        component = re.sub(r'[^\w]', '', component)
        directory = vim.eval('g:tracSessionDirectory')
        sessfile = directory + '/' + serverdir + "/vimsess." + str(component)

        if not os.path.isfile(sessfile):
            print "This ticket does not have a session: " + sessfile
            return

        vim.command("bdelete TICKETTOC_WINDOW")
        vim.command("bdelete TICKET_WINDOW")
        vim.command("bdelete TICKET_COMMENT_WINDOW")
        vim.command('source ' + sessfile)
        vim.command("bdelete TICKETTOC_WINDOW")
        vim.command("bdelete TICKET_WINDOW")
        vim.command("bdelete TICKET_COMMENT_WINDOW")
        trac.ticket_view(self.current_ticket_id)

    def get_session_file(self, id=None):
        global trac
        if not id:
            id = self.current_ticket_id

        directory = vim.eval('g:tracSessionDirectory')
        serverdir = re.sub(r'[^\w]', '', trac.server_name)
        return directory + '/' + serverdir + "/vimsess." + str(id)

    def session_is_present(self, id=None):
        sessfile = self.get_session_file(id)
        return  os.path.isfile(sessfile)

    def set_summary(self, summary):
        confirm = vim.eval('confirm("Overwrite Summary?", "&Yes\n&No\n", 2)')
        if int(confirm) == 2:
            print "Cancelled."
            return
        attribs = {'summary': summary}
        trac.ticket.update_ticket('', attribs, False)

    def context_set(self):
        line = vim.current.line
        if re.match("Milestone:", line):
            self.get_options(0)
        elif re.match("Type:", line):
            self.get_options(1)
        elif re.match("Status:", line):
            self.get_options(2)
        elif re.match("Resolution:", line):
            self.get_options(3)
        elif re.match("Priority:", line):
            self.get_options(4)
        elif re.match("Severity:", line):
            self.get_options(5)
        elif re.match("Component:", line):
            self.get_options(6)
        else:
            print "This only works on ticket property lines"
            return
        self.get_options(0)
        vim.command('setlocal modifiable')
        setting = vim.eval("complete(col('.'), g:tracOptions)")
        print setting

    def summary_view(self):
        global trac
        trac.uiticket.summarywindow.create('belowright 10 new')
        trac.uiticket.summarywindow.write(self.get_all_tickets(True, False))
        trac.uiticket.mode = 2


class TracTicketFilter:
    def __init__(self):
        self.filters = []

    def add(self,  keyword, attribute, b_whitelist=True,
            b_refresh_ticket=True):
        self.filters.append({'attr': attribute, 'key': keyword,
                             'whitelist': b_whitelist})
        if b_refresh_ticket:
            self.refresh_tickets()

    def clear(self):
        self.filters = []
        self.refresh_tickets()

    def delete(self, number):
        number = int(number)
        try:
            del self.filters[number - 1]
        except:
            return
        self.refresh_tickets()

    def list(self):
        if not self.filters:
            return ''

        i = 0
        str_list = ""
        for filter in self.filters:
            i += 1
            is_whitelist = 'whitelist'
            if not filter['whitelist']:
                is_whitelist = 'blacklist'
            str_list += '    ' + str(i) + '. ' + filter['attr'] + ': ' \
                    + filter['key'] + " : " + is_whitelist + "\n"

        return str_list

    def check(self, ticket):
        for filter in self.filters:
            if ticket[3][filter['attr']] == filter['key']:
                if not filter['whitelist']:
                    return False
            else:
                if filter['whitelist']:
                    return False
        return True

    def refresh_tickets(self):
        global trac
        trac.ticket_view(trac.ticket.current_ticket_id, True)


class TracTicketUI(UI):
    """ Trac Wiki User Interface Manager """
    def __init__(self):
        """ Initialize the User Interface """
        self.ticketwindow = TicketWindow()
        self.tocwindow = TicketTOContentsWindow()
        self.commentwindow = TicketCommentWindow()
        self.summarywindow = TicketSummaryWindow()
        self.mode = 0

    def normal_mode(self):
        """ restore mode to normal """
        if self.mode == 0:
            return

        if self.mode == 2:
            self.summarywindow.destroy()
            return

        # destory all created windows
        self.destroy()
        self.mode = 0
        self.cursign = None

    def destroy(self):
        """ destroy windows """
        vim.command("call UnloadTicketCommands()")

        self.ticketwindow.destroy()
        self.tocwindow.destroy()
        self.commentwindow.destroy()
        self.summarywindow.destroy()

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


class TicketSummaryWindow(VimWindow):
    """ Ticket Table Of Contents """
    def __init__(self, name='TICKETSUMMARY_WINDOW'):
        VimWindow.__init__(self, name)

    def on_create(self):
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.ticket_view("SUMMARYLINE")<cr>')
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
        vim.command('nnoremap <buffer> <2-LeftMouse> '
                    ':python trac.ticket_view("SUMMARYLINE")<cr>')
        vim.command('setlocal cursorline')
        vim.command('setlocal linebreak')
        vim.command('setlocal syntax=text')
        vim.command('setlocal foldmethod=indent')
        vim.command('setlocal nowrap')
        vim.command('silent norm gg')
        vim.command('setlocal noswapfile')

    def on_write(self):
        try:
            vim.command('%Align ||')
        except:
            vim.command('echo install Align for the best view of summary')
        vim.command('syn match Ignore /||/')
        #vim.command("setlocal nomodifiable")
        vim.command('norm gg')


class TicketWindow(NonEditableWindow):
    """ Ticket Window """
    def __init__(self, name='TICKET_WINDOW'):
        NonEditableWindow.__init__(self, name)

    def on_create(self):
        vim.command('setlocal noswapfile')
        vim.command('setlocal textwidth=100')
        #vim.command('nnoremap <buffer> <c-]> '
        #            ':python trac_ticket_view("CURRENTLINE") <cr>')
        #vim.command('resize +20')
        #vim.command('nnoremap <buffer> :w<cr> :TracSaveTicket<cr>')
        #vim.command('nnoremap <buffer> :wq<cr> '
        #            ':TracSaveTicket<cr>:TracNormalView<cr>')
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
        #map gf to a new buffer(switching buffers doesnt work with nofile)
        vim.command('nnoremap <buffer> gf <c-w><c-f><c-w>K')
        #vim.command('setlocal linebreak')
        vim.command('setlocal syntax=tracwiki')
        vim.command('nnoremap <buffer> <c-p> '
                    ':python trac.ticket.context_set()<cr>')


class TicketCommentWindow(VimWindow):
    """ For adding Comments to tickets """
    def __init__(self, name='TICKET_COMMENT_WINDOW'):
        VimWindow.__init__(self, name)

    def on_create(self):
        nmaps = [
            (':w<cr>', ':python trac.ticket.add_comment()<cr>'),
            (':wq<cr>', ':python trac.ticket.add_comment()<cr>'
                        ':python trac.normal_view()<cr>'),
            (':q<cr>', ':python trac.normal_view()<cr>'),
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
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
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
        self.mode = 0

    def server_mode(self):
        """ Displays server mode """
        self.create()
        vim.command('2wincmd w')  # goto srcview window(nr=1, top-left)
        self.cursign = '1'

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

    def on_create(self):
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')


class TracTimeline:
    def read_timeline(self):
        """ Call the XML Rpc list """
        global trac
        try:
            import feedparser
        except ImportError:
            print "Please install feedparser.py!"
            return

        from time import strftime
        import re

        query = 'ticket=on&changeset=on&wiki=on&max=50&daysback=90&format=rss'
        feed = '{scheme}://{server}/timeline?{query}'.format(query=query,
                                                        **trac.wiki.server_url)
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
        self.mode = 0

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
        vim.command('nnoremap <buffer> :q<cr> :python trac.normal_view()<cr>')
        #vim.command('vertical resize +70')
        vim.command('setlocal syntax=tracwiki')
        vim.command('setlocal linebreak')
        vim.command('nnoremap <buffer> <cr> '
                    ':python trac.search_open(False)<cr>')
        vim.command('nnoremap <buffer> <space> '
                    ':python trac.search_open(True)<cr>')
        vim.command('setlocal noswapfile')


class Trac:
    """ Main Trac class """
    def __init__(self, comment, server_list):
        """ initialize Trac """
        self.server_list = server_list
        self.server_url = server_list.values()[0]
        self.server_name = server_list.keys()[0]

        self.default_comment = comment

        self.wiki = TracWiki(self.server_url)
        self.search = TracSearch(self.server_url)
        self.ticket = TracTicket(self.server_url)
        self.timeline = TracTimeline()

        self.uiwiki = TracWikiUI()
        self.uiserver = TracServerUI()
        self.uiticket = TracTicketUI()
        self.uisearch = TracSearchUI()
        self.uitimeline = TracTimelineUI()

        self.user = self.get_user(self.server_url)

    def wiki_view(self, page=False, direction=False):
        """ Creates The Wiki View """
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
        self.uiwiki.tocwindow.clean()
        self.uiwiki.tocwindow.write(self.wiki.get_all_pages())
        self.uiwiki.wikiwindow.clean()
        self.uiwiki.wikiwindow.write(self.wiki.get_page(page))

        self.wiki.list_attachments()

        if self.wiki.attachments:
            self.uiwiki.wiki_attach_window.create('belowright 3 new')
            self.uiwiki.wiki_attach_window.write("\n".join(
                                                    self.wiki.attachments))
        self.uiwiki.wikiwindow.set_focus()

    def ticket_view(self, id=False, b_use_cache=False):
        """ Creates The Ticket View """
        print 'Connecting...'
        if id == 'CURRENTLINE':
            id = vim.current.line
            if 'Ticket:>>' in id:
                id = id.replace('Ticket:>> ', '')
            else:
                print "Click within a tickets area"
                return

        if id == 'SUMMARYLINE':
            m = re.search(r'^([0123456789]+)', vim.current.line)
            id = int(m.group(0))

        if not id:
            id = self.ticket.current_ticket_id

        self.normal_view()
        self.uiticket.open()

        style = vim.eval('g:tracTicketStyle')
        if style == 'summary':
            self.uiticket.summarywindow.clean()
            self.uiticket.summarywindow.write(self.ticket.get_all_tickets(True,
                                                b_use_cache))
        else:
            self.uiticket.tocwindow.clean()
            self.uiticket.tocwindow.write(self.ticket.get_all_tickets(False,
                                                b_use_cache))

        self.uiticket.ticketwindow.clean()
        self.uiticket.ticketwindow.write(self.ticket.get_ticket(id))
        #self.ticket.list_attachments()

        if not self.ticket.attribs:
            self.ticket.get_attribs()

    def sort_ticket(self, sorter, attr):
        self.ticket.set_sort_attr(sorter, attr)
        self.ticket_view()

    def ticket_paginate(self, direction=1):
        try:
            self.ticket.page += direction
            self.ticket_view()
        except:
            self.ticket.page -= direction
            print 'cannot go beyond current page'

    def server_view(self):
        """ Display's The Server list view """
        self.uiserver.server_mode()
        self.uiserver.serverwindow.clean()
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
        self.normal_view()
        output_string = self.search.search(keyword)
        self.uisearch.open()
        self.uisearch.searchwindow.clean()
        self.uisearch.searchwindow.write(output_string)

    def timeline_view(self):
        self.normal_view()
        output_string = self.timeline.read_timeline()
        self.uitimeline.open()
        self.uitimeline.timeline_window.clean()
        self.uitimeline.timeline_window.write((output_string))

    def set_current_server(self, server_key, quiet=False, view=False):
        """ Sets the current server key """
        self.ticket.current_ticket_id = False
        self.wiki.current_page = False

        self.server_url = self.server_list[server_key]
        self.server_name = server_key
        self.user = self.get_user(self.server_url)

        self.wiki.set_server(self.server_url)
        self.ticket.set_server(self.server_url)
        self.search.set_server(self.server_url)

        self.user = self.get_user(self.server_url)

        trac.normal_view()

        if not quiet:
            print "SERVER SET TO : " + server_key

            #Set view to default or custom
            if not view:
                view = vim.eval('g:tracDefaultView')

            {'wiki': self.wiki_view,
             'ticket': self.ticket_view,
             'timeline': self.timeline_view,
            }[view]()

    def get_user(self, server_url):
        return server_url.get('auth', '').split(':')[0]

    def normal_view(self):
        trac.uiserver.normal_mode()
        trac.uiwiki.normal_mode()
        trac.uiticket.normal_mode()
        trac.uisearch.normal_mode()
        trac.uitimeline.normal_mode()

    def add_attachment(self, file):
        """ add an attachment to current wiki / ticket """
        if self.uiwiki.mode == 1:
            print "Adding attachment to wiki", self.wiki.current_page
            self.wiki.add_attachment(file)
            print 'Done.'
        elif self.uiticket.mode == 1:
            print "Adding attachment to ticket", self.ticket.current_ticket_id
            self.ticket.add_attachment(file)
            print 'Done.'
        else:
            print "You need an active ticket or wiki open!"

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
        global browser
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
            vim.command('!' + browser + " file://" + file_name)

    def changeset_view(self, changeset):
        changeset = '{scheme}://{server}/changeset/{changeset}'.format(
                changeset=changeset, **self.wiki.server_url)

        self.normal_view()
        vim.command('belowright split')
        vim.command('enew')
        vim.command("setlocal buftype=nofile")
        vim.command('silent Nread ' + changeset + '?format=diff')
        vim.command('set ft=diff')


def trac_init():
    """ Initialize Trac Environment """
    global trac
    global browser

    # get needed vim variables
    comment = vim.eval('tracDefaultComment')
    if not comment:
        comment = 'VimTrac update'

    server_list = vim.eval('g:tracServerList')
    trac = Trac(comment, server_list)
    browser = vim.eval('g:tracBrowser')


def trac_window_resize():
    global mode
    mode = (mode + 1) % 3
    vim.command("wincmd {0}".format(['=', '|', '_'][mode]))
