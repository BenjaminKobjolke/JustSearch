"""fman commands: the search window, prompt searches with fixed presets that send
their results to the pane, and fuzzy quicksearch over this folder or all subfolders."""
import re

from core.quicksearch_matchers import contains_chars
from fman import (
    DirectoryPaneCommand, QuicksearchItem, Task, show_prompt, show_quicksearch,
    show_status_message, submit_task
)
from fman.impl.util.qt.thread import run_in_main_thread
from fman.url import as_human_readable, as_url

from . import settings
from .dialog import SearchDialog
from .matching import MODE_TOKENS, MODE_TOKENS_PATH, build_matcher
from .pane_results import reveal, search_root_url, show_in_pane
from .scanner import KIND_BOTH, KIND_FOLDERS, SearchOptions, scan, search

PROGRESS_EVERY = 100   # entries between progress text updates


class _SearchTask(Task):
    def __init__(self, folder, options):
        super().__init__('Searching...')
        self._folder = folder
        self._options = options
        self.hits = []
        self.scanned = 0

    def __call__(self):
        self.hits = list(
            search(self._folder, self._options, self._stop, self._on_scanned)
        )

    def _stop(self):
        self.check_canceled()   # raises Task.Canceled, which ends the walk
        return False

    def _on_scanned(self, hit):
        self.scanned += 1
        if self.scanned % PROGRESS_EVERY == 0:
            self.set_text('Scanning: %s (%d entries)' % (hit.rel_path, self.scanned))


def _run_task(folder, options):
    """The finished task, or None if the user canceled it."""
    task = _SearchTask(folder, options)
    try:
        submit_task(task)
    except task.Canceled:
        return None
    return task


class SearchWithDialog(DirectoryPaneCommand):
    @run_in_main_thread
    def __call__(self):
        self._dialog = SearchDialog(self.pane, search_root_url(self.pane))
        self._dialog.show()


class _PromptSearch(DirectoryPaneCommand):
    """Prompt prefilled with the last query (fully selected), search, show the
    hits flat in the pane. Subclasses fix everything but the query."""

    prompt_text = 'Search files and folders in subfolders:'

    def _preset(self):
        raise NotImplementedError

    def __call__(self):
        last_query = settings.last_options().query
        query, ok = show_prompt(self.prompt_text, last_query, 0, len(last_query))
        if not ok:
            return
        settings.remember_query(query)
        options = self._preset()
        options.query = query
        try:
            build_matcher(options.query, options.mode)
        except re.error as e:
            show_status_message('Invalid regular expression: %s' % e, 5)
            return
        root_url = search_root_url(self.pane)
        task = _run_task(as_human_readable(root_url), options)
        if task is None:
            return
        if not task.hits:
            show_status_message(
                'No matches for %r in %d entries.' % (query, task.scanned), 5
            )
            return
        show_in_pane(self.pane, root_url, [hit.rel_path for hit in task.hits])
        show_status_message(
            '%d matches in %d entries' % (len(task.hits), task.scanned), 5
        )


class SearchFilesAndFoldersTokenBased(_PromptSearch):
    def _preset(self):
        return SearchOptions(mode=MODE_TOKENS, kind=KIND_BOTH,
                             excluded=settings.excluded_folders())


class SearchFoldersTokenBased(_PromptSearch):
    prompt_text = 'Search folders in subfolders:'

    def _preset(self):
        return SearchOptions(mode=MODE_TOKENS, kind=KIND_FOLDERS,
                             excluded=settings.excluded_folders())


class SearchFoldersTokenBasedWithParent(_PromptSearch):
    prompt_text = 'Search folders with parent path:'

    def _preset(self):
        return SearchOptions(mode=MODE_TOKENS_PATH, kind=KIND_FOLDERS,
                             excluded=settings.excluded_folders())


class SearchWithLastSettings(_PromptSearch):
    prompt_text = 'Search with the last search window settings:'

    def _preset(self):
        return settings.last_options()


def _fuzzy_items(hits, query):
    for hit in hits:
        shown = '[%s]' % hit.rel_path if hit.is_dir else hit.rel_path
        match = contains_chars(shown.lower(), query.lower())
        if match or not query:
            yield QuicksearchItem(hit.path, shown, highlight=match)


class SearchFilesInThisFolder(DirectoryPaneCommand):
    def __call__(self):
        folder = as_human_readable(self.pane.get_path())
        hits = sorted(scan(folder, SearchOptions(max_depth=0), lambda: False),
                      key=lambda hit: hit.rel_path.lower())
        result = show_quicksearch(lambda query: _fuzzy_items(hits, query))
        if result:
            self.pane.place_cursor_at(as_url(result[1]))


class SearchFilesInSubFolders(DirectoryPaneCommand):
    def __call__(self):
        folder = as_human_readable(self.pane.get_path())
        task = _run_task(folder, SearchOptions(excluded=settings.excluded_folders()))
        if task is None or not task.hits:
            return
        show_status_message('%d entries found' % task.scanned, 5)
        result = show_quicksearch(lambda query: _fuzzy_items(task.hits, query))
        if result:
            reveal(self.pane, as_url(result[1]), is_dir=False)
