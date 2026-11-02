"""Small shared widgets: help popover and clickable help labels."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ..help_text import HELP

class HelpPopup(QFrame):
    def __init__(self, html, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setFrameShape(QFrame.StyledPanel)
        label = QLabel(html)
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        label.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(label)


class HelpLabel(QLabel):
    """Bold label that shows its explanation when clicked."""

    def __init__(self, text, key, parent=None):
        super().__init__(text, parent)
        font = self.font()
        font.setWeight(QFont.Medium)
        self.setFont(font)
        self.html = HELP[key]
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click for an explanation")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        popup = HelpPopup(self.html, self)
        popup.adjustSize()
        popup.move(self.mapToGlobal(QPoint(0, self.height())))
        popup.show()


def labelled(text, key):
    return HelpLabel(text, key)
