"""Walks a folder tree and yields the entries a search asks for.

No fman import, so test_just_search.py can run with plain Python.
"""
import os
from collections import namedtuple
from dataclasses import dataclass
from typing import FrozenSet, Optional

from .matching import build_matcher, file_contains, MODE_TOKENS

KIND_BOTH = 'both'
KIND_FILES = 'files'
KIND_FOLDERS = 'folders'

KIND_LABELS = (
    (KIND_BOTH, 'Files and folders'),
    (KIND_FILES, 'Files'),
    (KIND_FOLDERS, 'Folders'),
)

Hit = namedtuple('Hit', ('path', 'rel_path', 'is_dir'))


@dataclass
class SearchOptions:
    query: str = ''
    mode: str = MODE_TOKENS
    kind: str = KIND_BOTH
    max_depth: Optional[int] = None   # None: all subfolders, 0: only the folder itself
    text: str = ''                    # empty: do not look inside files
    encoding: str = 'utf-8'
    excluded: FrozenSet[str] = frozenset()   # lower-case folder names never entered


def scan(root, options, stop):
    """Yields a Hit for every entry below `root` that `options` allows."""
    yield from _scan_dir(root, '', 0, options, stop)


def search(root, options, stop, on_scanned=None):
    """Yields the Hits that match the query (and contain options.text, if set).
    `on_scanned(hit)` is called for every scanned entry, matching or not."""
    matches = build_matcher(options.query, options.mode)
    for hit in scan(root, options, stop):
        if on_scanned:
            on_scanned(hit)
        if not matches(hit.rel_path):
            continue
        if options.text and (hit.is_dir or not file_contains(
                hit.path, options.text, options.encoding, stop)):
            continue
        yield hit


def _scan_dir(folder, rel_folder, depth, options, stop):
    try:
        entries = os.scandir(folder)
    except OSError:
        return
    with entries:
        for entry in entries:
            if stop():
                return
            try:
                # follow_symlinks=False guards against junction/symlink cycles
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            rel_path = os.path.join(rel_folder, entry.name)
            if not is_dir:
                if options.kind != KIND_FOLDERS:
                    yield Hit(entry.path, rel_path, False)
                continue
            if entry.name.lower() in options.excluded:
                continue
            if options.kind != KIND_FILES:
                yield Hit(entry.path, rel_path, True)
            if options.max_depth is None or depth < options.max_depth:
                yield from _scan_dir(entry.path, rel_path, depth + 1, options, stop)
