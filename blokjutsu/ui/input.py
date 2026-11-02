"""App-wide input policy: Cocoa/Emacs control-key editing in text fields; mouse wheel never changes values."""
from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractScrollArea, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QSlider, QTextEdit,
)

CONTROL = Qt.MetaModifier if sys.platform == "darwin" else None   # Qt maps the physical Control key to Meta on macOS
MOVE = {Qt.Key_A: QTextCursor.StartOfBlock, Qt.Key_E: QTextCursor.EndOfBlock, Qt.Key_B: QTextCursor.PreviousCharacter,
        Qt.Key_F: QTextCursor.NextCharacter, Qt.Key_P: QTextCursor.Up, Qt.Key_N: QTextCursor.Down}


class ControlKeyEditing(QObject):
    """^A ^E ^B ^F ^P ^N ^D ^H ^K ^Y ^O ^T as in NSTextView; consecutive ^K kills accumulate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.killed = ""
        self.last_was_kill = False

    def eventFilter(self, obj, event):
        if CONTROL is None or event.type() != QEvent.KeyPress:
            return False
        if event.modifiers() & ~Qt.KeypadModifier != CONTROL:
            self.last_was_kill = False
            return False
        if isinstance(obj, (QPlainTextEdit, QTextEdit)):
            handled = self._text(obj, event.key())
        elif isinstance(obj, QLineEdit):
            handled = self._line(obj, event.key())
        else:
            return False
        self.last_was_kill = handled and event.key() == Qt.Key_K
        return handled

    def _kill(self, text):
        self.killed = self.killed + text if self.last_was_kill else text

    def _text(self, edit, key):
        if edit.isReadOnly() and key not in MOVE:
            return False
        c = edit.textCursor()
        if key in MOVE:
            c.movePosition(MOVE[key])
        elif key == Qt.Key_D:
            c.deleteChar()
        elif key == Qt.Key_H:
            c.deletePreviousChar()
        elif key == Qt.Key_K:
            c.clearSelection()
            mode = QTextCursor.KeepAnchor
            c.movePosition(QTextCursor.NextCharacter if c.atBlockEnd() else QTextCursor.EndOfBlock, mode)
            self._kill(c.selectedText().replace(" ", "\n"))
            c.removeSelectedText()
        elif key == Qt.Key_Y:
            c.insertText(self.killed)
        elif key == Qt.Key_O:
            c.insertText("\n")
            c.movePosition(QTextCursor.PreviousCharacter)
        elif key == Qt.Key_T:
            transpose_text(c)
        else:
            return False
        edit.setTextCursor(c)
        return True

    def _line(self, edit, key):
        if key == Qt.Key_A:
            edit.home(False)
        elif key == Qt.Key_E:
            edit.end(False)
        elif key == Qt.Key_B:
            edit.cursorBackward(False)
        elif key == Qt.Key_F:
            edit.cursorForward(False)
        elif edit.isReadOnly():
            return False
        elif key == Qt.Key_D:
            edit.del_()
        elif key == Qt.Key_H:
            edit.backspace()
        elif key == Qt.Key_K:
            self._kill(edit.text()[edit.cursorPosition():])
            edit.end(True)
            edit.del_()
        elif key == Qt.Key_Y:
            edit.insert(self.killed)
        elif key == Qt.Key_T:
            transpose_line(edit)
        else:
            return False
        return True


def transpose_text(c):
    if c.atBlockStart():
        return
    if c.atBlockEnd():
        c.movePosition(QTextCursor.PreviousCharacter)
    c.movePosition(QTextCursor.PreviousCharacter)
    c.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, 2)
    pair = c.selectedText()
    if len(pair) == 2:
        c.insertText(pair[::-1])


def transpose_line(edit):
    text, i = edit.text(), edit.cursorPosition()
    if len(text) < 2 or i == 0:
        return
    i = min(i, len(text) - 1)
    edit.setText(text[:i - 1] + text[i] + text[i - 1] + text[i + 1:])
    edit.setCursorPosition(i + 1)


class WheelScrollsPage(QObject):
    """Wheel/trackpad over a spin box or combo box scrolls the enclosing page instead of changing the value."""

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Wheel or not isinstance(obj, (QAbstractSpinBox, QComboBox, QSlider)):
            return False
        area = obj.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QCoreApplication.sendEvent(area.viewport(), event)
        return True


def install(app):
    filters = [ControlKeyEditing(app), WheelScrollsPage(app)]
    for f in filters:
        app.installEventFilter(f)
    return filters
