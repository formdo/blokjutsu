"""Describe image / Enhance prompt: the picture (or your prompt) on the left with the actions under it; on the
right, progress while the text encoder writes, then the short, medium and long texts, each with its actions
directly beneath it."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .icons import icon
from .theme import medium

LEVELS = (("short", "Short"), ("medium", "Medium"), ("long", "Long"))
INDENT = 4           # headings sit over the text inside the rounded boxes, not over the box edge


def text_box(text=""):
    """White rounded box of selectable, wrapped text."""
    label = QLabel(text, objectName="textBox")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    label.setFocusPolicy(Qt.ClickFocus)
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return label


def heading(text):
    label = medium(QLabel(text))
    label.setContentsMargins(INDENT, 0, 0, 0)
    return label


def muted(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setForegroundRole(QPalette.PlaceholderText)
    return label


def tight_row(*widgets):
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    for w in widgets:
        row.addWidget(w)
    row.addStretch(1)
    return row


class ScaledImage(QWidget):
    """A picture that fills its column's width, keeping its aspect ratio."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap(str(path))
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self):
        return not self.pixmap.isNull()

    def heightForWidth(self, width):
        if self.pixmap.isNull():
            return 0
        return round(width * self.pixmap.height() / self.pixmap.width())

    def sizeHint(self):
        return QSize(240, self.heightForWidth(240))

    def paintEvent(self, _):
        if self.pixmap.isNull():
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            size = self.pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
            painter.drawPixmap(0, 0, size.width(), size.height(), self.pixmap)
        finally:
            painter.end()


class DescribeDialog(QDialog):
    use = Signal(str)              # text to put in the prompt box
    again = Signal()
    cancel = Signal()

    def __init__(self, image_path, request=None, parent=None, title="Describe image"):
        """image_path None: Enhance prompt, showing `request` (the prompt being enhanced) instead."""
        super().__init__(parent)
        self.setObjectName("sheet")
        self.setWindowTitle(title)
        self.busy = False

        left = QWidget(objectName="sheetPanel")
        column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        if image_path:
            column.addWidget(ScaledImage(image_path))
        else:
            column.addWidget(heading("Your prompt"))
            column.addWidget(text_box(request or ""))
        self.retry = QPushButton("Describe again" if image_path else "Enhance again")
        self.retry.clicked.connect(self.again)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        column.addSpacing(4)
        column.addWidget(self.retry)
        column.addWidget(close)
        column.addStretch(1)

        self.pages = QStackedWidget(objectName="sheetPanel")
        self.pages.addWidget(self._working_page())
        self.pages.addWidget(self._result_page())

        splitter = QSplitter(Qt.Horizontal, objectName="sheetSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(18)
        splitter.addWidget(left)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 560])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.addWidget(splitter)
        self.resize(900, 640)

    def _working_page(self):
        page = QWidget(objectName="sheetPanel")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.stage = medium(QLabel("Waiting for the current picture to finish…"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.tokens = muted()
        for w in (self.stage, self.bar, self.tokens):
            v.addWidget(w)
        v.addStretch(1)
        return page

    def _result_page(self):
        content = QWidget(objectName="sheetPanel")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 8, 0)
        v.setSpacing(6)
        self.texts = {}
        for key, name in LEVELS:
            box = text_box()
            use = QPushButton("Use as prompt")
            use.clicked.connect(lambda _=False, k=key: self.use.emit(self.texts[k].text()))
            copy = QPushButton(icon("copy"), "Copy")
            copy.clicked.connect(lambda _=False, k=key: QGuiApplication.clipboard().setText(self.texts[k].text()))
            v.addWidget(heading(name))
            v.addWidget(box)
            v.addLayout(tight_row(use, copy))
            v.addSpacing(18)
            self.texts[key] = box
        self.watermarks = muted()
        self.watermarks.hide()
        v.addWidget(self.watermarks)
        v.addStretch(1)
        scroll = QScrollArea(objectName="sheetScroll")
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return scroll

    def working(self):
        self.busy = True
        self.retry.setEnabled(False)
        self.pages.setCurrentIndex(0)
        self.stage.setText("Waiting for the current picture to finish…")
        self.bar.setRange(0, 0)
        self.tokens.setText("")

    def set_stage(self, stage, total):
        self.stage.setText({"load": "Loading the model…", "describe": "Writing…"}.get(stage, self.stage.text()))

    def set_tokens(self, done, limit):
        self.tokens.setText(f"{done:,} tokens written")

    def show_result(self, captions):
        self.busy = False
        self.retry.setEnabled(True)
        for key, _ in LEVELS:
            self.texts[key].setText(captions.get(key, ""))
        marks = captions.get("watermarks") or []
        self.watermarks.setText(f"Watermark: {'; '.join(marks)}. Left out of the descriptions, so a prompt made "
                                "from them doesn't ask for it." if marks else "")
        self.watermarks.setVisible(bool(marks))
        self.pages.setCurrentIndex(1)

    def show_error(self, message):
        self.busy = False
        self.retry.setEnabled(True)
        self.stage.setText("Something went wrong")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.tokens.setText(message + "\n\nThe full error is in Help → Show Log.")

    def reject(self):
        if self.busy:
            self.cancel.emit()
        super().reject()
