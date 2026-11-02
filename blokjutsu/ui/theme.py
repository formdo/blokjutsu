"""Appearance: a style sheet computed from the system palette (re-applied on light/dark switches) and icons.

Interactive controls use one brand blue (ACCENT): solid with white text for the primary action, blue text on a
faint blue tint for secondary buttons. Focus rings and text selection keep the user's system accent color
(QPalette.Highlight), which is read and never set.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPalette
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QFrame, QLineEdit, QPushButton

from .toggle import mix

RESOURCES = Path(__file__).resolve().parents[1] / "resources"
ACCENT = QColor(54, 98, 227)
MEDIUM = 500      # between regular (400) and bold (700); SF Pro has a true Medium face
MARGIN = 20       # outer and panel-to-divider spacing
CONTROL_HEIGHT = 32   # single-line controls: 20 min-height + 2×5 padding + 2×1 border
LIGHT_WINDOW = QColor(251, 251, 249)


def enlarge(widget, factor=1.1):
    """The native system font, a little larger than the rest of the UI."""
    font = widget.font()
    font.setPointSizeF(round(font.pointSizeF() * factor))
    widget.setFont(font)


def medium(widget):
    font = widget.font()
    font.setWeight(QFont.Medium)
    widget.setFont(font)
    return widget

TEMPLATE = """
QMainWindow, QDialog, QSplitter, QScrollArea#panel,
QScrollArea#panel > QWidget#qt_scrollarea_viewport, QWidget#panelContent,
QWidget#sheetPanel, QScrollArea#sheetScroll, QScrollArea#sheetScroll > QWidget#qt_scrollarea_viewport
{{ background: {window}; }}
QSplitter#sheetSplitter::handle {{ background: transparent; }}
QFrame#card {{ background: transparent; border: none; border-bottom: 1px solid {hairline}; }}
QSplitter::handle {{ background: {hairline}; }}
QFrame#hairline {{ background: {hairline}; border: none; }}
QProgressBar {{ background: {tint}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {brand}; border-radius: 3px; }}

QPlainTextEdit#promptEdit {{
    background: {base}; border: 1px solid {hairline}; border-radius: 10px; padding: 5px;
}}
QPlainTextEdit#promptEdit:focus {{ border: 2px solid {accent}; padding: 4px; }}
QLabel#textBox {{
    background: {base}; border: 1px solid {hairline}; border-radius: 10px; padding: 8px 10px;
}}

QLineEdit, QAbstractSpinBox, QComboBox {{
    background: {tint}; border: 1px solid transparent; border-radius: 8px;
    padding: 5px 8px; min-height: 20px; selection-background-color: {accent}; selection-color: {on_accent};
}}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {{
    background: transparent; border: none; padding: 0; min-height: 0;
}}
QAbstractSpinBox {{ padding-right: 22px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; margin: 3px 3px 0 0; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; margin: 0 3px 3px 0; }}
QAbstractSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::down-arrow:disabled {{ image: none; }}
QComboBox {{ padding-left: 10px; padding-right: 26px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 24px; border: none;
}}
QComboBox::down-arrow {{ image: url("{down}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {base}; border: 1px solid {hairline}; border-radius: 8px; padding: 4px;
    selection-background-color: {accent}; selection-color: {on_accent};
}}

QPushButton, QToolButton#folderButton {{
    background: {tint}; color: {brand_text}; border: none; border-radius: 8px; padding: 6px 12px;
    font-weight: {medium};
}}
QPushButton:hover, QToolButton#folderButton:hover {{ background: {tint_hover}; }}
QPushButton:pressed, QToolButton#folderButton:pressed {{ background: {tint_pressed}; }}
QPushButton:disabled {{ color: {muted}; }}

QPushButton#destructive {{ color: {danger}; background: {danger_tint}; }}
QPushButton#destructive:hover {{ background: {danger_hover}; }}

QPushButton[card="true"] {{
    background: transparent; color: {soft_text}; border: 1px solid {soft_line}; padding: 5px 11px;
}}
QPushButton[card="true"]:hover {{ background: {tint}; }}
QPushButton[card="true"]:pressed {{ background: {tint_hover}; }}
QPushButton#destructive[card="true"] {{ color: {soft_red_text}; border-color: {soft_red_line}; }}
QPushButton#destructive[card="true"]:hover {{ background: {danger_tint}; }}

QMessageBox QPushButton, QDialogButtonBox QPushButton {{ min-width: 64px; }}

