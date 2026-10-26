"""Name matchers and the file-content check behind every JustSearch command.

No fman import, so test_just_search.py can run with plain Python.
"""
import fnmatch
import os
import re

MODE_TOKENS = 'tokens'
MODE_TOKENS_PATH = 'tokens_path'
MODE_GLOB = 'glob'
MODE_REGEX = 'regex'
MODE_FUZZY = 'fuzzy'
GLOB_SEPARATOR = ';'

MODE_LABELS = (
    (MODE_TOKENS, 'Words in name (any order)'),
    (MODE_TOKENS_PATH, 'Words in path (in order)'),
    (MODE_GLOB, 'Wildcards (*.pdf;*.txt)'),
    (MODE_REGEX, 'Regular expression'),
    (MODE_FUZZY, 'Fuzzy'),
)


def build_matcher(query, mode):
    """Returns fn(rel_path) -> bool. Raises re.error for an invalid regex."""
    if not query.strip():
        return lambda rel_path: True
    if mode == MODE_TOKENS:
        tokens = query.lower().split()
        return lambda rel_path: _contains_all(_leaf(rel_path).lower(), tokens)
    if mode == MODE_TOKENS_PATH:
        tokens = query.lower().split()
        return lambda rel_path: _contains_in_order(rel_path.lower(), tokens)
    if mode == MODE_GLOB:
        parts = (part.strip() for part in query.split(GLOB_SEPARATOR))
        pattern = re.compile(
            '|'.join(fnmatch.translate(part) for part in parts if part),
            re.IGNORECASE,
        )
        return lambda rel_path: bool(pattern.match(_leaf(rel_path)))
    if mode == MODE_REGEX:
        pattern = re.compile(query, re.IGNORECASE)
        return lambda rel_path: bool(pattern.search(_leaf(rel_path)))
    if mode == MODE_FUZZY:
        chars = query.lower().replace(' ', '')
        return lambda rel_path: _contains_in_order(rel_path.lower(), chars)
    raise ValueError('Unknown search mode: %r' % mode)


def file_contains(path, text, encoding, stop, ignore_case=False):
    """True if `text` occurs in the file.

    `encoding` must be valid (see codecs.lookup).
    """
    if ignore_case:
        text = text.casefold()
    try:
        with open(path, 'r', encoding=encoding, errors='ignore') as f:
            for line in f:
                if stop():
                    return False
                if text in (line.casefold() if ignore_case else line):
                    return True
    except OSError:
        pass
    return False


def _leaf(rel_path):
    return os.path.basename(rel_path)


def _contains_all(text, tokens):
    return all(token in text for token in tokens)


def _contains_in_order(text, parts):
    pos = 0
    for part in parts:
        idx = text.find(part, pos)
        if idx == -1:
            return False
        pos = idx + len(part)
    return True
