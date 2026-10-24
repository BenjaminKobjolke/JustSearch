"""Flat result list in a pane: search://<folder> lists every hit as one row.

A row's name is its path relative to the searched folder with os.sep replaced by
_SEPARATOR, so fman sees all hits as direct children of the search:// url.
"""
import os

from fman import DirectoryPaneListener
from fman.fs import FileSystem, Column, cached, is_dir as fs_is_dir, query as fs_query
from fman.url import as_url, basename, splitscheme, dirname as url_dirname

SCHEME = 'search://'
_SEPARATOR = '|'


def _to_file_url(path):
    return as_url(path.replace(_SEPARATOR, os.sep))


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
        if command_name != 'open_file' or 'url' not in args:
            return
        scheme, path = splitscheme(args['url'])
        if scheme != SCHEME:
            return
        real_url = _to_file_url(path)
        is_dir = fs_is_dir(real_url)
        reveal(self.pane, real_url, is_dir)
        return 'open_directory', {'url': real_url if is_dir else url_dirname(real_url)}
