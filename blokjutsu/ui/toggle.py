"""Animated on/off switch (drop-in for QCheckBox: checkable, toggled, isChecked/setChecked)."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QAbstractButton


def mix(a, b, t):
    return QColor.fromRgbF(*(x + (y - x) * t for x, y in zip(a.getRgbF()[:3], b.getRgbF()[:3])))


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self.setFixedSize(self.sizeHint())
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.toggled.connect(self._animate)

    def sizeHint(self):
        return QSize(40, 24)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, on):
        self._anim.stop()
        if not self.isVisible():
            self._set_offset(1.0 if on else 0.0)
            return
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _):
        pal = self.palette()
        off = mix(pal.color(QPalette.Window), pal.color(QPalette.WindowText), 0.22)
        track = mix(off, QColor(54, 98, 227), self._offset)
        if not self.isEnabled():
            track.setAlphaF(0.5)
        size = self.sizeHint()
        rect = QRectF(0, (self.height() - size.height()) / 2, size.width(), size.height())
        radius = rect.height() / 2
        knob = rect.height() - 4
        x = rect.left() + 2 + self._offset * (rect.width() - knob - 4)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(rect, radius, radius)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, rect.top() + 2.6, knob, knob))
        p.setBrush(Qt.white)
        p.drawEllipse(QRectF(x, rect.top() + 2, knob, knob))