QPushButton#primary, QPushButton:default {{
    background: {brand}; color: white; font-weight: {medium}; border-radius: 10px; padding: 9px 18px;
}}
QPushButton#primary:hover, QPushButton:default:hover {{ background: {brand_hover}; }}
QPushButton#primary:pressed, QPushButton:default:pressed {{ background: {brand_pressed}; }}
"""


def colors(palette):
    base, window = palette.color(QPalette.Base), palette.color(QPalette.Window)
    text, accent = palette.color(QPalette.Text), palette.color(QPalette.Highlight)
    dark = window.lightness() < 128
    ground = window if dark else base
    return dict(
        base=base.name(), window=window.name(), text=text.name(), accent=accent.name(),
        on_accent=palette.color(QPalette.HighlightedText).name(),
        hairline=mix(window, text, 0.14).name(),
        muted=mix(base, text, 0.45).name(),
        tint=mix(ground, ACCENT, 0.14 if dark else 0.052).name(),
        tint_hover=mix(ground, ACCENT, 0.22 if dark else 0.10).name(),
        tint_pressed=mix(ground, ACCENT, 0.30 if dark else 0.165).name(),
        soft_line=mix(ground, ACCENT, 0.45 if dark else 0.30).name(),
        soft_text=(mix(ACCENT, text, 0.3) if dark else mix(ACCENT, base, 0.25)).name(),
        soft_red_line=mix(ground, QColor(215, 0, 21), 0.45 if dark else 0.28).name(),
        soft_red_text=(QColor(255, 105, 97) if dark else mix(QColor(215, 0, 21), base, 0.2)).name(),
        brand=ACCENT.name(),
        brand_text=(mix(ACCENT, text, 0.45) if dark else ACCENT).name(),
        brand_hover=mix(ACCENT, base, 0.10).name(),
        brand_pressed=mix(ACCENT, QColor(0, 0, 0), 0.15).name(),
        medium=MEDIUM,
        danger=(QColor(255, 69, 58) if dark else QColor(215, 0, 21)).name(),
        danger_tint=mix(ground, QColor(215, 0, 21), 0.16 if dark else 0.06).name(),
        danger_hover=mix(ground, QColor(215, 0, 21), 0.26 if dark else 0.12).name(),
        up=(RESOURCES / "chevron-up.svg").as_posix(),
        down=(RESOURCES / "chevron-down.svg").as_posix(),
    )


def apply(widget):
    """Light mode: off-white window behind white text boxes; dark mode: the system palette unchanged."""
    palette = QApplication.palette()
    if palette.color(QPalette.Window).lightness() >= 128:
        palette.setColor(QPalette.Window, LIGHT_WINDOW)
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
    # backgrounds are set in the style sheet: Qt ignores setPalette on widgets that have style sheets
    widget.setStyleSheet(TEMPLATE.format(**colors(palette)))


def follow_color_scheme(widget):
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda *_: QTimer.singleShot(0, lambda: apply(widget)))


APPEARANCES = ("System", "Light", "Dark")


def set_appearance(name):
    """Override the macOS appearance for this app (Qt ≥ 6.8); returns False if unsupported."""
    from PySide6.QtCore import Qt

    hints = QGuiApplication.styleHints()
    scheme = getattr(Qt, "ColorScheme", None)
    if scheme is None or not hasattr(hints, "setColorScheme"):
        return False
    hints.setColorScheme({"System": scheme.Unknown, "Light": scheme.Light, "Dark": scheme.Dark}[name])
    return True


def window_background(scroll_area):
    """Mark a scroll area as a panel so the style sheet paints it, and its content, in the window color."""
    scroll_area.setObjectName("panel")
    scroll_area.setFrameShape(QFrame.NoFrame)
    if scroll_area.widget() is not None:
        scroll_area.widget().setObjectName("panelContent")


def button_padding(button):
    """Per-side horizontal padding the style sheet gives this button, plus a few pixels' margin."""
    if button.property("card"):
        return 14
    if button.isDefault() or button.objectName() == "primary":
        return 22
    return 16


def fit_button(button):
    """Minimum width from the medium-weight text the style sheet draws; the native size hint measures regular
    weight without the style-sheet padding, which clipped labels such as 'Cancel'."""
    font = QFont(button.font())
    font.setWeight(QFont.Medium)
    width = QFontMetrics(font).horizontalAdvance(button.text().replace("&&", "&")) + 2 * button_padding(button)
    if not button.icon().isNull():
        width += button.iconSize().width() + 6
    button.setMinimumWidth(width)
    vertical = 9 if button.isDefault() or button.objectName() == "primary" else 6
    button.setMinimumHeight(max(button.minimumHeight(), QFontMetrics(font).height() + 2 * vertical + 4))  # descenders


SPIN_TEXT_INSET = 9    # the spin box ignores style-sheet padding for its text; this lines it up with line edits


def inset_spin_text(spin):
    edit = spin.findChild(QLineEdit)
    if edit is not None:
        edit.setTextMargins(SPIN_TEXT_INSET, 0, 0, 0)


class ButtonFitter(QObject):
    """App-wide: size every push button to its label, and inset spin-box text, when polished or shown."""

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Polish, QEvent.Show):
            if isinstance(obj, QPushButton):
                fit_button(obj)
            elif isinstance(obj, QAbstractSpinBox):
                inset_spin_text(obj)
        return False


def install_button_fitter(app):
    fitter = ButtonFitter(app)
    app.installEventFilter(fitter)
    return fitter
