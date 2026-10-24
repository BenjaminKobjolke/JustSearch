"""Self-check for the fman-independent search logic (matching.py, scanner.py).

fman is not importable outside fman, so the package is registered without running
its __init__.py. Run: python test_just_search.py
"""
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_package = types.ModuleType('just_search')
_package.__path__ = [os.path.join(_HERE, 'just_search')]
sys.modules['just_search'] = _package

from just_search.matching import (  # noqa: E402
    build_matcher, file_contains,
    MODE_TOKENS, MODE_TOKENS_PATH, MODE_GLOB, MODE_REGEX, MODE_FUZZY
)
from just_search.scanner import (  # noqa: E402
    SearchOptions, scan, search, KIND_FILES, KIND_FOLDERS
)


def _never():
    return False


def _make_tree(root):
    files = {
        'report 2026.pdf': 'total',
        'notes.txt': 'hello world',
        os.path.join('invoices 2026', 'fraenk.pdf'): 'x',
        os.path.join('invoices 2026', 'deep', 'umlaut.txt'): 'grüße',
        os.path.join('.git', 'config'): 'hello world',
    }
    for rel_path, content in files.items():
        path = os.path.join(root, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def _rel_paths(hits):
    return sorted(hit.rel_path for hit in hits)


def test_matchers():
    path = os.path.join('invoices 2026', 'fraenk.pdf')
    assert build_matcher('', MODE_REGEX)(path)
    assert build_matcher('PDF fraenk', MODE_TOKENS)(path)
    assert not build_matcher('invoices', MODE_TOKENS)(path)  # leaf name only
    assert build_matcher('invoices fraenk', MODE_TOKENS_PATH)(path)
    assert not build_matcher('fraenk invoices', MODE_TOKENS_PATH)(path)
    assert build_matcher('*.PDF', MODE_GLOB)(path)
    assert not build_matcher('*.txt', MODE_GLOB)(path)
    assert build_matcher(r'^fr.*k\.pdf$', MODE_REGEX)(path)
    assert build_matcher('inv frk', MODE_FUZZY)(path)
    assert not build_matcher('kfr', MODE_FUZZY)('fraenk.pdf')


def test_scan_depth_kind_and_excluded(root):
    excluded = frozenset(['.git'])
    everything = _rel_paths(scan(root, SearchOptions(excluded=excluded), _never))
    assert os.path.join('.git', 'config') not in everything
    assert os.path.join('invoices 2026', 'deep', 'umlaut.txt') in everything

    current_only = _rel_paths(scan(root, SearchOptions(max_depth=0, excluded=excluded), _never))
    assert current_only == ['invoices 2026', 'notes.txt', 'report 2026.pdf']

    one_level = _rel_paths(scan(root, SearchOptions(max_depth=1, excluded=excluded), _never))
    assert os.path.join('invoices 2026', 'deep') in one_level
    assert os.path.join('invoices 2026', 'deep', 'umlaut.txt') not in one_level

    folders = _rel_paths(scan(root, SearchOptions(kind=KIND_FOLDERS, excluded=excluded), _never))
    assert folders == ['invoices 2026', os.path.join('invoices 2026', 'deep')]

    files = _rel_paths(scan(root, SearchOptions(kind=KIND_FILES, excluded=excluded), _never))
    assert 'invoices 2026' not in files and 'notes.txt' in files


def test_search(root):
    options = SearchOptions(query='2026', excluded=frozenset(['.git']))
    assert _rel_paths(search(root, options, _never)) == ['invoices 2026', 'report 2026.pdf']

    scanned = []
    options = SearchOptions(text='hello', excluded=frozenset(['.git']))
    assert _rel_paths(search(root, options, _never, scanned.append)) == ['notes.txt']
    assert len(scanned) == 6

    options = SearchOptions(query='*.txt', mode=MODE_GLOB, text='grüß')
    assert _rel_paths(search(root, options, _never)) == [
        os.path.join('invoices 2026', 'deep', 'umlaut.txt')
    ]

    options = SearchOptions(text='HELLO', excluded=frozenset(['.git']))
    assert list(search(root, options, _never)) == []
    options.ignore_case = True
    assert _rel_paths(search(root, options, _never)) == ['notes.txt']

    assert list(search(root, SearchOptions(), lambda: True)) == []


def test_file_contains(root):
    path = os.path.join(root, 'invoices 2026', 'deep', 'umlaut.txt')
    assert file_contains(path, 'grüß', 'utf-8', _never)
    assert not file_contains(path, 'grüß', 'cp1252', _never)
    assert not file_contains(os.path.join(root, 'missing.txt'), 'x', 'utf-8', _never)


def main():
    test_matchers()
    with tempfile.TemporaryDirectory() as root:
        _make_tree(root)
        test_scan_depth_kind_and_excluded(root)
        test_search(root)
        test_file_contains(root)
    print('All JustSearch checks passed.')


if __name__ == '__main__':
    main()
