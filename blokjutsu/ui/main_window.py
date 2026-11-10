"""Main window: controls on the left, history on the right, worker wiring, settings persistence."""
from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QScrollArea, QSplitter,
    QVBoxLayout, QWidget,
)

from .. import __version__

from .. import layout as L
from .. import params as P
from .. import store
from ..backend import local_snapshot
from ..logs import clear_logs
from ..settings import Settings, app_home, default_output, physical_memory, prepare_home, tilde
from ..worker import DescribeJob, Job, Worker
from .controls import ControlsPanel
from .describe_dialog import DescribeDialog
from .download_dialog import DownloadDialog, caption_spec, model_spec
from .history import HistoryView
from .settings_dialog import SettingsDialog
from . import theme

USER_GUIDE = "https://github.com/OpenMOSS/MOSS-Image/blob/main/USERGUIDE.md"
REPO = "https://github.com/OpenMOSS/MOSS-Image"
PAPER = "https://arxiv.org/abs/2610.23374"
HOME_PAGE = "https://formdo.github.io/blokjutsu/"
NEEDED_MEMORY = 32 * 2**30
LOW_MEMORY_BELOW = 48 * 2**30     # Low memory is on by default below this
EDIT_ACTIONS = (("Undo", "undo", QKeySequence.Undo), ("Redo", "redo", QKeySequence.Redo), None,
                ("Cut", "cut", QKeySequence.Cut), ("Copy", "copy", QKeySequence.Copy),
                ("Paste", "paste", QKeySequence.Paste), ("Select All", "selectAll", QKeySequence.SelectAll))



def clear_work_files():
    """Delete every editor scratch file (masks, extended or cropped canvases)."""
    for path in (app_home() / "work").glob("*"):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def prune_work_files(days=30):
    """Drop editor scratch files (masks, extended canvases) older than `days`; saved images keep their own copies."""
    import time
    cutoff = time.time() - days * 86400
    for path in (app_home() / "work").glob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def confirm_action(parent, title, text, details, action):
    """Question alert with Cancel as the default and Esc button."""
    box = QMessageBox(QMessageBox.Question, title, text, parent=parent)
    box.setInformativeText(details)
    accept = box.addButton(action, QMessageBox.AcceptRole)
    cancel = box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is accept


def confirm_delete(parent, title, text, details, action="Delete"):
    """Caution alert; Cancel is the default and Esc button."""
    box = QMessageBox(QMessageBox.Warning, title, text, parent=parent)
    box.setInformativeText(details)
    delete = box.addButton(action, QMessageBox.DestructiveRole)
    cancel = box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is delete



