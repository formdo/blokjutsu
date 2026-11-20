"""LoRAs in the interface: a row per LoRA in use, trigger words highlighted in the prompt, the LoRA library
(pick one to add, rename, set its trigger word, delete), and adding LoRAs from Hugging Face or from a file."""
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QRegularExpression, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPalette, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from .. import lora as R
from .. import network
from ..params import DEFAULT_MODEL
from .blocks import BlockSpinner
from .icons import RED, icon
from .theme import medium
from .widgets import labelled

TRIGGER = QColor(138, 79, 216)          # the LoRA colour: trigger words in the prompt and on each LoRA's row
SLIDER_MAX = 1.5
FIND_URL = "https://huggingface.co/models?other=base_model:adapter:OpenMOSS-Team/MOSS-Image-Base"
log = logging.getLogger("blokjutsu.loras")


def model_config():
    """The downloaded transformer's dimensions, to check LoRAs against (MOSS-Image's own if not downloaded)."""
    try:
        from ..backend import local_snapshot
        return R.model_config(local_snapshot(DEFAULT_MODEL))
    except Exception:
        return None


def amount(n):
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def duration(seconds):
    s = int(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def grow(form):
    """Fields that fill the width (macOS forms otherwise keep them at their natural, often cramped, size)."""
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    return form


def chip(text):
    """A trigger word drawn as a tinted chip."""
    label = QLabel(text)
    label.setStyleSheet(f"QLabel {{ color: {TRIGGER.name()}; background: rgba(138, 79, 216, 38); "
                        "border-radius: 5px; padding: 1px 6px; }")
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


class TriggerHighlighter(QSyntaxHighlighter):
    """Tints every exact occurrence of an active LoRA's trigger word; an edited word no longer matches."""

    def __init__(self, document):
        super().__init__(document)
        self.patterns = []
        self.format = QTextCharFormat()
        self.format.setForeground(TRIGGER)
        background = QColor(TRIGGER)
        background.setAlpha(38)
        self.format.setBackground(background)

    def set_triggers(self, triggers):
        words = sorted({t for t in triggers if t}, key=len, reverse=True)
        if words == getattr(self, "words", None):
            return               # typing is highlighted as it happens; rehighlighting mid-edit loses formats
        self.words = words
        self.patterns = [QRegularExpression(QRegularExpression.escape(w)) for w in words]
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern in self.patterns:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                m = matches.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), self.format)


