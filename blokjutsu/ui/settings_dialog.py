"""Settings… (⌘,): app-level preferences that are not generation parameters."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QPushButton, QSpinBox

from ..settings import app_home, tilde
from .toggle import ToggleSwitch
from .widgets import labelled


class SettingsDialog(QDialog):
    def __init__(self, live_preview, cache_mb, reveal, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.live_preview = ToggleSwitch()
        self.live_preview.setChecked(live_preview)
        self.cache_mb = QSpinBox(minimum=256, maximum=262144, singleStep=1024, suffix=" MB")
        self.cache_mb.setValue(cache_mb)
        home = QLabel(tilde(app_home()))
        home.setWordWrap(True)
        show = QPushButton("Show in Finder")
        show.clicked.connect(lambda: reveal(app_home()))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout(self)
        form.addRow(labelled("Live preview", "live_preview"), self.live_preview)
        form.addRow(labelled("Image cache", "image_cache"), self.cache_mb)
        form.addRow(labelled("App data", "app_data"), home)
        form.addRow("", show)
        form.addRow(buttons)
