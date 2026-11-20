"""Your own models in the interface: adding them from Hugging Face or from a folder or file, and the model library
window. Both work like their LoRA counterparts (ui/loras.py), so similar things behave alike."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from .. import lora as R
from .. import models as M
from ..params import EDIT_MODELS, MODELS
from .loras import HubImport, grow, indented, model_config, note_label
from .theme import medium
from .widgets import labelled

FIND_MODELS = "https://huggingface.co/models?other=base_model:finetune:OpenMOSS-Team/MOSS-Image-Base"
PART_NAMES = {"text_encoder": "text encoder", "vae": "image decoder", "scheduler": "scheduler",
              "tokenizer": "tokenizer"}


def describe_model(found_tensors, card="", card_data=None, name="", source=None):
    """The info to store for a model, after checking its image model fits MOSS-Image."""
    M.check_transformer(found_tensors, model_config())
    return {"name": name, "trained_on": R.trained_on(card_data), "license": (card_data or {}).get("license", ""),
            "recommended": M.recommended(card), "source": source or {}}


def settings_text(info):
    return R.settings_text(info.get("recommended")) or "the usual ones"


class ModelHubImport(HubImport):
    TITLE = "Add a model from Hugging Face"
    FIND_TEXT, FIND_URL = "Find models on Hugging Face", FIND_MODELS
    FIND_TIP = "Opens huggingface.co in your web browser, showing fine-tunes of MOSS-Image"
    INFO_COMMAND = "model-info"

    def _build_details(self, form):
        self.name = QLineEdit()
        self.facts = {k: note_label() for k in ("Downloaded", "Shared", "Trained on", "Settings", "License")}
        form.addRow(labelled("Name", "model_name"), self.name)
        for key, label in self.facts.items():
            form.addRow(medium(QLabel(key)), label)

    def _check(self, found):
        tensors = {k: (d, tuple(s)) for k, (d, s) in found["tensors"].items()}
        repo = found["repo"]
        try:
            self.info = describe_model(tensors, found["card"], found["card_data"], name=repo.split("/")[-1],
                                       source={"repo": repo, "revision": found["revision"]})
            self.found = found
        except ValueError as exc:
            self.status.setText(f"{repo} can't be used with Blokjutsu. {exc}")

    def _download(self, found, folder):
        free = shutil.disk_usage(folder).free
        if found["size"] > free - (2 << 30):
            self.status.setText(f"It fits MOSS-Image, but needs {found['size'] / 1e9:.1f} GB and only "
                                f"{free / 1e9:.1f} GB is free.")
            self.found = None
            self._finished(0, None)
            return
        self.status.setText(f"It fits MOSS-Image. Downloading {found['size'] / 1e9:.1f} GB"
                            + (f"; its {', '.join(PART_NAMES[p] for p in found['reuse'])} are already here"
                               if found["reuse"] else "") + "…")
        self.target = folder
        self._run("file", "model-files", found["repo"], found["revision"], folder, *[n for n, _ in found["fetch"]])

    def _store(self, path):
        try:
            source = Path(path)
            if self.found["layout"] == "single":
                source = source / self.found["fetch"][0][0]
            weights = source if source.is_file() else M.transformer_weights(source)
            M.check_transformer(M.header_of(weights), model_config())
            self.added = M.add(source, self.info, move=True)
        except (OSError, ValueError) as exc:
            self.status.setText(f"The downloaded model can't be used: {exc}")

    def _save_edits(self):
        M.update(self.added["id"], name=self.name.text().strip() or self.added["name"])

    def _show_added(self):
        info, f = self.added, self.found
        self.name.setText(info.get("name", ""))
        self.facts["Downloaded"].setText(f"{f['size'] / 1e9:.1f} GB")
        self.facts["Shared"].setText("its " + ", ".join(PART_NAMES[p] for p in f["reuse"]) +
                                     " from MOSS-Image" if f["reuse"] else "nothing: it has all its own parts")
        self.facts["Trained on"].setText(info.get("trained_on") or "not stated")
        self.facts["Settings"].setText(settings_text(info))
        self.facts["License"].setText(info.get("license") or "not stated")
        self.details.show()
        self.status.setText("Added to your model library. Choose it under Model in Advanced options.")
        self.go.setText("Done")
        self.go.setEnabled(True)
        self.cancel.hide()


def add_model_from_disk(parent, folder=False):
    """Choose a model folder (with transformer/ and any other parts) or one image-model .safetensors file."""
    if folder:
        path = QFileDialog.getExistingDirectory(parent, "Add a model folder", str(Path.home()))
    else:
        path, _ = QFileDialog.getOpenFileName(parent, "Add a model file", str(Path.home()),
                                              "Model files (*.safetensors)")
    if not path:
        return None
    source = Path(path)
    try:
        weights = source if source.is_file() else M.transformer_weights(source)
        if weights is None:
            raise ValueError("There is no image model in that folder: it needs a transformer/ folder, or use "
                             "From a file… for a single .safetensors file.")
        M.check_transformer(M.header_of(weights), model_config())
        readme = (source.parent if source.is_file() else source) / "README.md"
        card = readme.read_text(errors="replace")[:40_000] if readme.exists() else ""
        info = {"name": source.stem, "trained_on": R.trained_on(R.card_data_of(card)),
                "license": R.card_data_of(card).get("license", ""), "recommended": M.recommended(card),
                "source": {"file": source.name}}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        QMessageBox.warning(parent, "Add a model", f"{source.name} can't be used.\n\n{exc}")
        return None
    return M.add(source, info)


class ModelChooser(QDialog):
    """Which model the picture uses: a list of the models on this Mac with one ticked. Ticking another switches
    at once. Manage Model Library… adds and deletes models."""

    def __init__(self, choose, current, cached, manage, parent=None, family="moss"):
        super().__init__(parent)
        self.family = family
        self.setWindowTitle("Choose model")
        self.choose, self.current, self.cached, self.manage = choose, current, cached, manage
        self.list = QListWidget()
        self.list.itemChanged.connect(self._ticked)
        manage_button = QPushButton("Manage Model Library…")
        manage_button.setAutoDefault(False)
        manage_button.clicked.connect(self._manage)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(manage_button)
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(indented(medium(QLabel("Local models"))))
        layout.addWidget(self.list, 1)
        layout.addLayout(bottom)
        self.resize(460, 420)
        self._reload()

    def _reload(self):
        self.values = []
        self.list.blockSignals(True)
        self.list.clear()
        originals = EDIT_MODELS if self.family == "qwen-image" else MODELS
        entries = [(M.display_name(r), r, self.cached(r)) for r in originals.values()]
        entries += [(i.get("name", ""), M.PREFIX + i["id"], True) for i in M.library()
                    if i.get("family", "moss") == self.family]
        for name, value, here in entries:
            item = QListWidgetItem(name if here else f"{name}  (not downloaded)")
            item.setFlags((item.flags() | Qt.ItemIsUserCheckable) if here else Qt.NoItemFlags)
            item.setCheckState(Qt.Checked if value == self.current else Qt.Unchecked)
            self.list.addItem(item)
            self.values.append(value)
        self.list.blockSignals(False)

    def _ticked(self, item):
        value = self.values[self.list.row(item)]
        if item.checkState() == Qt.Checked and value != self.current:
            self.current = value
            self.choose(value)
        QTimer.singleShot(0, self._reload)   # exactly one stays ticked (not rebuilt inside its own signal)

    def _manage(self):
        self.manage()
        if M.is_library(self.current) and M.find(M.library_id(self.current)) is None:
            self.current = next(iter((EDIT_MODELS if self.family == "qwen-image" else MODELS).values()))
            self.choose(self.current)
        self._reload()


class ModelLibrary(QDialog):
    """The models on this Mac: the two originals and your own. Add, rename, delete; a deleted original can be
    downloaded again from here."""

    def __init__(self, parent=None, in_use="", cached=None, download_original=None, delete_original=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Model Library")
        self.in_use, self.cached = in_use, cached or (lambda repo: True)
        self.download_original, self.delete_original = download_original, delete_original
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemSelectionChanged.connect(self._selection)
        hub = QPushButton("From Hugging Face…")
        hub.clicked.connect(self._from_hub)
        local = QPushButton("From a folder…")
        local.clicked.connect(lambda: self._from_disk(True))
        single = QPushButton("From a file…")
        single.clicked.connect(lambda: self._from_disk(False))
        sources = QHBoxLayout()
        for b in (hub, local, single):
            sources.addWidget(b)

        self.name = QLineEdit()
        self.name.editingFinished.connect(self._rename)
        self.settings = QLineEdit(placeholderText="the usual ones")
        self.settings.editingFinished.connect(self._save_settings)
        self.source, self.base, self.license, self.size = (note_label() for _ in range(4))
        self.again = QPushButton("Download again…")
        self.again.setToolTip("Download this original model again")
        self.again.clicked.connect(self._download_again)
        form = grow(QFormLayout())
        form.addRow(labelled("Name", "model_name"), self.name)
        form.addRow(labelled("Settings", "model_settings"), self.settings)
        for key, label in (("From", self.source), ("Trained on", self.base),
                           ("License", self.license), ("Size", self.size)):
            form.addRow(medium(QLabel(key)), label)
        form.addRow("", self.again)
        self.form = form
        self.detail = QWidget()
        self.detail.setLayout(form)

        left = QVBoxLayout()
        left.addWidget(indented(medium(QLabel("Local model library"))))
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

        self.delete = QPushButton("Delete selected models", objectName="destructive")
        self.delete.setAutoDefault(False)
        self.delete.clicked.connect(self._delete)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.delete)
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addLayout(middle, 1)
        layout.addLayout(bottom)
        self.resize(820, 480)
        self._reload()

    def _reload(self, select=None):
        originals = [{"id": repo, "name": M.display_name(repo), "original": True, "here": self.cached(repo),
                      "source": {"repo": repo}, "license": "apache-2.0", "family": M.family_of(repo)}
                     for repo in [*MODELS.values(), *EDIT_MODELS.values()]]
        mine = [{**info, "original": False, "here": True} for info in M.library()]
        self.items = originals + mine
        self.list.blockSignals(True)
        self.list.clear()
        for info in self.items:
            text = info["name"] + ("" if info["here"] else "  (not downloaded)")
            value = info["id"] if info["original"] else M.PREFIX + info["id"]
            text += "  (in use)" if value == self.in_use else ""
            item = QListWidgetItem(text)
            if not info["here"]:
                item.setForeground(self.palette().color(QPalette.PlaceholderText))
            self.list.addItem(item)
        self.list.blockSignals(False)
        index = next((i for i, info in enumerate(self.items) if info["id"] == select), 0)
        self.list.setCurrentRow(index)
        self._show(index)
        self._selection()

    def _current(self):
        i = self.list.currentRow()
        return self.items[i] if 0 <= i < len(self.items) else None

    def _selected(self):
        return [self.items[self.list.row(item)] for item in self.list.selectedItems()]

    def _selection(self):
        chosen = [i for i in self._selected() if i["here"]]
        self.delete.setEnabled(bool(chosen))
        self.delete.setText("Delete selected model" if len(chosen) == 1 else "Delete selected models")

    def _show(self, _index):
        info = self._current()
        if info is None:
            return
        self.name.setText(info["name"])
        self.name.setReadOnly(info["original"])
        source = info.get("source", {})
        self.source.setText(f'<a href="https://huggingface.co/{source["repo"]}">{source["repo"]}</a>'
                            if source.get("repo") else source.get("file", "a file"))
        self.base.setText("—" if info["original"] else info.get("trained_on") or "not stated")
        self.settings.setText("" if info["original"] else R.settings_text(info.get("recommended")))
        self.settings.setReadOnly(info["original"])
        self.license.setText(info.get("license") or "not stated")
        self.size.setText(f"{M.folder_bytes(info['path']) / 1e9:.1f} GB" if not info["original"] else
                          f"about {M.ORIGINAL_SIZES[info['family']] / 1e9:.0f} GB" if info["here"] else
                          "not downloaded")
        self.form.setRowVisible(self.again, info["original"] and not info["here"])

    def _rename(self):
        info = self._current()
        name = self.name.text().strip()
        if info and not info["original"] and name and name != info["name"]:
            M.update(info["id"], name=name)
            self._reload(info["id"])

    def _save_settings(self):
        """Read settings typed as on a model card ('8 steps, adherence 1'); text that names none is put back."""
        info = self._current()
        if info is None or info["original"]:
            return
        rec = R.settings(self.settings.text())
        if self.settings.text().strip() and not rec:
            self.settings.setText(R.settings_text(info.get("recommended")))
            return
        if rec != (info.get("recommended") or {}):
            M.update(info["id"], recommended=rec)
            self._reload(info["id"])

    def _from_hub(self):
        dialog = ModelHubImport(self)
        if dialog.exec() and dialog.added:
            self._reload(dialog.added["id"])

    def _from_disk(self, folder):
        info = add_model_from_disk(self, folder)
        if info:
            self._reload(info["id"])

    def _download_again(self):
        info = self._current()
        if info and self.download_original:
            self.accept()
            self.download_original(info["id"])

    def _delete(self):
        """Always ask: even a model that can be downloaded again takes many gigabytes and a long wait."""
        chosen = [i for i in self._selected() if i["here"]]
        if not chosen:
            return
        originals = [i for i in chosen if i["original"]]
        freed = sum(M.ORIGINAL_SIZES[i["family"]] if i["original"] else M.folder_bytes(i["path"]) for i in chosen)
        detail = [f"This frees about {freed / 1e9:.0f} GB."]
        if originals:
            detail.append("Downloading an original again takes as much again, and a while.")
            left = [repo for repo in MODELS.values() if self.cached(repo) and repo not in {i["id"] for i in originals}]
            if not left and M.library():
                detail.append("Your other models use an original's text encoder and image decoder, so they "
                              "won't work until one is downloaded again.")
        hub = [i for i in chosen if not i["original"] and i.get("source", {}).get("repo")]
        disk = [i for i in chosen if not i["original"] and not i.get("source", {}).get("repo")]
        if hub:
            detail.append("Models from Hugging Face can be added again from there.")
        if disk:
            detail.append("Models added from this Mac are gone for good unless you still have the files.")
        names = ", ".join(i["name"] for i in chosen)
        box = QMessageBox(QMessageBox.Warning, "Delete models", f"Permanently delete {names}?", parent=self)
        box.setInformativeText(" ".join(detail))
        delete = box.addButton("Delete", QMessageBox.DestructiveRole)
        box.setDefaultButton(box.addButton(QMessageBox.Cancel))
        box.exec()
        if box.clickedButton() is not delete:
            return
        for info in chosen:
            if info["original"]:
                if self.delete_original:
                    self.delete_original(info["id"])
            else:
                M.remove(info["id"])
        self._reload()
