"""Flat result list in a pane: search://<folder> lists every hit as one row.

A row's name is its path relative to the searched folder with os.sep replaced by
_SEPARATOR, so fman sees all hits as direct children of the search:// url.
"""
import os

import fman
from fman import DirectoryPaneCommand, DirectoryPaneListener, show_alert, show_prompt
from fman.fs import FileSystem, Column, cached, is_dir as fs_is_dir, query as fs_query
from fman.url import (
    as_url,
    basename,
    splitscheme,
    dirname as url_dirname,
    join as url_join,
)

SCHEME = 'search://'
_SEPARATOR = '|'
RUN_ON_RESULTS_COMMAND = 'run_on_search_results'
RENAME_RESULT_COMMAND = 'rename_search_result'
_FILE_ARGUMENT = {
    'move_to_trash': 'urls',
    'delete_permanently': 'urls',
    'move': 'files',
    'copy': 'files',
}


def _to_file_url(path):
    return as_url(path.replace(_SEPARATOR, os.sep))


def _row_file_url(row_url):
    return _to_file_url(splitscheme(row_url)[1])


def _is_results_pane(pane):
    return splitscheme(pane.get_path())[0] == SCHEME


def search_root_url(pane):
    """Folder to search in. While the pane shows search:// results, search the
    folder those results came from instead of the virtual url."""
    url = pane.get_path()
    if splitscheme(url)[0] == SCHEME:
        return SearchResultsFileSystem.root_url or url
    return url


def reveal(pane, url, is_dir):
    """Opens a folder hit, or opens a file hit's folder with the cursor on it."""
    if is_dir:
        pane.set_path(url)
    else:
        pane.set_path(url_dirname(url), callback=lambda: pane.place_cursor_at(url))


def show_in_pane(pane, root_url, rel_paths):
    SearchResultsFileSystem.results = [p.replace(os.sep, _SEPARATOR) for p in rel_paths]
    SearchResultsFileSystem.root_url = root_url
    target = SCHEME + splitscheme(root_url)[1]
    if pane.get_path() == target:
        pane.reload()   # set_path to the url already shown would be a no-op
    else:
        pane.set_path(target)


class SearchResultsFileSystem(FileSystem):
    scheme = SCHEME
    results = []
    root_url = ''   # real file:// url the last search ran in

    def get_default_columns(self, path):
        return (SearchName.get_qualified_name(), SearchPath.get_qualified_name(),
                'core.Size', 'core.Modified')

    def iterdir(self, path):
        yield from self.results

    def resolve(self, path):
        url = self.scheme + path
        if _SEPARATOR in basename(url):
            return _to_file_url(path)
        return url

    @cached
    def is_dir(self, path):
        return fs_is_dir(_to_file_url(path))

    def size_bytes(self, path):
        return fs_query(_to_file_url(path), 'size_bytes')

    def modified_datetime(self, path):
        return fs_query(_to_file_url(path), 'modified_datetime')


class SearchName(Column):
    def get_str(self, url):
        return basename(url).split(_SEPARATOR)[-1]


class SearchPath(Column):
    def get_str(self, url):
        return splitscheme(_to_file_url(splitscheme(url)[1]))[1]


class SearchResultsListener(DirectoryPaneListener):
    def on_command(self, command_name, args):
        if _is_results_pane(self.pane):
            if (
                command_name in _FILE_ARGUMENT
                and _FILE_ARGUMENT[command_name] not in args
            ):
                return RUN_ON_RESULTS_COMMAND, {'command': command_name}
            if command_name == 'rename':
                return RENAME_RESULT_COMMAND, {}
        if command_name != 'open_file' or 'url' not in args:
            return
        scheme, path = splitscheme(args['url'])
        if scheme != SCHEME:
            return
        real_url = _to_file_url(path)
        is_dir = fs_is_dir(real_url)
        reveal(self.pane, real_url, is_dir)
        return 'open_directory', {'url': real_url if is_dir else url_dirname(real_url)}


class RunOnSearchResults(DirectoryPaneCommand):
    def __call__(self, command: str) -> None:
        rows = self.get_chosen_files()
        self.pane.run_command(command, {
            _FILE_ARGUMENT[command]: [_row_file_url(row) for row in rows],
        })
        _drop_missing(rows)

    def is_visible(self) -> bool:
        return _is_results_pane(self.pane)


def _drop_missing(rows):
    for row in rows:
        if fman.fs.exists(_row_file_url(row)):
            continue
        result = basename(row)
        if result in SearchResultsFileSystem.results:
            SearchResultsFileSystem.results.remove(result)
        fman.fs.notify_file_removed(row)


class RenameSearchResult(DirectoryPaneCommand):
    def __call__(self) -> None:
        row = self.pane.get_file_under_cursor()
        if not row:
            return
        real_url = _row_file_url(row)
        old_name = basename(real_url)
        is_dir = fs_is_dir(real_url)
        end = len(old_name) if is_dir else len(os.path.splitext(old_name)[0])
        new_name, ok = show_prompt('Rename to:', old_name, 0, end)
        if not ok or not new_name or new_name == old_name:
            return
        if '/' in new_name or os.sep in new_name or _SEPARATOR in new_name:
            show_alert('Use Move (F6) to move files.')
            return

        target_url = url_join(url_dirname(real_url), new_name)
        if fman.fs.exists(target_url) and not fman.fs.samefile(real_url, target_url):
            show_alert('%s already exists!' % new_name)
            return
        try:
            fman.fs.move(real_url, target_url)
        except OSError as error:
            show_alert('Could not rename %s to %s: %s' % (old_name, new_name, error))
            return

        old_relative = _relative_result_path(row)
        new_relative = old_relative.rsplit(_SEPARATOR, 1)[0] + _SEPARATOR + new_name \
            if _SEPARATOR in old_relative else new_name
        replacements = []
        for index, result in enumerate(SearchResultsFileSystem.results):
            if result == old_relative:
                replacements.append((index, result, new_relative))
            elif is_dir and result.startswith(old_relative + _SEPARATOR):
                replacements.append((index, result,
                                     new_relative + result[len(old_relative):]))

        for index, old_result, new_result in replacements:
            SearchResultsFileSystem.results[index] = new_result
            old_row = row if old_result == old_relative else _result_url(old_result)
            new_row = _result_url(new_result)
            fman.fs.notify_file_removed(old_row)
            fman.fs.notify_file_added(new_row)
        self.pane.place_cursor_at(_result_url(new_relative))

    def is_visible(self) -> bool:
        return _is_results_pane(self.pane)


def _relative_result_path(row):
    root_path = splitscheme(SearchResultsFileSystem.root_url)[1].rstrip('/')
    row_path = splitscheme(row)[1]
    return row_path[len(root_path) + 1:]


def _result_url(relative_path):
    root_path = splitscheme(SearchResultsFileSystem.root_url)[1].rstrip('/')
    return SCHEME + root_path + '/' + relative_path
