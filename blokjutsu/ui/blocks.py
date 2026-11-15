"""A busy indicator in the app icon's colours: its four blocks take turns sliding round the cream tile, clockwise,
the red one settling back to its tilt each time it stops."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import QWidget

CREAM, YELLOW, BLUE, RED = (QColor("#EFE5CF"), QColor("#F2B41C"), QColor("#1D4FA3"), QColor("#D9302C"))
CELLS = ((0, 0), (1, 0), (1, 1), (0, 1))          # clockwise from top left, as (column, row)
START = {"yellow": 0, "blue-top": 1, "red": 2, "blue-bottom": 3}   # the icon's arrangement
MOVE, HOLD = 0.45, 0.35                           # seconds per slide, seconds at rest
TILT = 17                                         # degrees, the red block's tilt in the icon
FRAME_MS = 16


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(t, 0.0), 1.0))


class BlockSpinner(QWidget):
    def __init__(self, size=44, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.t = 0.0
        self.timer = QTimer(self, interval=FRAME_MS, timeout=self._tick)

    def start(self):
        self.t = 0.0
        self.timer.start()
        self.show()

    def stop(self):
        self.timer.stop()
        self.hide()

    def _tick(self):
        self.t += FRAME_MS / 1000
        self.update()

    def _place(self, name):
        """Cell position (fractional while sliding) and the red block's tilt, at the current time."""
        period = MOVE + HOLD
        step, into = divmod(self.t, period)
        k = ease(into / MOVE)
        a = CELLS[(START[name] + int(step)) % 4]
        b = CELLS[(START[name] + int(step) + 1) % 4]
        x, y = a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        tilt = TILT * (1 - math.sin(math.pi * k)) if name == "red" else 0
        return x, y, tilt

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        p.setPen(Qt.NoPen)
        p.setBrush(CREAM)
        p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.2, s * 0.2)
        pad, gap = s * 0.12, s * 0.025
        cell = (s - 2 * pad - gap) / 2
        for name in START:
            x, y, tilt = self._place(name)
            rect = QRectF(pad + x * (cell + gap), pad + y * (cell + gap), cell, cell)
            p.save()
            p.translate(rect.center())
            p.rotate(tilt)
            p.translate(-rect.center())
            self._block(p, name, rect)
            p.restore()

    @staticmethod
    def _block(p, name, rect):
        radius = rect.width() * 0.04
        if name in ("yellow", "red"):
            p.setBrush(YELLOW if name == "yellow" else RED)
            p.drawRoundedRect(rect, radius, radius)
            return
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        p.setClipPath(clip)
        tl, tr, br, bl = rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()
        first, second = (BLUE, YELLOW) if name == "blue-top" else (YELLOW, BLUE)
        p.setBrush(first)
        p.drawPolygon(QPolygonF([QPointF(tl), QPointF(tr), QPointF(bl)]))
        p.setBrush(second)
        p.drawPolygon(QPolygonF([QPointF(tr), QPointF(br), QPointF(bl)]))
        p.setClipping(False)
