"""The search window: every option in one place, with hits sent to the pane
as a flat search:// list when the search ends."""
import codecs
import os
import queue
import re
import threading

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QSpinBox, QVBoxLayout
)
from fman.url import as_human_readable, as_url

from . import settings
from .matching import MODE_LABELS, build_matcher
from .pane_results import reveal, show_in_pane
from .scanner import KIND_LABELS, SearchOptions, search

ENCODINGS = ('utf-8', 'utf-16', 'cp437', 'cp1252')
DRAIN_INTERVAL_MS = 200
DEPTH_ALL = -1   # spin box value shown as 'all'


class SearchDialog(QDialog):
    def __init__(self, pane, root_url):
        super().__init__()
        self._pane = pane
        self._hits = []
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._worker = None
        self._scanned = 0
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle('Just Search')
        self.resize(1000, 600)
        self._build_ui()
        self._load(as_human_readable(root_url))
        self._timer = QTimer(self)
        self._timer.setInterval(DRAIN_INTERVAL_MS)
        self._timer.timeout.connect(self._drain)

    def _build_ui(self):
        self._query = _editable_combo(settings.query_history())
        self._query.lineEdit().returnPressed.connect(self._start)
        self._mode = _data_combo(MODE_LABELS)
        self._kind = _data_combo(KIND_LABELS)
        self._folder = QLineEdit()
        self._folder.returnPressed.connect(self._start)
        self._depth = QSpinBox()
        self._depth.setRange(DEPTH_ALL, 99)
        self._depth.setSpecialValueText('all')
        self._text_enabled = QCheckBox('&Text in files')
        self._text = _editable_combo(settings.text_history())
        self._encoding = _editable_combo(ENCODINGS)
        self._ignore_case = QCheckBox('&Ignore case')
        for widget in (self._text, self._encoding, self._ignore_case):
            self._text_enabled.toggled.connect(widget.setEnabled)

        form = QFormLayout()
        form.addRow('&Name (F1)', self._query)
        form.addRow('Match', _row(self._mode, QLabel('Find'), self._kind,
                                   QLabel('Depth (0 = this folder only)'), self._depth))
        form.addRow('&Folder (F2)', self._folder)
        form.addRow(self._text_enabled, _row(self._text, QLabel('Encoding'), self._encoding,
                                             self._ignore_case))

        self._results = QListWidget()
        self._results.itemActivated.connect(self._jump)
        self._status = QLabel()

        self._search_button = _button('&Search', self._start)
        self._search_button.setDefault(True)
        self._stop_button = _button('Sto&p', self._stop_search)
        buttons = _row(self._status, self._search_button, self._stop_button,
                       _button('&Close', self.close))
        buttons.insertStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._results)
        layout.addLayout(buttons)
        self._set_running(False)

    def _load(self, folder):
        options = settings.last_options()
        self._query.setEditText(options.query)
        self._mode.setCurrentIndex(max(0, self._mode.findData(options.mode)))
        self._kind.setCurrentIndex(max(0, self._kind.findData(options.kind)))
        self._depth.setValue(DEPTH_ALL if options.max_depth is None else options.max_depth)
        self._folder.setText(folder)
        self._text_enabled.setChecked(settings.text_search_enabled())
        self._encoding.setEditText(options.encoding)
        self._ignore_case.setChecked(options.ignore_case)
        enabled = self._text_enabled.isChecked()
        for widget in (self._text, self._encoding, self._ignore_case):
            widget.setEnabled(enabled)
        self._query.lineEdit().selectAll()

    def _options(self):
        depth = self._depth.value()
        return SearchOptions(
            query=self._query.currentText(),
            mode=self._mode.currentData(),
            kind=self._kind.currentData(),
            max_depth=None if depth == DEPTH_ALL else depth,
            text=self._text.currentText() if self._text_enabled.isChecked() else '',
            encoding=self._encoding.currentText().strip() or ENCODINGS[0],
            ignore_case=self._ignore_case.isChecked(),
            excluded=settings.excluded_folders(),
        )

    def _start(self):
        if self._worker:
            return
        options = self._options()
        folder = self._folder.text().strip()
        error = _validate(options, folder)
        if error:
            self._status.setText(error)
            return
        settings.remember_dialog(options, self._text_enabled.isChecked())
        self._hits = []
        self._results.clear()
        self._scanned = 0
        self._stop.clear()
        self._root_url = as_url(folder)
        self._worker = threading.Thread(
            target=self._run, args=(folder, options), daemon=True)
        self._set_running(True)
        self._worker.start()
        self._timer.start()

    def _run(self, folder, options):
        def count(_hit):
            self._scanned += 1
        for hit in search(folder, options, self._stop.is_set, count):
            self._queue.put(hit)
        self._queue.put(None)   # end marker

    def _drain(self):
        batch = []
        finished = False
        while not self._queue.empty():
            hit = self._queue.get()
            if hit is None:
                finished = True
                break
            batch.append(hit)
        self._hits.extend(batch)
        self._results.addItems([hit.path for hit in batch])
        state = 'stopped' if self._stop.is_set() else 'done' if finished else 'searching'
        self._status.setText('%d found, %d scanned (%s)' % (len(self._hits), self._scanned, state))
        if finished:
            self._timer.stop()
            self._worker = None
            self._set_running(False)
            if self._hits:
                self._show_in_pane()

    def _stop_search(self):
        self._stop.set()

    def _set_running(self, running):
        self._search_button.setEnabled(not running)
        self._stop_button.setEnabled(running)

    def _jump(self, item):
        hit = self._hits[self._results.row(item)]
        reveal(self._pane, as_url(hit.path), hit.is_dir)

    def _show_in_pane(self):
        show_in_pane(self._pane, self._root_url, [hit.rel_path for hit in self._hits])
        self.close()

    def keyPressEvent(self, event):
        focus = {Qt.Key_F1: self._query, Qt.Key_F2: self._folder, Qt.Key_F3: self._results}
        if event.key() in focus:
            if event.key() == Qt.Key_F3 and self._results.currentRow() < 0:
                self._results.setCurrentRow(0)
            focus[event.key()].setFocus()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._stop.set()
        self._timer.stop()
        super().closeEvent(event)


def _validate(options, folder):
    if not os.path.isdir(folder):
        return 'Not a folder: ' + folder
    try:
        build_matcher(options.query, options.mode)
    except re.error as e:
        return 'Invalid regular expression: %s' % e
    try:
        codecs.lookup(options.encoding)
    except LookupError:
        return 'Unknown encoding: ' + options.encoding
    return ''


def _editable_combo(items):
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems(list(items))
    return combo


def _data_combo(labels):
    combo = QComboBox()
    for value, label in labels:
        combo.addItem(label, value)
    return combo


def _button(text, slot):
    button = QPushButton(text)
    button.clicked.connect(slot)
    return button


def _row(*widgets):
    row = QHBoxLayout()
    for widget in widgets:
        row.addWidget(widget)
    return row
