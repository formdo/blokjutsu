"""Scrolling history: pending-job cards (with live preview) and finished-image cards, newest first.

Every finished image is decoded off the GUI thread into a display-sized cache, nearest-to-viewport first,
so scrolling never waits on disk or PNG decoding.
"""
from __future__ import annotations

import html
import time

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from .. import img2img as I
from .. import params as P
from .image_cache import ImageCache
from .icons import BLUE, RED, icon
from .theme import MARGIN, RESOURCES, enlarge, window_background

MAX_HEIGHT_FRACTION = 0.85
STAGES = {"encode_image": "Encoding input image…", "load": "Loading model…", "download": "Downloading model weights (first use only; tens of GB)…", "encode": "Encoding prompt…",
          "decode": "Decoding image…", "save": "Saving…"}


def summary(p, elapsed=None):
    bits = [f"{p.width}×{p.height}", f"seed {p.seed}"]
    if p.variation > 0:
        bits.append(f"variation {p.variation:.2f} (seed {p.variation_seed})" if p.variation_seed
                    else f"variation {p.variation:.2f}")
    if p.init_image:
        bits.append(f"{'inpainted' if p.mask_image else 'from image'}, change {I.sigma_to_change(p.init_strength):.2f}")
    bits += [f"{p.steps} steps", f"adherence {p.cfg:g}", p.sampler, P.model_name(p.model)]
    if elapsed:
        bits.append(f"{clock(elapsed)} m:s" if elapsed >= 60 else f"{elapsed:.0f} s")
    return " · ".join(bits)


def _html(text):
    return html.escape(text.strip()).replace("\n", "<br>")


def prompt_text(p):
    """Full prompt as rich text; the negative prompt, if any, on the next line after an italic label."""
    text = _html(p.prompt)
    if p.negative_prompt.strip():
        text += f"<br><i>Negative:</i> {_html(p.negative_prompt)}"
    return text


class ImageView(QWidget):
    """Letterboxes a pixmap (from the cache, or a live preview) into its rect; placeholder until available."""

    def __init__(self, natural, cache=None, path=None, parent=None):
        super().__init__(parent)
        self.natural = natural
        self.cache, self.path = cache, path
        self.preview = None
        self.text = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def fit_height(self, width, max_height):
        nw, nh = max(1, self.natural.width()), max(1, self.natural.height())
        height = int(min(width * nh / nw, max_height))
        if height != self.height():
            self.setFixedHeight(height)

    def target_rect(self):
        size = self.natural.scaled(self.size(), Qt.KeepAspectRatio)
        return QRect(0, (self.height() - size.height()) // 2, size.width(), size.height())

    def device_width(self):
        return self.target_rect().width() * self.devicePixelRatioF()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.target_rect()
        pixmap = self.cache.get(self.path) if self.path else None
        if pixmap is None:
            pixmap = self.preview
        if pixmap is not None:
            painter.drawPixmap(rect, pixmap)
        else:
            painter.fillRect(rect, QColor(128, 128, 128, 40))
        if self.text:
            self._badge(painter, rect, pixmap is not None)

    def _badge(self, painter, rect, over_image):
        if not over_image:
            painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)
            return
        metrics = painter.fontMetrics()
        box = metrics.boundingRect(self.text).adjusted(-8, -4, 8, 4)
        box.moveTopLeft(rect.topLeft() + QRect(0, 0, 8, 8).bottomRight())
        painter.fillRect(box, QColor(0, 0, 0, 150))
        painter.setPen(Qt.white)
        painter.drawText(box, Qt.AlignCenter, self.text)


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 4, 0, 22)
        self.layout_.setSpacing(6)

    def caption(self, text, muted=False, rich=False):
        label = QLabel(text)
        label.setTextFormat(Qt.RichText if rich else Qt.PlainText)
        label.setWordWrap(True)
        selectable(label)
        if muted:
            label.setForegroundRole(QPalette.PlaceholderText)
        self.layout_.addWidget(label)
        return label


def selectable(label):
    """Select with the mouse or keyboard; ⌘C (Edit → Copy) and the context menu copy the selection."""
    label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
    label.setFocusPolicy(Qt.ClickFocus)
    label.setCursor(Qt.IBeamCursor)
    return label


def button_row(*buttons):
    row = QHBoxLayout()
    row.setSpacing(6)
    row.setContentsMargins(0, 6, 0, 0)
    for b in buttons:
        row.addWidget(b)
    row.addStretch(1)
    return row


