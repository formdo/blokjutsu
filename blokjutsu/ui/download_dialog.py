"""The one place the app asks to use the network: a consent page, then progress, then the outcome.

The same dialog serves first launch (model missing), File → Download Model…, and
File → Download Captioning Head…. The download runs in a child process (fetch.py) with offline mode lifted
for that process alone.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication, QDialog, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .. import network
from ..fetch import CAPTION_CANDIDATES
from ..settings import app_home, models_dir, tilde

WIDTH = 520
MARGIN, SPACING, ICON, GAP = 20, 16, 64, 10
PAGE = WIDTH - 2 * MARGIN - SPACING - ICON     # text column width
log = logging.getLogger("blokjutsu.download")


@dataclass(frozen=True)
class DownloadSpec:
    kind: str                # 'model' or 'caption'
    title: str
    heading: str
    intro: str
    rows: tuple              # (label, text) pairs shown on the consent page
    args: tuple              # fetch.py arguments
    action: str = "Download"


def model_spec(model, first_run=False, fake=False):
    name = model.split("/")[-1]
    if first_run:
        heading = f"Download {name}?"
        intro = ("Blokjutsu makes pictures with the MOSS-Image model, which runs locally on this Mac. "
                 "It has to be downloaded once before the first picture.")
    else:
        heading = f"Download {name} again?"
        intro = ("Fetches any of the model's files that are missing or damaged; files you already have are "
                 "skipped. Blokjutsu always uses the model version it was tested with, which a new release of "
                 "Blokjutsu can move forward.")
    return DownloadSpec(
        "model", "Download model", heading, intro,
        (("What", f"{model}: image model, text encoder (Qwen3.5-9B) and image decoder (FLUX.2 VAE)"),
         ("Size", "Tens of GB; the exact total is shown when the download starts. Files you already have are "
                  "skipped."),
         ("From", "huggingface.co, run by Hugging Face"),
         ("Saved in", tilde(models_dir())),
         ("Sent", network.WHAT_IS_SENT)),
        ("fake", "4") if fake else ("model", model))


def caption_spec(text_encoder_dir, fake=False):
    first, second = CAPTION_CANDIDATES
    return DownloadSpec(
        "caption", "Download captioning head", "Download the captioning head?",
        "Describe Image uses MOSS-Image's own text encoder, which can also read images. The model was "
        "published without its final output layer, so that one layer is downloaded from Qwen.",
        (("What", f"The output layer (lm_head) of {first} or {second}, whichever is identical to MOSS's text "
                  "encoder. A few MB of each are compared first; nothing is kept if neither matches."),
         ("Size", "2.0 GB, plus a few small tokenizer and settings files"),
         ("From", "huggingface.co, run by Hugging Face"),
         ("Saved in", tilde(app_home() / "caption")),
         ("Sent", network.WHAT_IS_SENT)),
        ("fake", "4") if fake else ("caption-head", str(text_encoder_dir), str(app_home() / "caption")))


def gigabytes(n):
    return f"{n / 1e9:.2f} GB"


def clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def text_label(text, wrap=True, muted=False, bold=False, size=None):
    label = QLabel(text)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    font = label.font()
    if bold:
        font.setWeight(QFont.DemiBold)
    if size:
        font.setPointSizeF(font.pointSizeF() * size)
    label.setFont(font)
    if muted:
        label.setForegroundRole(QPalette.PlaceholderText)
    return label


def buttons(*items):
    row = QHBoxLayout()
    row.addStretch(1)
    for b in items:
        row.addWidget(b)
    return row


class DownloadDialog(QDialog):
    succeeded = Signal(str)        # spec.kind

    def __init__(self, spec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.process = None
        self.setWindowTitle(spec.title)
        self.setFixedWidth(WIDTH)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._consent_page())
        self.pages.addWidget(self._progress_page())
        self.pages.addWidget(self._result_page())
        outer = QHBoxLayout(self)
        outer.setContentsMargins(MARGIN, MARGIN, MARGIN, 16)
        outer.setSpacing(SPACING)
        icon = QLabel()
        icon.setPixmap(QApplication.windowIcon().pixmap(ICON, ICON))
        icon.setAlignment(Qt.AlignTop)
        outer.addWidget(icon, 0, Qt.AlignTop)
        outer.addWidget(self.pages, 1)

    # pages

    def _consent_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(text_label(self.spec.heading, bold=True, size=1.15))
        v.addWidget(text_label(self.spec.intro))
        v.addLayout(self._facts())
        v.addWidget(text_label("Nothing is downloaded unless you click " + self.spec.action + ". "
                               "Blokjutsu uses the internet only for downloads like this one.", muted=True))
        later = QPushButton("Not now")
        later.setAutoDefault(False)          # otherwise, having focus first, it takes over the default role
        later.clicked.connect(self.reject)
        go = QPushButton(self.spec.action)
        go.setDefault(True)
        go.setFocus()
        go.clicked.connect(self.start)
        v.addLayout(buttons(later, go))
        return page

    def _facts(self):
        """Label/text rows; fixed widths so wrapped text is measured at the width it really gets."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(GAP)
        grid.setVerticalSpacing(6)
        names = [text_label(label, wrap=False, bold=True) for label, _ in self.spec.rows]
        name_width = max(QFontMetrics(n.font()).horizontalAdvance(n.text()) for n in names) + 2
        for row, (name, (_, text)) in enumerate(zip(names, self.spec.rows)):
            name.setAlignment(Qt.AlignRight | Qt.AlignTop)
            name.setFixedWidth(name_width)
            value = text_label(text, muted=True)
            value.setFixedWidth(PAGE - name_width - GAP)
            grid.addWidget(name, row, 0, Qt.AlignTop)
            grid.addWidget(value, row, 1, Qt.AlignTop)
        return grid

    def _progress_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(text_label(self.spec.heading.rstrip("?").replace("Download", "Downloading", 1) + "…",
                               bold=True, size=1.15))
        self.status = text_label("Starting…")
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.detail = text_label("", muted=True)
        stop = QPushButton("Cancel")
        stop.clicked.connect(self.stop)
        for w in (self.status, self.bar, self.detail):
            v.addWidget(w)
        v.addStretch(1)
        v.addLayout(buttons(stop))
        return page

    def _result_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.result_heading = text_label("", bold=True, size=1.15)
        self.result_text = text_label("")
        self.details = QPlainTextEdit(readOnly=True)
        self.details.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.details.setMinimumHeight(180)
        self.details.hide()
        self.show_details = QPushButton("Show details")
        self.show_details.setAutoDefault(False)
        self.show_details.clicked.connect(self._toggle_details)
        v.addWidget(self.result_heading)
        v.addWidget(self.result_text)
        v.addWidget(self.details)
        v.addStretch(1)
        self.retry = QPushButton("Try again")
        self.retry.setAutoDefault(False)
        self.retry.clicked.connect(self.start)
        self.close_button = QPushButton("Close")
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        row = buttons(self.retry, self.close_button)
        row.insertWidget(0, self.show_details)
        v.addLayout(row)
        return page

    def _toggle_details(self):
        self.details.setVisible(not self.details.isVisible())
        self.show_details.setText("Hide details" if self.details.isVisible() else "Show details")
        self.adjustSize()

    # process

    def start(self):
        self.pages.setCurrentIndex(1)
        self.bar.setRange(0, 0)
        self.status.setText("Connecting to huggingface.co…")
        self.detail.setText("")
        self.started, self.first = time.monotonic(), None
        self.failure, self.buffer = None, b""
        self.details.clear()
        self._note(f"$ {' '.join(network.download_command(*self.spec.args)[1:])}")
        argv = network.download_command(*self.spec.args)
        process = QProcess(self)
        process.setProgram(argv[0])
        process.setArguments(argv[1:])
        env = QProcessEnvironment()
        for key, value in network.download_environment().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(
            lambda: self._note(bytes(process.readAllStandardError()).decode(errors="replace").rstrip()))
        process.finished.connect(self._finished)
        self.process = process
        process.start()

    def stop(self):
        if self.process is not None:
            self.process.kill()

    def _read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        *lines, self.buffer = self.buffer.split(b"\n")
        for line in lines:
            kind, _, rest = line.decode(errors="replace").strip().partition(" ")
            if kind == "STATUS":
                self.status.setText(rest)
            elif kind == "PROGRESS":
                self._progress(*map(int, rest.split()))
            elif kind == "ERROR":
                self.failure = rest
            if kind != "PROGRESS":
                self._note(line.decode(errors="replace").rstrip())

    def _note(self, text):
        """Keep child output for Show Details and the app log."""
        if text:
            self.details.appendPlainText(text)
            log.info("%s", text)

    def _progress(self, done, total):
        now = time.monotonic()
        if self.first is None:
            self.first = (now, done)
        self.bar.setRange(0, 1000)
        self.bar.setValue(int(1000 * done / max(total, 1)))
        text = f"{gigabytes(done)} of {gigabytes(total)}"
        t0, d0 = self.first
        if now - t0 > 2 and done > d0:
            rate = (done - d0) / (now - t0)
            text += f" · {rate / 1e6:.0f} MB/s · about {clock((total - done) / rate)} left"
        self.detail.setText(text)

    def _finished(self, code, status):
        self.process = None
        self.pages.setCurrentIndex(2)
        if code == 0 and status == QProcess.NormalExit:
            self.result_heading.setText("Download complete")
            self.result_text.setText({"model": "The model is ready. Blokjutsu now runs locally, without the network.",
                                      "caption": "Describe image and Enhance prompt are ready. Blokjutsu now runs locally, without the network."}
                                     [self.spec.kind])
            self.retry.hide()
            self.succeeded.emit(self.spec.kind)
        elif status == QProcess.CrashExit and self.failure is None:
            self.result_heading.setText("Download stopped")
            self.result_text.setText("Nothing more will be fetched. What was already downloaded is kept, "
                                     "so downloading again picks up where this left off.")
            self.retry.setText("Resume")
            self.retry.show()
        else:
            self.result_heading.setText("Download failed")
            self.result_text.setText(self.failure or f"The download process exited with code {code}.")
            self.retry.setText("Try again")
            self.retry.show()
            if not self.details.isVisible():
                self._toggle_details()

    def reject(self):
        self.stop()
        super().reject()
