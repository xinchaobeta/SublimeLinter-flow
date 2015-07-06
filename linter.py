#
# linter.py
# Linter for SublimeLinter3, a code checking framework for Sublime Text 3
#
# Written by Clifton Kaznocha
# Copyright (c) 2014 Clifton Kaznocha
#
# License: MIT
#

"""This module exports the Flow plugin class."""

import sublime, sublime_plugin
from SublimeLinter.lint import Linter, persist, highlight

FLOW_REGION_KEY = 'sublimelinter-flow-{}-marks'.format(highlight.ERROR)
FLOW_MARK_SCOPE = highlight.MARK_SCOPE_FORMAT.format(highlight.ERROR)
FLOW_MARK_ICON  = persist.gutter_marks[highlight.ERROR]
FlOW_MARK_FLAGS = highlight.MARK_STYLES[persist.settings.get('mark_style', 'outline')]

def clear_view(view):
    view.erase_regions(FLOW_REGION_KEY)

class Flow_error:
  last_instance = None

  def __init__(self, json_output, file):
    if self.last_instance:
        self.last_instance.clear()
    Flow_error.last_instance = self

    self.output = json_output
    self.file = file
    if not self.output["passed"]: 
        error, self.index = self.get_error()
        self.msgs = [Flow_msg(msg) for msg in error['message']] if error else []
    else:
        self.msgs = []

  def on_view_ready(self, callback):
    rest = len(self.msgs)
    def check():
        nonlocal rest
        rest -= 1
        rest or callback()
    for flow_msg in self.msgs:
        flow_msg.on_view_ready(check)
    return self

  def get_error(self):
    none_entry_error, index = None, None
    for error in self.output['errors']:
        for idx, msg in enumerate(error['message']):
            error_file = msg['path']
            if self.file == error_file:
                if idx:
                    if not none_entry_error: none_entry_error, index = error, idx
                else:
                    # It is an entry error
                    return error, idx
    return none_entry_error, index

  def show_report(self):
    def on_select(index):
        if index >= 0: self.msgs[index].focus()

    report = [flow_msg.report(self.file) for flow_msg in self.msgs]
    return self.on_view_ready(lambda: sublime.active_window().show_quick_panel(
        items = report,
        on_select = on_select,
        selected_index = self.index
    ))

  def highlight(self):
    return self.on_view_ready(lambda: [flow_msg.highlight() for flow_msg in self.msgs])

  def clear(self):
    for flow_msg in self.msgs:
        flow_msg.clear()
    return self

class Flow_msg:
  def __init__(self, msg):
    self.line = msg['line'] - 1
    self.col = msg['start'] - 1
    self.line_end = msg['endline'] - 1
    self.col_end = msg['end']
    self.file = msg['path']
    self.message = msg['descr']
    self.view = self.get_view()

  def get_view(self):
    window = sublime.active_window()
    view = window.find_open_file(self.file)
    if not view:
        current_view = window.active_view()
        view = window.open_file("{}:{}:{}".format(self.file, self.line, self.col), sublime.ENCODED_POSITION)
        window.focus_view(current_view)
    return view

  def on_view_ready(self, callback):
    if self.view.is_loading():
        sublime.set_timeout_async(lambda: self.on_view_ready(callback), 50)
    else:
        callback()
    return self

  def region(self):
    start = self.view.text_point(self.line, self.col)
    end = self.view.text_point(self.line_end, self.col_end)
    return sublime.Region(start, end)

  def highlight(self):
    regions = self.view.get_regions(FLOW_REGION_KEY)
    regions.append(self.region())
    self.view.add_regions(FLOW_REGION_KEY, regions, FLOW_MARK_SCOPE, FLOW_MARK_ICON, FlOW_MARK_FLAGS)
    return self

  def report(self, base_file):
    point = self.view.text_point(self.line, self.col)
    code = self.view.substr(self.view.full_line(point))[:self.col] + '➜' + self.view.substr(self.region())
    message = self.message if self.file == base_file else '↯ ' + self.message
    return [code, message]

  def focus(self):
    sublime.active_window().open_file("{}:{}:{}".format(self.file, self.line, self.col), sublime.ENCODED_POSITION)
    return self

  def clear(self):
    clear_view(self.view)
    return self

class Flow(Linter):

    """Provides an interface to flow."""

    syntax = ('javascript', 'html', 'javascriptnext', 'javascript (babel)', 'javascript (jsx)', 'jsx')
    executable = 'flow'
    version_args = '--version'
    version_re = r'(?P<version>\d+\.\d+\.\d+)'
    version_requirement = '>= 0.1.0'
    defaults = {
        # Allows the user to lint *all* files, regardless of whether they have the `/* @flow */` declaration at the top.
        'all': False,

        # Allow to bypass the 50 errors cap
        'show-all-errors': True,

        # Allows flow to start server (makes things faster on larger projects)
        'use-server': True,

        # Options for flow
        '--lib:,': ''
    }
    word_re = r'^((\'|")?[^"\']+(\'|")?)(?=[\s\,\)\]])'
    selectors = {
        'html': 'source.js.embedded.html'
    }

    def cmd(self):
        """Return the command line to execute."""
        command = [self.executable_path, '--json']

        if self.get_merged_settings()['use-server']:
            command.append('--no-auto-start')
        else:
            command.append('check')

        if self.get_merged_settings()['show-all-errors']:
            command.append('--show-all-errors')

        if self.get_merged_settings()['all']:
            command.append('--all')

        return command

    def find_errors(self, output):
        """
        A generator which matches the linter's regex against the linter output.
        If multiline is True, split_match is called for each non-overlapping
        match of self.regex. If False, split_match is called for each line
        in output.
        """
        # match, line, col, error, warn, message, near
        default = (None, None, None, None, None, '', None)

        try:
            json_output = sublime.decode_value(output)
        except ValueError:
            return [default]

        # since the sublimelinter won't show error report outside the file of current view, we use our own report  
        Flow_error(json_output, self.view.file_name()).show_report().highlight()
        yield default


class Clear(sublime_plugin.EventListener):
    def is_enabled(self, view): 
        return 'source.js' in view.scope_name(0).split(' ')
        
    def on_modified_async(self, view): 
        clear_view(view)