class LoraRow(QWidget):
    """One LoRA in use: its name, strength, and trigger word (or that it needs none)."""
    changed = Signal()
    removed = Signal(object)
    add_trigger = Signal(str)

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = dict(item)                # a picture entry: id, name, sha256, strength, trigger
        self.missing = R.locate(self.item) is None
        name = medium(QLabel(self.item.get("name") or "LoRA"))
        remove = QToolButton(icon=icon("remove"), toolTip="Stop using this LoRA", objectName="folderButton")
        remove.clicked.connect(lambda: self.removed.emit(self))
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(name, 1)
        top.addWidget(remove)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, round(SLIDER_MAX * 100))
        self.spin = QDoubleSpinBox(decimals=2, singleStep=0.05, minimum=0, maximum=R.MAX_STRENGTH)
        self.spin.setFixedWidth(84)
        self.spin.setToolTip("Strength: 0 is off, 1 is as the LoRA was trained")
        self.slider.valueChanged.connect(lambda v: self.spin.setValue(v / 100))
        self.spin.valueChanged.connect(self._strength)
        self.spin.setValue(float(self.item.get("strength", 1.0)))
        strength = QHBoxLayout()
        strength.setContentsMargins(0, 0, 0, 0)
        strength.addWidget(self.slider, 1)
        strength.addWidget(self.spin)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        trigger = self.item.get("trigger", "")
        self.add_button = QPushButton("Add to prompt")
        self.add_button.setProperty("card", True)
        self.add_button.setToolTip("Put the trigger word at the start of the prompt")
        self.add_button.clicked.connect(lambda: self.add_trigger.emit(trigger))
        self.add_button.hide()
        if self.missing:
            note = QLabel("Not in your LoRAs any more: add it again, or remove it here")
            note.setStyleSheet(f"color: {RED};")
            note.setWordWrap(True)
            bottom.addWidget(note, 1)
        elif trigger:
            bottom.addWidget(QLabel("Trigger"))
            bottom.addWidget(chip(trigger))
            bottom.addStretch(1)
            bottom.addWidget(self.add_button)
        else:
            note = QLabel("No trigger word: it applies to the whole picture")
            note.setForegroundRole(QPalette.PlaceholderText)
            bottom.addWidget(note, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addLayout(strength)
        layout.addLayout(bottom)

    def _strength(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(round(min(value, SLIDER_MAX) * 100))
        self.slider.blockSignals(False)
        self.item["strength"] = round(value, 2)
        self.changed.emit()

    def show_trigger_missing(self, prompt):
        trigger = self.item.get("trigger", "")
        self.add_button.setVisible(bool(trigger) and not self.missing and trigger not in prompt)


def works_with(family):
    return {"moss": "MOSS-Image-SFT and -Base"}.get(family or "moss", R.family_name(family))


def describe_check(tensors, card="", card_data=None, metadata=None, adapter_config=None, name="", source=None):
    """The info to store for a LoRA, after checking which model family it fits (raises ValueError if none)."""
    family, _, ranks = R.detect(tensors, {"moss": model_config()})
    alpha = R.alpha_from(adapter_config)
    return {"name": name, "trigger": R.find_trigger(card, card_data, metadata), "strength": R.find_strength(card),
            "trained_on": R.trained_on(card_data), "license": (card_data or {}).get("license", ""),
            "source": source or {}, "ranks": ranks, "family": family, "recommended": R.recommended(card),
            "alpha": {"lora_alpha": alpha[0], "r": alpha[1]} if alpha else None}


def add_from_file(parent):
    """Choose a .safetensors file, check it, and add it to the library; returns its info or None."""
    path, _ = QFileDialog.getOpenFileName(parent, "Add a LoRA", str(Path.home()), "LoRA files (*.safetensors)")
    if not path:
        return None
    try:
        tensors, metadata = R.read_header(path)
        adapter = Path(path).with_name("adapter_config.json")
        config = json.loads(adapter.read_text()) if adapter.exists() else None
        readme = Path(path).with_name("README.md")
        card = readme.read_text(errors="replace")[:40_000] if readme.exists() else ""
        info = describe_check(tensors, card, R.card_data_of(card), metadata, config, name=Path(path).stem,
                              source={"file": Path(path).name})
    except (OSError, ValueError) as exc:
        QMessageBox.warning(parent, "Add a LoRA", f"{Path(path).name} can't be used.\n\n{exc}")
        return None
    return R.add(path, info)


class HubImport(QDialog):
    """Add a LoRA from Hugging Face in one step. Download first asks for the repo's card and the header of its
    file (small requests), checks that it fits MOSS-Image, and only then downloads it. Nothing is requested
    until Download is clicked. Afterwards the name and trigger word can be corrected.

    Models use the same window (ui/models.py), with these attributes and the hook methods below replaced."""
    TITLE = "Add a LoRA from Hugging Face"
    FIND_TEXT, FIND_URL = "Find LoRAs on Hugging Face", FIND_URL
    FIND_TIP = "Opens huggingface.co in your web browser, showing LoRAs made for MOSS-Image"
    INFO_COMMAND = "lora-info"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.TITLE)
        self.process, self.buffer, self.found, self.info, self.added, self.mode, self.tmp = (None, b"", None, None,
                                                                                               None, None, None)
        self.link = QLineEdit(placeholderText="https://huggingface.co/owner/name, or owner/name")
        self.link.textChanged.connect(lambda t: self.go.setEnabled(bool(t.strip()) and self.process is None))
        self.link.returnPressed.connect(lambda: self.go.isEnabled() and self.go.click())
        sent = QLabel("Download contacts huggingface.co. " + network.WHAT_IS_SENT)
        sent.setForegroundRole(QPalette.PlaceholderText)
        sent.setWordWrap(True)
        find = QPushButton(icon("external"), self.FIND_TEXT)
        find.setToolTip(self.FIND_TIP)
        find.setProperty("card", True)
        find.setAutoDefault(False)
        find.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.FIND_URL)))

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.details = QWidget()
        self._build_details(grow(QFormLayout(self.details)))
        self.details.hide()
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.hide()
        self.detail = QLabel()
        self.detail.setForegroundRole(QPalette.PlaceholderText)
        self.detail.hide()
        self.first = None                    # (time, bytes) at the first progress report, for the rate
        self.spinner = BlockSpinner()
        self.spinner.hide()
        busy = QHBoxLayout()
        busy.addWidget(self.spinner, 0, Qt.AlignTop)
        busy.addWidget(self.status, 1)

        self.go = QPushButton("Download", objectName="primary")
        self.go.setEnabled(False)
        self.go.setDefault(True)
        self.go.clicked.connect(self._go)
        self.cancel = QPushButton("Cancel")
        self.cancel.setAutoDefault(False)
        self.cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(find)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.go)

        layout = QVBoxLayout(self)
        layout.addWidget(self.link)
        layout.addWidget(sent)
        layout.addLayout(busy)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        layout.addWidget(self.details)
        layout.addStretch(1)
        layout.addLayout(buttons)
        self.resize(640, 440)

    # what differs between LoRAs and models

    def _build_details(self, form):
        self.name = QLineEdit()
        self.trigger = QLineEdit(placeholderText="none")
        self.facts = {k: note_label() for k in ("File", "Trained on", "Works with", "Strength", "Settings",
                                                "License")}
        form.addRow(labelled("Name", "lora_name"), self.name)
        form.addRow(labelled("Trigger", "lora_trigger"), self.trigger)
        for key, label in self.facts.items():
            form.addRow(medium(QLabel(key)), label)

    def _save_edits(self):
        R.update(self.added["id"], name=self.name.text().strip() or self.added["name"],
                 trigger=self.trigger.text().strip())

    def _download(self, found, folder):
        model = R.family_name(self.info.get("family")) if self.info else "MOSS-Image"
        self.status.setText(f"It fits {model}. Downloading {found['file']} ({found['size'] / 1e6:.0f} MB)…")
        self._run("file", "lora", found["repo"], found["revision"], found["file"], folder)

    # the steps

    def _go(self):
        if self.added:                                   # Done: keep the corrected details
            self._save_edits()
            self.accept()
            return
        repo = R.repo_of(self.link.text())
        if not repo:
            self.status.setText("Paste a Hugging Face link, like https://huggingface.co/owner/name.")
            return
        self.found = self.info = None
        self.status.setText(f"Asking huggingface.co about {repo}…")
        self.spinner.start()
        self._run("info", self.INFO_COMMAND, repo)

    def _run(self, mode, *args):
        self.mode, self.buffer = mode, b""
        argv = network.download_command(*args)
        process = QProcess(self)
        process.setProgram(argv[0])
        process.setArguments(argv[1:])
        env = QProcessEnvironment()
        for key, value in network.download_environment().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(
            lambda: log.info("%s", bytes(process.readAllStandardError()).decode(errors="replace").rstrip()))
        process.finished.connect(self._finished)
        self.process = process
        self.go.setEnabled(False)
        self.link.setEnabled(False)
        process.start()

    def _read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        *lines, self.buffer = self.buffer.split(b"\n")
        for line in lines:
            kind, _, rest = line.decode(errors="replace").strip().partition(" ")
            if kind == "STATUS":
                self.status.setText(rest)
            elif kind == "PROGRESS":
                self._progress(*map(int, rest.split()))
            elif kind == "INFO":
                self._check(json.loads(rest))
            elif kind == "DONE" and self.mode == "file":
                self._store(rest)
            elif kind == "ERROR":
                self.status.setText(f"That didn't work: {rest}")
            if kind != "PROGRESS":
                log.info("%s", line.decode(errors="replace").rstrip())

    def _progress(self, done, total):
        """The bar, and below it: how much, how fast, time so far, and about how long is left."""
        now = time.monotonic()
        if self.first is None:
            self.first = (now, done)
        self.bar.show()
        self.bar.setRange(0, 1000)
        self.bar.setValue(int(1000 * done / max(total, 1)))
        t0, d0 = self.first
        text = f"{amount(done)} of {amount(total)} · {duration(now - t0)} so far"
        if now - t0 > 2 and done > d0:
            rate = (done - d0) / (now - t0)
            text += f" · {rate / 1e6:.0f} MB/s · about {duration((total - done) / rate)} left"
        self.detail.setText(text)
        self.detail.show()

    def _check(self, found):
        tensors = {k: (d, tuple(s)) for k, (d, s) in found["tensors"].items()}
        repo = found["repo"]
        try:
            self.info = describe_check(tensors, found["card"], found["card_data"], found["metadata"],
                                       found["adapter_config"], name=repo.split("/")[-1],
                                       source={"repo": repo, "revision": found["revision"], "file": found["file"]})
            self.found = found
        except ValueError as exc:
            self.status.setText(f"{repo} can't be used with Blokjutsu. {exc}")

    def _store(self, path):
        try:
            R.detect(R.read_header(path)[0], {"moss": model_config()})
            self.added = R.add(path, self.info, move=True)
        except (OSError, ValueError) as exc:
            self.status.setText(f"The downloaded file can't be used: {exc}")

    def _finished(self, code, status):
        self.process = None
        if self.mode == "info" and self.found:
            self.tmp = tempfile.mkdtemp(prefix="blokjutsu-download-")
            self._download(self.found, self.tmp)
            return
        self.bar.hide()
        self.detail.hide()
        self.first = None
        self.spinner.stop()
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.tmp = None
        if self.added:
            self._show_added()
        else:
            self.link.setEnabled(True)
            self.go.setEnabled(bool(self.link.text().strip()))

    def _show_added(self):
        info, f = self.added, self.found
        self.name.setText(info.get("name", ""))
        self.trigger.setText(info.get("trigger", ""))
        for key, value in (("File", f"{f['file']} ({f['size'] / 1e6:.0f} MB)"),
                           ("Trained on", info.get("trained_on") or "not stated"),
                           ("Works with", works_with(info.get("family"))),
                           ("Strength", f"{info.get('strength', 1.0):g}"),
                           ("Settings", R.settings_text(info.get("recommended")) or "the usual ones"),
                           ("License", info.get("license") or "not stated")):
            self.facts[key].setText(value)
        self.details.show()
        self.status.setText("Added to your LoRA library. Check its name and trigger word"
                            + (" (found on its page)." if info.get("trigger") else
                               ": its page names none. If it needs one, type it here."))
        self.go.setText("Done")
        self.go.setEnabled(True)
        self.cancel.hide()

    def reject(self):
        if self.process is not None:
            self.process.kill()
        super().reject()


