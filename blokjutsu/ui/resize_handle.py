"""A drag handle under a text box that changes the box's height (like a web textarea's grip)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QWidget


class ResizeHandle(QWidget):
    resized = Signal(int)

    def __init__(self, target, minimum=48, maximum=1200, parent=None):
        super().__init__(parent)
        self.target, self.minimum, self.maximum = target, minimum, maximum
        self.setFixedHeight(10)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag to resize")
        self._origin = None

    def set_height(self, height):
        height = max(self.minimum, min(self.maximum, int(height)))
        self.target.setFixedHeight(height)
        return height

    def mousePressEvent(self, event):
        self._origin = (event.globalPosition().y(), self.target.height())

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            y0, h0 = self._origin
            self.set_height(h0 + event.globalPosition().y() - y0)

    def mouseReleaseEvent(self, _):
        if self._origin is not None:
            self._origin = None
            self.resized.emit(self.target.height())

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.palette().color(QPalette.PlaceholderText))
        painter.setOpacity(0.5)
        painter.drawRoundedRect(QRectF(self.width() / 2 - 18, 3, 36, 4), 2, 2)