def open_in_preview(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Preview", str(path)])
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class MainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.setWindowTitle("Blokjutsu")
        theme.apply(self)
        theme.follow_color_scheme(self)
        self.settings = Settings()
        prepare_home()
        self.live_preview = bool(self.settings.get("live_preview", True))
        self.backend = backend
        saved = self.settings.get("low_memory")
        backend.low_memory = bool(saved) if saved is not None else (physical_memory() or 0) < LOW_MEMORY_BELOW
        self.job_ids = itertools.count(1)

        self.controls = ControlsPanel()
        self.history = HistoryView(cache_mb=int(self.settings.get("image_cache_mb", 4096)))
        self.history.card_hooks = self._hook_card
        scroll = QScrollArea()
        scroll.setWidget(self.controls)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)
        theme.window_background(scroll)
        left = QWidget(objectName="panelContent")    # Generate stays put above the scrolling controls
        left.setAttribute(Qt.WA_StyledBackground)
        column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        bar = QHBoxLayout()
        bar.setContentsMargins(theme.MARGIN, theme.MARGIN - 4, theme.MARGIN, 6)
        bar.addWidget(self.controls.generate_button)
        column.addLayout(bar)
        column.addWidget(scroll, 1)
        left.setMinimumWidth(400)
        splitter = QSplitter()
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left)
        splitter.addWidget(self.history)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 900])
        self.setCentralWidget(splitter)

        self.worker = Worker(backend)
        self.worker.stage.connect(self._on_stage)
        self.worker.step.connect(self._on_step)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.preview.connect(lambda j, img, exact: self._pending(j) and self._pending(j).set_preview(img, exact))
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.described.connect(self._on_described)
        self.worker.missing.connect(self._on_missing)
        self.describing = {}                 # job id → DescribeDialog
        self._download_dialog = None

        self.controls.generateRequested.connect(self.generate)
        self.controls.deleteHistoryRequested.connect(self.delete_all_history)
        self.controls.describeRequested.connect(self.describe_image)
        self.controls.enhanceRequested.connect(self.enhance_prompt)
        self.controls.maskRequested.connect(self.edit_mask)
        self.controls.layoutRequested.connect(self.edit_layout)
        self.discarded = set()
        self.controls.outputDirEdited.connect(self.change_output_dir)
        self._hide_status = QTimer(self, singleShot=True, timeout=lambda: self.notify(None))
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().hide()
        self._build_menu()
        self._restore()
        QTimer.singleShot(300, self._check_first_run)

    # setup / persistence

    def _build_menu(self):
        def action(menu, text, slot, shortcut=None, role=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if role is not None:
                a.setMenuRole(role)
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        bar = self.menuBar()
        file_menu = bar.addMenu("File")
        action(file_menu, "About Blokjutsu", self.about, role=QAction.AboutRole)
        action(file_menu, "Settings…", self.open_settings, "Ctrl+,", QAction.ApplicationSpecificRole)
        action(file_menu, "Generate", self.generate, "Ctrl+Return")
        action(file_menu, "Import Parameters…", self.import_parameters, QKeySequence.Open)
        file_menu.addSeparator()
        action(file_menu, "Show Output Folder in Finder", lambda: self._reveal(self.output_dir))
        action(file_menu, "Show App Data in Finder", lambda: self._reveal(app_home()))
        file_menu.addSeparator()
        action(file_menu, "Download Model…", lambda: self.open_download("model"))
        action(file_menu, "Download Captioning Head…", lambda: self.open_download("caption"))
        file_menu.addSeparator()
        action(file_menu, "Delete All History…", self.delete_all_history)

        edit_menu = bar.addMenu("Edit")
        for item in EDIT_ACTIONS:
            if item is None:
                edit_menu.addSeparator()
                continue
            text, method, key = item
            action(edit_menu, text, lambda _=False, m=method: self._edit(m), key)

        view_menu = bar.addMenu("View")
        appearance = view_menu.addMenu("Appearance")
        group = QActionGroup(self)
        current = self.settings.get("appearance", "System")
        for name in theme.APPEARANCES:
            a = QAction(name, self, checkable=True, checked=name == current)
            a.triggered.connect(lambda _=False, n=name: self.set_appearance(n))
            group.addAction(a)
            appearance.addAction(a)
        appearance.setEnabled(theme.set_appearance(current))

        window_menu = bar.addMenu("Window")
        action(window_menu, "Minimize", self.showMinimized, "Ctrl+M")
        action(window_menu, "Zoom", lambda: self.showNormal() if self.isMaximized() else self.showMaximized())

        help_menu = bar.addMenu("Help")
        action(help_menu, "Blokjutsu User's Guide", lambda: QDesktopServices.openUrl(QUrl(HOME_PAGE)))
        action(help_menu, "MOSS-Image User Guide", lambda: QDesktopServices.openUrl(QUrl(USER_GUIDE)))
        action(help_menu, "MOSS-Image Technical Report (arXiv)", lambda: QDesktopServices.openUrl(QUrl(PAPER)))
        action(help_menu, "MOSS-Image on GitHub", lambda: QDesktopServices.openUrl(QUrl(REPO)))
        help_menu.addSeparator()
        action(help_menu, "Show Log", self.show_log)

    @staticmethod
    def _edit(method):
        widget = QApplication.focusWidget()
        if isinstance(widget, QLabel):            # selectable card text: Copy only
            if method == "copy" and widget.hasSelectedText():
                QGuiApplication.clipboard().setText(widget.selectedText())
            return
        if widget is not None and hasattr(widget, method):
            getattr(widget, method)()

    def show_log(self):
        from ..logs import log_file
        path = log_file()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self._reveal(path.parent)

    def _set_low_memory(self, on):
        self.backend.low_memory = on
        self.settings.set("low_memory", on)
        self.settings.save()

    def _set_embed_metadata(self, on):
        """Turning it on needs confirmation: the settings become a permanent part of each new picture file."""
        if on and not confirm_action(
                self, "Settings in PNG", "Write the prompt and settings into each new picture?",
                "Every picture saved from now on will permanently contain its prompt, negative prompt, seed and "
                "all other settings inside the PNG file. Anyone you give the file to can read them, and they stay "
                "in copies of it.\n\nPictures already saved are not changed.", "Turn on"):
            self.controls.embed_metadata.blockSignals(True)
            self.controls.embed_metadata.setChecked(False)
            self.controls.embed_metadata.blockSignals(False)
            return
        self.settings.set("embed_metadata", on)
        self.settings.save()

    def about(self):
        QMessageBox.about(
            self, "About Blokjutsu",
            f"<p><b>Blokjutsu</b> {__version__}</p>"
            "<p>A local, permissively licensed, open-source Mac app for generating and editing images from "
            f"text prompts with the open-weight <a href='{REPO}'>MOSS-Image&nbsp;↗</a> model by the OpenMOSS "
            f"Team and MOSI.AI (<a href='{PAPER}'>technical report&nbsp;↗</a>). Blokjutsu is not affiliated "
            "with them; all of the image-making is theirs.</p>"
            "<p><i>Blok</i> is Danish for block and <i>jutsu</i> (術) Japanese for art: the art of the block.</p>"
            "<p>Written by Bob Carpenter together with Claude, Anthropic's AI model.</p>"
            f"<p>Copyright 2026 Bob Carpenter. Apache License 2.0. <a href='{HOME_PAGE}'>User's Guide&nbsp;↗</a></p>")

    def open_settings(self):
        dialog = SettingsDialog(self.live_preview, self.history.cache.budget >> 20, self._reveal, self)
        if dialog.exec():
            self.live_preview = dialog.live_preview.isChecked()
            self.history.cache.budget = dialog.cache_mb.value() << 20
            self.settings.set("live_preview", self.live_preview)
            self.settings.set("image_cache_mb", dialog.cache_mb.value())
            self.settings.save()

    def notify(self, message, timeout=0):
        """Transient status line, shown only while it has something to say."""
        bar = self.statusBar()
        if not message:
            bar.clearMessage()
            bar.hide()
            return
        bar.show()
        bar.showMessage(message, timeout)
        if timeout:
            self._hide_status.start(timeout)

    def set_appearance(self, name):
        theme.set_appearance(name)
        self.settings.set("appearance", name)
        self.settings.save()

    # downloads: the app's only network access, each confirmed in DownloadDialog

    def _check_first_run(self):
        if not self.backend.has("model", self.controls.params().model):
            self.open_download("model", first_run=True)
        else:
            self._check_memory()

    def _check_memory(self):
        """Once, on Macs with less memory than the model needs: say so (Low memory is already on)."""
        total = physical_memory()
        if self.backend.fake or total is None or total >= NEEDED_MEMORY or self.settings.get("memory_warned"):
            return
        self.settings.set("memory_warned", True)
        self.settings.save()
        QMessageBox.information(
            self, "Memory", f"This Mac has {total / 2**30:.0f} GB of memory.\n\nMOSS-Image needs about 30 GB: "
            "a 10 GB image model and a 17 GB text encoder. Low memory (in Advanced options) is on, so the text "
            "encoder is set aside after reading each prompt, but macOS may still swap to disk and pictures may "
            "take much longer.")

    def open_download(self, kind, first_run=False, then=None):
        """Ask, then download 'model' or the 'caption' head; `then` runs after a successful download."""
        if self._download_dialog is not None:
            self._download_dialog.raise_()
            self._download_dialog.activateWindow()
            return
        model = self.controls.params().model
        fake = self.backend.fake
        if kind == "model":
            spec = model_spec(model, first_run, fake)
        elif not self.backend.has("model", model):
            self.open_download("model", True, lambda: self.open_download("caption", then=then))
            return
        else:
            if then is None and self.backend.has("caption") and not confirm_action(
                    self, "Captioning head", "The captioning head is already downloaded.",
                    "Describe image and Enhance prompt use it without any network access. Download it again "
                    "only to repair a damaged copy.", "Download again"):
                return
            spec = caption_spec(None if fake else Path(local_snapshot(model)) / "text_encoder", fake)
        dialog = DownloadDialog(spec, self)
        done = []
        dialog.succeeded.connect(lambda k: (done.append(k), self.backend.downloaded(k)))
        dialog.finished.connect(lambda _r: self._download_closed(bool(done), then))
        self._download_dialog = dialog
        dialog.open()

    def _download_closed(self, succeeded, then):
        self._download_dialog = None
        if succeeded and then is not None:
            QTimer.singleShot(0, then)

    # describe image

    def describe_image(self, path):
        self._write(path, None)

    def enhance_prompt(self, text):
        self._write(None, text)

    def _write(self, path, request):
        """Describe the image at `path`, or expand the prompt `request` (Enhance Prompt)."""
        model = self.controls.params().model
        for what in ("model", "caption"):
            if not self.backend.has(what, model):
                self.open_download(what, first_run=what == "model", then=lambda: self._write(path, request))
                return
        dialog = DescribeDialog(path, request, self, "Describe image" if path else "Enhance prompt")
        dialog.path, dialog.request = path, request
        dialog.job_id = None
        dialog.use.connect(self._use_caption)
        dialog.again.connect(lambda d=dialog: self._describe(d))
        dialog.cancel.connect(lambda d=dialog: d.job_id and self.worker.cancel(d.job_id))
        dialog.show()
        self._describe(dialog)

    def _describe(self, dialog):
        thinking = self.controls.think_first.isChecked()
        dialog.working()
        dialog.job_id = next(self.job_ids)
        self.describing[dialog.job_id] = dialog
        self.worker.submit(DescribeJob(dialog.job_id, self.controls.params().model,
                                       Path(dialog.path) if dialog.path else None, thinking, dialog.request))

    def _use_caption(self, text):
        cursor = self.controls.prompt.textCursor()     # an edit, not setPlainText, so ⌘Z restores the old prompt
        cursor.select(QTextCursor.Document)
        cursor.insertText(text)
        self.notify("Prompt replaced (⌘Z to undo).", 6000)

    # inpainting / outpainting

    def edit_layout(self, backdrop=None):
        from .layout_editor import LayoutEditor

        editor = LayoutEditor(self.controls.layout_draft(), backdrop, self, self._confirm_delete_layout)
        editor.exec()
        if editor.action == "delete":
            self.controls.set_layout(None)
            self.notify("Layout deleted. Pictures made from it keep theirs: Edit layout on one brings it back.", 8000)
            return
        if editor.action == "remove" and not self.controls.prompt.toPlainText().strip():
            self.controls.prompt.setPlainText(editor.draft["summary"].get("caption", ""))
        self.controls.set_layout(editor.draft, use=editor.action == "use")

    def _confirm_delete_layout(self, draft, parent):
        """Delete at once if a picture in the history keeps this exact layout; otherwise it would be lost, so ask."""
        mine = L.signature(draft)
        for card in self.history.by_path.values():
            p = card.entry.params
            if p.layout and L.signature(L.scaled(L.loads(p.layout), draft["width"], draft["height"])) == mine:
                return True
        return confirm_delete(parent, "Delete layout", "Delete this layout?",
                              "No picture has been made from it as it is now, so it can't be brought back.")

    def _edit_layout_of(self, entry):
        """Reuse a layout picture's settings and open its layout over it."""
        self._reuse(entry)
        self.edit_layout(str(entry.image))

    def edit_mask(self):
        from .mask_editor import MaskEditor

        image = self.controls.input_well.path
        if not image:
            self.notify("Choose an input image first.", 4000)
            return
        editor = MaskEditor(image, self.controls.mask_path, self)
        if editor.exec() and editor.paths:
            new_image, mask = editor.paths
            self.controls.set_input_with_mask(new_image, mask)
            if any(v > 0 for v in editor.canvas.margins) and self.controls.input_strength.value() < 1.0:
                self.controls.input_strength.setValue(1.0)       # new margins start from noise
                self.notify("Change set to 1.00 so the new margins are generated from scratch.", 6000)

    def _on_described(self, job_id, captions):
        if dialog := self.describing.pop(job_id, None):
            dialog.show_result(captions)

    def bring_to_front(self):
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _restore(self):
        geometry = self.settings.get("geometry")
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
        else:
            self.resize(1400, 900)
        saved = self.settings.get("params")
        if saved:
            try:
                self.controls.set_params(P.from_json(json.dumps(saved)))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        kept = self.settings.get("kept_layout", "")
        if kept and self.controls.draft is None:
            try:
                self.controls.set_layout(L.loads(kept), use=False)
            except (ValueError, TypeError):
                pass
        self.controls.set_advanced_open(bool(self.settings.get("advanced_open", False)))
        self.controls.set_size_step(int(self.settings.get("size_step", 128)))
        self.controls.think_first.setChecked(False)     # slow: off at every launch, on only when asked for
        self.controls.low_memory.setChecked(self.backend.low_memory)
        self.controls.low_memory.toggled.connect(self._set_low_memory)
        self.controls.embed_metadata.setChecked(bool(self.settings.get("embed_metadata", False)))
        self.controls.embed_metadata.toggled.connect(self._set_embed_metadata)
        self.controls.prompt_handle.set_height(self.settings.get("prompt_height", 96))
        self.controls.negative_handle.set_height(self.settings.get("negative_height", 56))
        prune_work_files()
        default_output().mkdir(parents=True, exist_ok=True)
        self.output_dir = Path(self.settings.get("output_dir", str(default_output())))
        self.controls.output_dir.setText(tilde(self.output_dir))
        self.history.set_entries(store.scan(self.output_dir))

    def closeEvent(self, event):
        if self.worker.busy():
            answer = QMessageBox.question(self, "Quit Blokjutsu",
                                          "Images are still generating. Quit and discard them?")
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.settings.set("geometry", bytes(self.saveGeometry().toBase64()).decode())
        self.settings.set("params", json.loads(P.to_json(self.controls.params())))
        kept = self.controls.draft if self.controls.draft is not None and not self.controls.use_layout else None
        self.settings.set("kept_layout", L.dumps(kept))
        self.settings.set("advanced_open", self.controls.advanced_toggle.isChecked())
        self.settings.set("size_step", self.controls.width_box.singleStep())
        self.settings.set("prompt_height", self.controls.prompt.height())
        self.settings.set("negative_height", self.controls.negative.height())
        self.settings.set("live_preview", self.live_preview)
        self.settings.set("image_cache_mb", self.history.cache.budget >> 20)
        self.settings.set("output_dir", str(self.output_dir))
        self.settings.save()
        event.accept()

    # output folder

    def confirm_dir(self, text):
        """Absolute directory if it exists or the user agrees to create it; else None."""
        path = Path(text).expanduser()
        path = path if path.is_absolute() else Path.home() / path
        path = path.resolve()
        if path.is_dir():
            return path
        if path.exists():
            QMessageBox.warning(self, "Output folder", f"This path exists but is not a folder:\n\n{path}")
            return None
        box = QMessageBox(QMessageBox.Question, "Create output folder?",
                          f"This folder does not exist:\n\n{path}\n\nCreate it?", parent=self)
        create = box.addButton("Create", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not create:
            return None
        try:
            path.mkdir(parents=True)
        except OSError as exc:
            QMessageBox.warning(self, "Output folder", f"Could not create\n\n{path}\n\n{exc}")
            return None
        return path

    def change_output_dir(self, text):
        path = self.confirm_dir(text)
        if path is None:
            self.controls.output_dir.setText(tilde(self.output_dir))
            return
        self.controls.output_dir.setText(tilde(path))
        if path != self.output_dir:
            self.output_dir = path
            self.settings.set("output_dir", str(path))
            self.settings.save()
            self.history.set_entries(store.scan(path))

    # generation

    def generate(self):
        p = self.controls.params()
        try:
            P.validate(p)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot generate", str(exc))
            return
        error, warnings = P.layout_warnings(p)
        problems = ([f"The prompt starts with '{{' but is not valid JSON ({error})."] if error else []) + warnings
        if problems and QMessageBox.question(
                self, "Check prompt", "\n\n".join(problems) + "\n\nGenerate anyway?") != QMessageBox.Yes:
            return
        out = self.confirm_dir(self.controls.output_dir.text())
        if out is None:
            return
        self.change_output_dir(str(out))
        for job_params in P.realize(p):
            job_id = next(self.job_ids)
            card = self.history.add_pending(job_id, job_params)
            card.cancel.connect(self._cancel)
            card.dismiss.connect(self.history.drop_pending)
            self.worker.submit(Job(job_id, job_params, out, self.live_preview,
                                   bool(self.settings.get("embed_metadata", False))))

    def _pending(self, job_id):
        return self.history.pending.get(job_id)

    def _cancel(self, job_id):
        """Remove the card now; the worker stops between steps, and any image it still saves is deleted."""
        self.discarded.add(job_id)
        self.worker.cancel(job_id)
        self.history.drop_pending(job_id)

    def _on_step(self, job_id, done, total):
        if dialog := self.describing.get(job_id):
            dialog.set_tokens(done, total)
        elif card := self._pending(job_id):
            card.set_step(done, total)

    def _on_stage(self, job_id, stage, total):
        if dialog := self.describing.get(job_id):
            dialog.set_stage(stage, total)
        if card := self._pending(job_id):
            card.set_stage(stage, total)
        if stage == "load":
            self.notify("Loading model from the local cache…")
        elif stage == "encode":
            self.notify(None)

    def _on_finished(self, job_id, entry):
        if job_id in self.discarded:
            self.discarded.discard(job_id)
            store.delete(entry.folder)
            return
        self._remember_output(entry.folder.parent)
        if job_id not in self.history.pending:
            return
        if entry.folder.parent == self.output_dir:
            self.history.complete(job_id, entry)
        else:
            self.history.drop_pending(job_id)
        self.notify(f"Saved {entry.image}", 8000)

    def _on_missing(self, job_id, what):
        """A job needed a download that has not happened; ask for it, then retry describing."""
        if dialog := self.describing.pop(job_id, None):
            dialog.done(0)
            self.open_download(what, then=lambda d=dialog: self._write(d.path, d.request))
            return
        if card := self._pending(job_id):
            card.set_error("The model is not downloaded yet.")
        self.open_download(what, first_run=True)

    def _on_cancelled(self, job_id):
        self.describing.pop(job_id, None)
        self.discarded.discard(job_id)
        self.history.drop_pending(job_id)

    def _on_failed(self, job_id, message):
        if dialog := self.describing.pop(job_id, None):
            dialog.show_error(message)
            return
        if job_id in self.discarded:
            self.discarded.discard(job_id)
            return
        if card := self._pending(job_id):
            card.set_error(message)

    # history card actions

    def _hook_card(self, card):
        clipboard = QGuiApplication.clipboard()
        card.reuse.connect(self._reuse)
        card.vary.connect(self._vary)
        card.use_input.connect(lambda e: self.controls.set_input_image(str(e.image)))
        card.describe.connect(lambda e: self.describe_image(str(e.image)))
        card.copySeed.connect(lambda e: clipboard.setText(str(e.params.seed)))
        card.copyPrompt.connect(lambda e: clipboard.setText(e.params.prompt))
        card.reveal.connect(lambda e: self._reveal(e.image))
        card.open_.connect(lambda e: open_in_preview(e.image))
        card.edit_layout.connect(self._edit_layout_of)
        card.trash.connect(self._trash)

    def _vary(self, entry):
        """Load this image's settings with Variations on, then generate Images-many variations of it."""
        strength = self.controls.variation.value() or P.DEFAULT_VARIATION
        self.controls.set_params(P.vary_from(entry.params, strength, self.controls.count.value()))
        self.generate()

    def _reuse(self, entry):
        self.controls.set_params(entry.params)
        self.notify(f"Loaded settings from {entry.folder.name} (seed {entry.params.seed})", 6000)

    def _reveal(self, path):
        path = Path(path)
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)], check=False)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path if path.is_dir() else path.parent)))

    def _trash(self, entry):
        if not confirm_delete(self, "Delete image", "Delete this image?",
                              f"{entry.folder}\n\nThe image and its parameters will be permanently deleted. "
                              "This cannot be undone."):
            return
        if not store.delete(entry.folder):
            QMessageBox.warning(self, "Delete image", f"Could not delete\n\n{entry.folder}")
            return
        self.history.remove_folder(entry.folder)

    def _remember_output(self, folder):
        """Every output folder pictures were saved to, so Delete all history finds them all."""
        roots = self.settings.get("output_roots", [])
        if str(folder) not in roots:
            self.settings.set("output_roots", roots + [str(folder)])
            self.settings.save()

    def _output_roots(self):
        roots = [str(self.output_dir)] + list(self.settings.get("output_roots", []))
        return [Path(r) for r in dict.fromkeys(roots) if Path(r).is_dir()]

    def delete_all_history(self):
        """Delete everything the app has made from your prompts and pictures, in every output folder used,
        plus the log, scratch files, the live preview's file and cached prompts. Settings and models are kept."""
        roots = self._output_roots()
        by_root = {root: sorted({e.folder for e in store.scan(root)}) for root in roots}
        folders = [f for fs in by_root.values() for f in fs]
        running = list(self.history.pending)
        lines = [f"{len(fs)} picture folder(s) in {root}" for root, fs in by_root.items() if fs] \
            or ["No picture folders."]
        lines = ["\n".join(lines) + "\nwill be permanently deleted. This cannot be undone."]
        if running:
            lines.append(f"{len(running)} queued or running generation(s) will be cancelled.")
        lines.append("Also cleared: the app's log, working copies from Select area to change, the file the live "
                     "preview builds from your pictures, and the prompt and settings in the controls. Your "
                     "Settings and the downloaded models are kept.")
        if not confirm_delete(self, "Delete all history", "Delete all history?", "\n\n".join(lines),
                              "Delete all"):
            return
        for job_id in running:
            self.discarded.add(job_id)
            self.worker.cancel(job_id)
            self.history.drop_pending(job_id)
        failed = [f for f in folders if not store.delete(f)]
        self.history.set_entries(store.scan(self.output_dir))
        self.history.cache.clear()
        self.controls.set_params(P.Params())
        self.controls.input_well.set_path("")
        self.settings.set("params", json.loads(P.to_json(self.controls.params())))
        self.settings.set("output_roots", [str(self.output_dir)])
        self.settings.save()
        self.backend.forget()
        clear_work_files()
        clear_logs()
        if failed:
            QMessageBox.warning(self, "Delete all history",
                                f"{len(failed)} folder(s) could not be deleted, e.g.\n\n{failed[0]}")
        else:
            self.notify(f"Deleted {len(folders)} picture folder(s) and cleared the log.", 6000)

    def import_parameters(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import parameters", str(self.output_dir),
                                              "Parameters (*.json *.png)")
        if not path:
            return
        try:
            record = json.loads(store.png_parameters(path) if path.lower().endswith(".png")
                                else Path(path).read_text(encoding="utf-8"))
            p = store.resolve_files(P.from_record(record), Path(path).parent)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Import parameters", f"Could not read {path}:\n\n{exc}")
            return
        self.controls.set_params(p)
        self.notify(f"Imported {path}", 6000)