class ButtonGrid(QWidget):
    """Equal-width buttons in 4 columns (two rows of four), falling back to 2 or 1 column when narrow."""

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.buttons = buttons
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 6, 0, 0)
        self.grid.setSpacing(6)
        self.grid.setSizeConstraint(QLayout.SetNoConstraint)    # our minimumSizeHint, not 4 columns' worth
        for b in buttons:
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.columns = 0
        self._arrange(4)

    def _widest(self):
        return max(b.minimumSizeHint().width() for b in self.buttons)

    def _arrange(self, columns):
        if columns == self.columns:
            return
        self.columns = columns
        for b in self.buttons:
            self.grid.removeWidget(b)
        for i, b in enumerate(self.buttons):
            self.grid.addWidget(b, i // columns, i % columns)
        for c in range(4):
            self.grid.setColumnStretch(c, 1 if c < columns else 0)
        self.updateGeometry()

    def minimumSizeHint(self):
        return QSize(self._widest(), super().minimumSizeHint().height())

    def resizeEvent(self, event):
        spacing = self.grid.horizontalSpacing()
        fits = [n for n in (4, 2) if n * self._widest() + (n - 1) * spacing <= event.size().width()]
        self._arrange(fits[0] if fits else 1)
        super().resizeEvent(event)


CARD_TIPS = {
    "Generate similar image": "Make new pictures that are close variations of this one",
    "Use as input": "Start a new picture from this one (Start from image)",
    "Describe image": "Write a description of this picture that you can use as a prompt",
    "Reuse settings": "Put this picture's prompt and settings back in the controls",
    "Copy seed": "Copy the seed number",
    "Copy prompt": "Copy the prompt text",
    "Open in Preview": "Open the picture in the Mac's Preview app",
    "Show in Finder": "Show the picture's folder in Finder",
    "Delete": "Delete this picture and its settings permanently",
}


class EntryCard(Card):
    reuse = Signal(object)
    vary = Signal(object)
    use_input = Signal(object)
    describe = Signal(object)
    copySeed = Signal(object)
    copyPrompt = Signal(object)
    reveal = Signal(object)
    open_ = Signal(object)
    trash = Signal(object)

    def __init__(self, entry, cache, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.path = str(entry.image)
        size = QImageReader(self.path).size()
        self.image = ImageView(size if size.isValid() else QSize(entry.params.width, entry.params.height),
                               cache, self.path)
        self.layout_.addWidget(self.image)
        self.caption(summary(entry.params, entry.elapsed))
        self.caption(prompt_text(entry.params), muted=True, rich=True)
        actions = [("Generate similar image", self.vary, None), ("Use as input", self.use_input, None),
                   ("Describe image", self.describe, None),
                   ("Reuse settings", self.reuse, None), ("Copy seed", self.copySeed, "copy"),
                   ("Copy prompt", self.copyPrompt, "copy"), ("Open in Preview", self.open_, None),
                   ("Show in Finder", self.reveal, "folder"),
                   ("Delete", self.trash, "trash")]
        buttons = []
        for text, signal, name in actions:
            color = RED if signal is self.trash else BLUE
            b = QPushButton(icon(name, color), text) if name else QPushButton(text)
            b.setProperty("card", True)
            if signal is self.trash:
                b.setObjectName("destructive")
            b.clicked.connect(lambda _=False, s=signal: s.emit(self.entry))
            b.setToolTip(CARD_TIPS.get(text, ""))
            buttons.append(b)
        self.layout_.addWidget(ButtonGrid(buttons))


def clock(seconds):
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


class PendingCard(Card):
    """In-progress job: live preview, progress, and elapsed / estimated remaining time (m:ss), ticking each second."""
    cancel = Signal(int)
    dismiss = Signal(int)
    last_decode = 0.0      # seconds the previous VAE decode + save took; used in the total estimate

    def __init__(self, job_id, params, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.image = ImageView(QSize(params.width, params.height))
        self.image.text = "Queued"
        self.layout_.addWidget(self.image)
        self.caption(summary(params))
        self.caption(prompt_text(params), muted=True, rich=True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.button = QPushButton("Cancel")
        self.button.setProperty("card", True)
        self.button.clicked.connect(lambda: self.cancel.emit(job_id))
        self.layout_.addWidget(self.progress)
        self.layout_.addLayout(button_row(self.button))
        self.status = "Queued"
        self.started = self.denoise_started = self.decode_started = None
        self.done = self.total = 0
        self.ticker = QTimer(self, interval=1000, timeout=self._render)

    def set_text(self, text):
        self.status = text
        self._render()

    def _render(self):
        text = self.status
        if self.started is not None:
            now = time.monotonic()
            text += f" · {clock(now - self.started)} elapsed"
            if self.done and self.denoise_started is not None and self.decode_started is None:
                per_step = (now - self.denoise_started) / self.done
                remaining = per_step * (self.total - self.done) + PendingCard.last_decode
                text += f" · ~{clock(remaining)} remaining"
        self.image.text = text
        self.image.update()

    def set_preview(self, qimage, exact=False):
        # the linear decoder is blocky at 16-px patches; a ¼-scale copy drawn with smoothing reads as soft focus
        if not exact:
            qimage = qimage.scaled(max(1, qimage.width() // 4), max(1, qimage.height() // 4),
                                   Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.image.preview = QPixmap.fromImage(qimage)
        self.image.update()

    def set_stage(self, stage, total):
        now = time.monotonic()
        if self.started is None:
            self.started = now
            self.ticker.start()
        if stage == "decode":
            self.decode_started = now
        elif stage == "save" and self.decode_started is not None:
            PendingCard.last_decode = now - self.decode_started
        self.progress.show()
        if stage == "denoise":
            self.denoise_started, self.total, self.done = now, total, 0
            self.progress.setRange(0, total)
            self.progress.setValue(0)
            self.set_text(f"Step 0/{total}")
        else:
            self.progress.setRange(0, 0)
            self.set_text(STAGES.get(stage, stage))

    def set_step(self, done, total):
        self.done = done
        self.progress.setValue(done)
        self.set_text(f"Step {done}/{total}")

    def stop_clock(self):
        self.ticker.stop()

    def set_cancelling(self):
        self.button.setEnabled(False)
        self.set_text("Cancelling…")

    def set_error(self, message):
        self.ticker.stop()
        self.started = None
        self.progress.hide()
        self.set_text("Failed")
        self.caption(message).setStyleSheet("color: #c0392b;")
        self.button.setText("Dismiss")
        self.button.setEnabled(True)
        self.button.clicked.disconnect()
        self.button.clicked.connect(lambda: self.dismiss.emit(self.job_id))


def empty_state():
    widget = QWidget()
    art = QLabel()
    art.setPixmap(QIcon(str(RESOURCES / "empty.svg")).pixmap(QSize(360, 270)))
    art.setAlignment(Qt.AlignCenter)
    text = QLabel("Your pictures will appear here.\nWrite a prompt and press Generate.")
    text.setAlignment(Qt.AlignCenter)
    text.setForegroundRole(QPalette.PlaceholderText)
    enlarge(text)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 100, 0, 40)
    layout.setSpacing(16)
    layout.addWidget(art)
    layout.addWidget(text)
    return widget


class HistoryView(QScrollArea):
    def __init__(self, cache_mb=4096, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cache = ImageCache(cache_mb, parent=self)
        self.cache.ready.connect(self._on_ready)
        self.container = QWidget()
        self.stack = QVBoxLayout(self.container)
        self.stack.setSpacing(18)
        self.stack.setContentsMargins(MARGIN, MARGIN - 4, MARGIN, MARGIN)
        self.empty = empty_state()
        self.stack.addWidget(self.empty)
        self.stack.addStretch(1)
        self.setWidget(self.container)
        window_background(self)
        self.pending = {}
        self.by_path = {}
        self.card_hooks = None
        self._refresh = QTimer(self, singleShot=True, interval=40, timeout=self._update)
        self.verticalScrollBar().valueChanged.connect(self._schedule)

    def _schedule(self):
        if not self._refresh.isActive():
            self._refresh.start()

    def cards(self):
        items = (self.stack.itemAt(i).widget() for i in range(self.stack.count()))
        return [w for w in items if isinstance(w, Card)]

    def _insert(self, index, card):
        self.stack.insertWidget(index, card)
        self.empty.hide()
        self._schedule()

    def _remove(self, card):
        self.stack.removeWidget(card)
        if isinstance(card, EntryCard):
            self.by_path.pop(card.path, None)
            self.cache.evict(card.path)
        card.deleteLater()
        self.empty.setVisible(not self.cards())
        self._schedule()

    def _entry_card(self, entry):
        card = EntryCard(entry, self.cache)
        self.by_path[card.path] = card
        if self.card_hooks:
            self.card_hooks(card)
        return card

    def set_entries(self, entries):
        for card in self.cards():
            if isinstance(card, EntryCard):
                self._remove(card)
        offset = len(self.pending)
        for i, entry in enumerate(entries):
            self.stack.insertWidget(offset + i, self._entry_card(entry))
        self.empty.setVisible(not self.cards())
        self._schedule()

    def add_pending(self, job_id, params):
        card = PendingCard(job_id, params)
        self.pending[job_id] = card
        self._insert(0, card)
        self.verticalScrollBar().setValue(0)
        return card

    def complete(self, job_id, entry):
        card = self.pending.pop(job_id)
        index = self.stack.indexOf(card)
        preview = card.image.preview
        new = self._entry_card(entry)
        if preview is not None:
            new.image.preview = preview
        self._remove(card)
        self._insert(index, new)

    def drop_pending(self, job_id):
        if job_id in self.pending:
            self._remove(self.pending.pop(job_id))

    def remove_folder(self, folder):
        for card in self.cards():
            if isinstance(card, EntryCard) and card.entry.folder == folder:
                self._remove(card)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule()

    def _on_ready(self, path):
        card = self.by_path.get(path)
        if card is not None:
            card.image.update()

    def _update(self):
        viewport = self.viewport()
        margins = self.stack.contentsMargins()
        width = viewport.width() - margins.left() - margins.right() - 20
        cards = self.cards()
        for card in cards:
            card.image.fit_height(width, viewport.height() * MAX_HEIGHT_FRACTION)
        top, h = self.verticalScrollBar().value(), max(1, viewport.height())
        for card in cards:
            if not isinstance(card, EntryCard):
                continue
            g = card.geometry()
            screens = 0 if g.bottom() >= top and g.top() <= top + h else \
                (top - g.bottom()) / h if g.bottom() < top else (g.top() - top - h) / h
            self.cache.request(card.path, max(card.image.device_width(), width), priority=-int(screens))