class LoraChooser(QDialog):
    """Which LoRAs the picture uses: a tick list of the library. Ticking adds a LoRA to the controls at once,
    unticking removes it. Manage LoRA Library… adds and deletes LoRAs."""

    def __init__(self, add, remove, in_use, parent=None, family="moss"):
        super().__init__(parent)
        self.setWindowTitle("Choose LoRAs")
        self.add, self.remove, self.in_use, self.family = add, remove, set(in_use), family
        self.list = QListWidget()
        self.list.itemChanged.connect(self._ticked)
        self.empty = QLabel("Your LoRA library is empty. Manage LoRA Library… adds LoRAs from Hugging Face or "
                            "from files.")
        self.empty.setWordWrap(True)
        self.empty.setForegroundRole(QPalette.PlaceholderText)
        self.others = QLabel()
        self.others.setWordWrap(True)
        self.others.setForegroundRole(QPalette.PlaceholderText)
        manage = QPushButton("Manage LoRA Library…")
        manage.setAutoDefault(False)
        manage.clicked.connect(self._manage)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(manage)
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(indented(medium(QLabel("Local LoRAs"))))
        layout.addWidget(self.list, 1)
        layout.addWidget(self.empty)
        layout.addWidget(self.others)
        layout.addLayout(bottom)
        self.resize(460, 420)
        self._reload()

    def _reload(self):
        everything = R.library()
        self.items = [i for i in everything if i.get("family", "moss") == self.family]
        hidden = len(everything) - len(self.items)
        self.others.setText(f"{hidden} LoRA{'s are' if hidden != 1 else ' is'} for another model and "
                            f"{'are' if hidden != 1 else 'is'} not listed here." if hidden else "")
        self.others.setVisible(bool(hidden))
        self.list.blockSignals(True)
        self.list.clear()
        for info in self.items:
            trigger = info.get("trigger", "")
            item = QListWidgetItem(info.get("name", "") + (f"   ·   {trigger}" if trigger else ""))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if info["id"] in self.in_use else Qt.Unchecked)
            item.setToolTip(f"Trigger word: {trigger}" if trigger else "No trigger word: applies to the whole picture")
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.empty.setVisible(not everything)

    def _ticked(self, item):
        info = self.items[self.list.row(item)]
        if item.checkState() == Qt.Checked and info["id"] not in self.in_use:
            self.in_use.add(info["id"])
            self.add(info)
        elif item.checkState() != Qt.Checked and info["id"] in self.in_use:
            self.in_use.discard(info["id"])
            self.remove(info["id"])

    def _manage(self):
        LoraLibrary(self, self.in_use).exec()
        gone = self.in_use - {info["id"] for info in R.library()}
        for lora_id in gone:
            self.in_use.discard(lora_id)
            self.remove(lora_id)
        self._reload()


