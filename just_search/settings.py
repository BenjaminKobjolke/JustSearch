"""Remembers the last search, the input histories and the excluded folders
in 'Just Search.json' in fman's data folder."""
from fman import load_json, save_json

from .scanner import SearchOptions

SETTINGS_FILE = 'Just Search.json'
HISTORY_SIZE = 10
DEFAULT_EXCLUDED_FOLDERS = [
    '.obsidian', '.git', '.trash', '.stfolder', '.stversions', 'node_modules'
]


def _settings():
    # save_on_quit: fman caches this dict, so later calls see earlier changes
    return load_json(SETTINGS_FILE, default={}, save_on_quit=True)


def last_options():
    """The dialog's last options. `text` is empty when text search was off."""
    saved = _settings().get('options', {})
    options = SearchOptions(excluded=excluded_folders())
    for name in (
        'query',
        'mode',
        'kind',
        'max_depth',
        'text',
        'encoding',
        'ignore_case',
    ):
        if name in saved:
            setattr(options, name, saved[name])
    if not text_search_enabled():
        options.text = ''
    return options


def excluded_folders():
    names = _settings().get('excluded_folders', DEFAULT_EXCLUDED_FOLDERS)
    return frozenset(name.lower() for name in names)


def text_search_enabled():
    return _settings().get('text_search_enabled', False)


def query_history():
    return _settings().get('query_history', [])


def text_history():
    return _settings().get('text_history', [])


def remember_query(query):
    settings = _settings()
    settings.setdefault('options', {})['query'] = query
    _add_to_history(settings, 'query_history', query)
    save_json(SETTINGS_FILE)


def remember_dialog(options, text_enabled):
    settings = _settings()
    settings['options'] = {
        'query': options.query, 'mode': options.mode, 'kind': options.kind,
        'max_depth': options.max_depth, 'text': options.text,
        'encoding': options.encoding, 'ignore_case': options.ignore_case,
    }
    settings['text_search_enabled'] = text_enabled
    settings.setdefault('excluded_folders', DEFAULT_EXCLUDED_FOLDERS)
    _add_to_history(settings, 'query_history', options.query)
    if text_enabled:
        _add_to_history(settings, 'text_history', options.text)
    save_json(SETTINGS_FILE)


def _add_to_history(settings, key, value):
    if not value:
        return
    history = [entry for entry in settings.get(key, []) if entry != value]
    settings[key] = ([value] + history)[:HISTORY_SIZE]