def indented(label, pixels=3):
    """A heading nudged right to line up with the box below it."""
    label.setContentsMargins(pixels, 0, 0, 0)
    return label


def note_label(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextBrowserInteraction)
    label.setOpenExternalLinks(True)
    return label


class LoraLibrary(QDialog):
    """The LoRAs on this Mac: add them from Hugging Face or a file, correct their names, trigger words and
    strengths, delete them."""

    def __init__(self, parent=None, in_use=()):
        super().__init__(parent)
        self.setWindowTitle("Manage LoRA Library")
        self.in_use = set(in_use)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemSelectionChanged.connect(self._selection)
        hub = QPushButton("From Hugging Face…")
        hub.clicked.connect(self._from_hub)
        local = QPushButton("From a file…")
        local.clicked.connect(self._from_file)
        sources = QHBoxLayout()
        sources.addWidget(hub)
        sources.addWidget(local)

        self.name = QLineEdit()
        self.name.editingFinished.connect(lambda: self._save("name", self.name.text().strip()))
        self.trigger = QLineEdit(placeholderText="none")
        self.trigger.editingFinished.connect(lambda: self._save("trigger", self.trigger.text().strip()))
        self.strength = QDoubleSpinBox(decimals=2, singleStep=0.05, minimum=0, maximum=R.MAX_STRENGTH)
        self.strength.setFixedWidth(100)
        self.strength.editingFinished.connect(lambda: self._save("strength", round(self.strength.value(), 2)))
        self.settings = QLineEdit(placeholderText="the usual ones")
        self.settings.editingFinished.connect(self._save_settings)
        self.source, self.base, self.works, self.license, self.size = (note_label() for _ in range(5))
        form = grow(QFormLayout())
        form.addRow(labelled("Name", "lora_name"), self.name)
        form.addRow(labelled("Trigger", "lora_trigger"), self.trigger)
        form.addRow(labelled("Strength", "lora_strength"), self.strength)
        form.addRow(labelled("Settings", "lora_settings"), self.settings)
        for key, label in (("From", self.source), ("Trained on", self.base), ("Works with", self.works),
                           ("License", self.license), ("Size", self.size)):
            form.addRow(medium(QLabel(key)), label)
        self.detail = QWidget()
        self.detail.setLayout(form)

        left = QVBoxLayout()
        left.addWidget(indented(medium(QLabel("Local LoRA library"))))
        left.addWidget(self.list, 1)
        left.addLayout(sources)
        right = QVBoxLayout()
        right.addSpacing(24)
        right.addWidget(self.detail)
        right.addStretch(1)
        middle = QHBoxLayout()
        middle.addLayout(left, 1)
        middle.addSpacing(12)
        middle.addLayout(right, 1)

        self.empty = QLabel("No LoRAs yet. Add one from Hugging Face, or from a .safetensors file you have.")
        self.empty.setWordWrap(True)
        self.empty.setForegroundRole(QPalette.PlaceholderText)
        self.delete = QPushButton("Delete selected LoRAs", objectName="destructive")
        self.delete.setAutoDefault(False)
        self.delete.clicked.connect(self._delete)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.delete)
        bottom.addWidget(self.empty, 1)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addLayout(middle, 1)
        layout.addLayout(bottom)
        self.resize(780, 460)
        self._reload()

    def _reload(self, select=None):
        self.items = R.library()
        self.list.blockSignals(True)
        self.list.clear()
        for info in self.items:
            self.list.addItem(info.get("name", "") + ("  (in use)" if info["id"] in self.in_use else ""))
        self.list.blockSignals(False)
        index = next((i for i, info in enumerate(self.items) if info["id"] == select), 0 if self.items else -1)
        self.list.setCurrentRow(index)
        self._show(index)
        self._selection()
        self.empty.setVisible(not self.items)

    def _current(self):
        i = self.list.currentRow()
        return self.items[i] if 0 <= i < len(self.items) else None

    def _selected(self):
        return [self.items[self.list.row(item)] for item in self.list.selectedItems()]

    def _selection(self):
        n = len(self._selected())
        self.delete.setEnabled(n > 0)
        self.delete.setText("Delete selected LoRA" if n == 1 else "Delete selected LoRAs")

    def _show(self, _index):
        info = self._current()
        self.detail.setEnabled(info is not None)
        if info is None:
            for w in (self.name, self.trigger, self.settings, self.source, self.base, self.works, self.license,
                      self.size):
                w.setText("")
            return
        self.name.setText(info.get("name", ""))
        self.trigger.setText(info.get("trigger", ""))
        self.strength.setValue(float(info.get("strength", 1.0)))
        source = info.get("source", {})
        self.source.setText(f'<a href="https://huggingface.co/{source["repo"]}">{source["repo"]}</a>'
                            if source.get("repo") else source.get("file", "a file"))
        self.base.setText(info.get("trained_on") or "not stated")
        self.works.setText(works_with(info.get("family")))
        self.settings.setText(R.settings_text(info.get("recommended")))
        self.license.setText(info.get("license") or "not stated")
        self.size.setText(f"{Path(info['path']).stat().st_size / 1e6:.0f} MB")

    def _save(self, key, value):
        info = self._current()
        if info is not None and info.get(key) != value:
            R.update(info["id"], **{key: value})
            self._reload(info["id"])

    def _save_settings(self):
        """Read settings typed as on a model card ('4 steps, adherence 1'); text that names none is put back."""
        info = self._current()
        if info is None:
            return
        rec = R.settings(self.settings.text())
        if self.settings.text().strip() and not rec:
            self.settings.setText(R.settings_text(info.get("recommended")))
            return
        self._save("recommended", rec)

    def _from_hub(self):
        dialog = HubImport(self)
        if dialog.exec() and dialog.added:
            self._reload(dialog.added["id"])

    def _from_file(self):
        info = add_from_file(self)
        if info:
            self._reload(info["id"])

    def _delete(self):
        """Ask only if some would be lost for good: LoRAs from Hugging Face can be fetched again."""
        chosen = self._selected()
        if not chosen:
            return
        local = [i.get("name", "") for i in chosen if not i.get("source", {}).get("repo")]
        if local:
            box = QMessageBox(QMessageBox.Warning, "Delete LoRAs",
                              f"Delete {len(chosen)} LoRA{'s' if len(chosen) != 1 else ''}?", parent=self)
            box.setInformativeText(f"{', '.join(local)} came from {'a file' if len(local) == 1 else 'files'}, so "
                                   "Blokjutsu can't fetch {} again. Pictures made with {} can't be remade until "
                                   "you add {} again.".format(*(("it", "it", "it") if len(local) == 1
                                                                else ("them", "them", "them"))))
            delete = box.addButton("Delete", QMessageBox.DestructiveRole)
            box.setDefaultButton(box.addButton(QMessageBox.Cancel))
            box.exec()
            if box.clickedButton() is not delete:
                return
        for info in chosen:
            R.remove(info["id"])
        self._reload()
