"""Layout editor: boxes on a canvas the size of the picture, each with a kind, a description and, for text, its
words; plus a description of the whole picture. Drag on empty canvas to draw a box; drag a box to move it, its
handles to resize it. Edges and centres snap to the canvas and to other boxes. Everything is kept on close.
"""
from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .. import layout as L

KINDS = {"object": "Object", "character": "Person or character", "text": "Text"}
COLORS = {"object": QColor(47, 111, 216), "character": QColor(138, 79, 216), "text": QColor(216, 104, 47)}
GUIDE = QColor(230, 0, 140)
PAD = 16              # view px around the canvas
HANDLE = 7            # view px, side of a resize handle
SNAP = 6              # view px within which an edge or centre snaps
MIN_SIDE = 8          # canvas px, smallest box
TEXT_FLAGS = int((Qt.AlignLeft | Qt.AlignTop).value) | int(Qt.TextWordWrap.value)
HANDLES = ("tl", "t", "tr", "r", "br", "b", "bl", "l")
CURSORS = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor,
           "bl": Qt.SizeBDiagCursor, "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
           "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor}


def label_of(item):
    words = (item.get("text") or "").strip()
    return words.replace("\n", " / ") if item["label"] == "text" and words else item.get("caption", "").strip()


def list_text(item):
    text = label_of(item) or "(no description yet)"
    return f"{KINDS[item['label']]}: {text[:60]}{'…' if len(text) > 60 else ''}"


class Canvas(QWidget):
    """The boxes, drawn over an optional backdrop (a picture made from this layout)."""
    selected = Signal(int)          # index, or -1
    changed = Signal()

    def __init__(self, draft, backdrop=None, parent=None):
        super().__init__(parent)
        self.draft, self.current = draft, -1
        self.backdrop = QImage(backdrop) if backdrop else None
        self.show_backdrop = self.backdrop is not None and not self.backdrop.isNull()
        self.drag = None            # (mode, start canvas point, original box)
        self.guides = []            # ("x" | "y", canvas coordinate)
        self.rubber = None          # the box being drawn, in canvas coordinates
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(480, 360)

    @property
    def items(self):
        return self.draft["items"]

    # geometry

    def scale(self):
        w, h = self.draft["width"], self.draft["height"]
        return min((self.width() - 2 * PAD) / w, (self.height() - 2 * PAD) / h)

    def origin(self):
        s = self.scale()
        return QPointF((self.width() - s * self.draft["width"]) / 2, (self.height() - s * self.draft["height"]) / 2)

    def to_view(self, box):
        s, o = self.scale(), self.origin()
        x1, y1, x2, y2 = box
        return QRectF(o.x() + s * x1, o.y() + s * y1, s * (x2 - x1), s * (y2 - y1))

    def to_canvas(self, pos):
        s, o = self.scale(), self.origin()
        return (pos.x() - o.x()) / s, (pos.y() - o.y()) / s

    def handle_rects(self, box):
        r = self.to_view(box)
        xs = {"l": r.left(), "m": r.center().x(), "r": r.right()}
        ys = {"t": r.top(), "m": r.center().y(), "b": r.bottom()}
        where = {"tl": ("l", "t"), "t": ("m", "t"), "tr": ("r", "t"), "r": ("r", "m"),
                 "br": ("r", "b"), "b": ("m", "b"), "bl": ("l", "b"), "l": ("l", "m")}
        half = HANDLE / 2
        return {k: QRectF(xs[a] - half, ys[b] - half, HANDLE, HANDLE) for k, (a, b) in where.items()}

    def handle_at(self, pos):
        if self.current < 0:
            return None
        for name, rect in self.handle_rects(self.items[self.current]["bbox"]).items():
            if rect.adjusted(-3, -3, 3, 3).contains(pos):
                return name
        return None

    def box_at(self, pos):
        """The smallest box under the point, so a word on a label can be picked from inside its object."""
        hits = [i for i, it in enumerate(self.items) if self.to_view(it["bbox"]).contains(pos)]
        return min(hits, key=lambda i: self._area(self.items[i]["bbox"]), default=-1)

    @staticmethod
    def _area(box):
        return (box[2] - box[0]) * (box[3] - box[1])

    # snapping

    def _lines(self, skip):
        w, h = self.draft["width"], self.draft["height"]
        xs, ys = [0, w / 2, w], [0, h / 2, h]
        for i, it in enumerate(self.items):
            if i != skip:
                x1, y1, x2, y2 = it["bbox"]
                xs += [x1, (x1 + x2) / 2, x2]
                ys += [y1, (y1 + y2) / 2, y2]
        return xs, ys

    def _snap(self, values, lines, axis):
        """The smallest shift (within SNAP view px) that puts one of values on a line, or 0."""
        reach = SNAP / self.scale()
        best = None
        for v in values:
            for line in lines:
                if abs(line - v) <= reach and (best is None or abs(line - v) < abs(best[0])):
                    best = (line - v, line)
        if best is None:
            return 0
        self.guides.append((axis, best[1]))
        return best[0]

    # editing

    def select(self, index):
        self.current = index
        self.selected.emit(index)
        self.update()

    def set_box(self, index, box):
        w, h = self.draft["width"], self.draft["height"]
        x1, y1, x2, y2 = (round(v) for v in box)
        x1, y1 = max(0, min(x1, w - MIN_SIDE)), max(0, min(y1, h - MIN_SIDE))
        x2, y2 = min(w, max(x2, x1 + MIN_SIDE)), min(h, max(y2, y1 + MIN_SIDE))
        self.items[index]["bbox"] = [x1, y1, x2, y2]
        self.changed.emit()
        self.update()

    def add(self, box, label="object"):
        self.items.append({"label": label, "caption": "", "bbox": [0, 0, MIN_SIDE, MIN_SIDE]})
        self.set_box(len(self.items) - 1, box)
        self.select(len(self.items) - 1)

    def remove(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
            self.changed.emit()
            self.select(min(index, len(self.items) - 1))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.setFocus()
        pos, point = event.position(), self.to_canvas(event.position())
        handle = self.handle_at(pos)
        if handle:
            self.drag = (handle, point, list(self.items[self.current]["bbox"]))
            return
        index = self.box_at(pos)
        if index >= 0:
            self.select(index)
            self.drag = ("move", point, list(self.items[index]["bbox"]))
        else:
            self.select(-1)
            self.drag = ("new", point, None)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if not self.drag:
            handle = self.handle_at(pos)
            self.setCursor(CURSORS[handle] if handle else
                           Qt.OpenHandCursor if self.box_at(pos) >= 0 else Qt.CrossCursor)
            return
        mode, (sx, sy), box = self.drag
        x, y = self.to_canvas(pos)
        self.guides = []
        if mode == "new":
            xs, ys = self._lines(-1)
            x += self._snap([x], xs, "x")
            y += self._snap([y], ys, "y")
            self.rubber = (min(sx, x), min(sy, y), max(sx, x), max(sy, y))
            self.update()
            return
        xs, ys = self._lines(self.current)
        x1, y1, x2, y2 = box
        dx, dy = x - sx, y - sy
        if mode == "move":
            dx += self._snap([x1 + dx, (x1 + x2) / 2 + dx, x2 + dx], xs, "x")
            dy += self._snap([y1 + dy, (y1 + y2) / 2 + dy, y2 + dy], ys, "y")
            w, h = x2 - x1, y2 - y1
            nx1 = min(max(x1 + dx, 0), self.draft["width"] - w)
            ny1 = min(max(y1 + dy, 0), self.draft["height"] - h)
            self.set_box(self.current, (nx1, ny1, nx1 + w, ny1 + h))
            return
        if "l" in mode:
            x1 += dx
            x1 += self._snap([x1], xs, "x")
        if "r" in mode:
            x2 += dx
            x2 += self._snap([x2], xs, "x")
        if "t" in mode:
            y1 += dy
            y1 += self._snap([y1], ys, "y")
        if "b" in mode:
            y2 += dy
            y2 += self._snap([y2], ys, "y")
        self.set_box(self.current, (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def mouseReleaseEvent(self, event):
        mode = self.drag[0] if self.drag else None
        self.drag, self.guides = None, []
        rubber, self.rubber = self.rubber, None
        if mode == "new" and rubber and min(rubber[2] - rubber[0], rubber[3] - rubber[1]) >= MIN_SIDE:
            self.add(rubber)
        self.update()

    def keyPressEvent(self, event):
        if self.current < 0:
            return super().keyPressEvent(event)
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove(self.current)
            return
        step = 1 if event.modifiers() & Qt.ShiftModifier else 16
        moves = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0), Qt.Key_Up: (0, -step), Qt.Key_Down: (0, step)}
        if event.key() in moves:
            dx, dy = moves[event.key()]
            x1, y1, x2, y2 = self.items[self.current]["bbox"]
            w, h = x2 - x1, y2 - y1
            nx1 = min(max(x1 + dx, 0), self.draft["width"] - w)
            ny1 = min(max(y1 + dy, 0), self.draft["height"] - h)
            self.set_box(self.current, (nx1, ny1, nx1 + w, ny1 + h))
            return
        super().keyPressEvent(event)

    # drawing

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        page = self.to_view((0, 0, self.draft["width"], self.draft["height"]))
        p.fillRect(page, self.palette().color(QPalette.Base))
        if self.show_backdrop and self.backdrop is not None:
            p.setOpacity(0.55)
            p.drawImage(page, self.backdrop)
            p.setOpacity(1.0)
        p.setPen(QPen(self.palette().color(QPalette.Mid), 1))
        p.drawRect(page)
        font = p.font()
        font.setPointSizeF(max(9.0, font.pointSizeF() * 0.85))
        p.setFont(font)
        for i, it in enumerate(self.items):
            color = COLORS[it["label"]]
            rect = self.to_view(it["bbox"])
            fill = QColor(color)
            fill.setAlpha(22 if self.show_backdrop else 30)
            p.fillRect(rect, fill)
            p.setPen(QPen(color, 2.5 if i == self.current else 1.5))
            p.drawRect(rect)
            p.save()
            p.setClipRect(rect)
            p.drawText(rect.adjusted(4, 2, -4, -2), TEXT_FLAGS, label_of(it))
            p.restore()
        if 0 <= self.current < len(self.items):
            p.setPen(QPen(COLORS[self.items[self.current]["label"]], 1))
            p.setBrush(self.palette().color(QPalette.Base))
            for rect in self.handle_rects(self.items[self.current]["bbox"]).values():
                p.drawRect(rect)
        if self.rubber:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(COLORS["object"], 1, Qt.DashLine))
            p.drawRect(self.to_view(self.rubber))
        p.setPen(QPen(GUIDE, 1))
        for axis, v in self.guides:
            a = self.to_view((v, 0, v, self.draft["height"]) if axis == "x" else (0, v, self.draft["width"], v))
            p.drawLine(a.topLeft(), a.bottomRight())


class LayoutEditor(QDialog):
    """Edits a copy of the draft, kept however the window is closed. `action` says what to do with it: "use" it
    (Close), "remove" it (back to the typed prompt, the layout kept for later) or "delete" it. `confirm_delete`,
    if given, is asked before deleting and may say no."""

    def __init__(self, draft, backdrop=None, parent=None, confirm_delete=None):
        super().__init__(parent)
        self.setWindowTitle("Layout")
        self.draft, self.action, self.confirm_delete = copy.deepcopy(draft), "use", confirm_delete
        self.canvas = Canvas(self.draft, backdrop)
        self.canvas.selected.connect(self._show_box)
        self.canvas.changed.connect(self._refresh)

        self.caption = QPlainTextEdit(self.draft["summary"].get("caption", ""))
        self.caption.setPlaceholderText("The whole picture: subject, setting, style, colours, light")
        self.caption.setFixedHeight(96)
        self.caption.textChanged.connect(self._summary_edited)
        self.meta = QLineEdit(", ".join(self.draft["summary"].get("meta", [])))
        self.meta.setPlaceholderText("poster, photograph, watercolour…")
        self.meta.textEdited.connect(self._summary_edited)

        self.boxes = QListWidget()
        self.boxes.currentRowChanged.connect(lambda i: i != self.canvas.current and self.canvas.select(i))
        add_text, add_object = QPushButton("Add text"), QPushButton("Add object")
        add_text.clicked.connect(lambda: self._add("text"))
        add_object.clicked.connect(lambda: self._add("object"))
        self.delete = QPushButton("Delete box")
        self.delete.clicked.connect(lambda: self.canvas.remove(self.canvas.current))

        self.kind = QComboBox()
        for key, name in KINDS.items():
            self.kind.addItem(name, key)
        self.kind.activated.connect(self._box_edited)
        self.words = QPlainTextEdit()
        self.words.setPlaceholderText("The exact words; press Return for a new line")
        self.words.setFixedHeight(64)
        self.words.textChanged.connect(self._box_edited)
        self.description = QPlainTextEdit()
        self.description.setPlaceholderText("What it looks like: for text, the lettering (size, weight, colour)")
        self.description.setFixedHeight(72)
        self.description.textChanged.connect(self._box_edited)
        self.position = [QSpinBox(minimum=0, maximum=99999, buttonSymbols=QSpinBox.NoButtons) for _ in range(4)]
        for box in self.position:
            box.editingFinished.connect(self._position_edited)
        self.box_form = QFormLayout()
        self.box_form.addRow("Kind", self.kind)
        self.box_form.addRow("Words", self.words)
        self.box_form.addRow("Description", self.description)
        for title, pair in (("Position", self.position[:2]), ("Size", self.position[2:])):
            row = QHBoxLayout()
            for name, box in zip(("x", "y") if title == "Position" else ("w", "h"), pair):
                box.setFixedWidth(72)
                row.addWidget(QLabel(name))
                row.addWidget(box)
            row.addStretch(1)
            self.box_form.addRow(title, row)
        self.box_panel = QWidget()
        self.box_panel.setLayout(self.box_form)

        side = QVBoxLayout()
        side.addWidget(QLabel("The whole picture"))
        side.addWidget(self.caption)
        side.addWidget(self.meta)
        side.addSpacing(10)
        side.addWidget(QLabel("Boxes"))
        side.addWidget(self.boxes, 1)
        buttons = QHBoxLayout()
        for b in (add_text, add_object, self.delete):
            buttons.addWidget(b)
        side.addLayout(buttons)
        side.addWidget(self.box_panel)
        side_widget = QWidget()
        side_widget.setLayout(side)
        side_widget.setFixedWidth(360)

        middle = QHBoxLayout()
        middle.addWidget(self.canvas, 1)
        middle.addWidget(side_widget)

        hint = QLabel("Drag on the picture to draw a box; drag a box to move it, its corners to resize it. "
                      "Arrow keys move the selected box (⇧ for one pixel). Everything is kept when you close.")
        hint.setForegroundRole(QPalette.PlaceholderText)
        hint.setWordWrap(True)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.show_picture = QCheckBox("Show picture")
        self.show_picture.setVisible(self.canvas.backdrop is not None)
        self.show_picture.setChecked(self.canvas.show_backdrop)
        self.show_picture.toggled.connect(self._toggle_backdrop)
        remove = QPushButton("Remove layout")
        remove.setToolTip("Go back to the typed prompt; the layout is kept, and Layout… brings it back")
        remove.clicked.connect(lambda: self._finish("remove"))
        delete = QPushButton("Delete layout", objectName="destructive")
        delete.setToolTip("Throw this layout away (pictures made from it keep theirs)")
        delete.clicked.connect(self._delete)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.info, 1)
        bottom.addWidget(self.show_picture)
        bottom.addWidget(delete)
        bottom.addWidget(remove)
        bottom.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(middle, 1)
        layout.addLayout(bottom)
        self.resize(1200, 820)
        self._refresh()
        self.canvas.select(0 if self.draft["items"] else -1)

    def _toggle_backdrop(self, on):
        self.canvas.show_backdrop = on
        self.canvas.update()

    def _add(self, label):
        w, h = self.draft["width"], self.draft["height"]
        bw, bh = (w // 2, h // 8) if label == "text" else (w // 3, h // 3)
        self.canvas.add(((w - bw) / 2, (h - bh) / 2, (w + bw) / 2, (h + bh) / 2), label)
        (self.words if label == "text" else self.description).setFocus()

    def _finish(self, action):
        self.action = action
        self.accept()

    def _delete(self):
        if self.confirm_delete is None or self.confirm_delete(self.draft, self):
            self._finish("delete")

    def _summary_edited(self, *_):
        summary = self.draft["summary"]
        summary["caption"] = self.caption.toPlainText()
        meta = [m.strip() for m in self.meta.text().split(",") if m.strip()]
        if meta:
            summary["meta"] = meta
        else:
            summary.pop("meta", None)
        self._refresh(keep_list=True)

    def _show_box(self, index):
        """Fill the box fields from the selected box, without echoing the edits back."""
        has = 0 <= index < len(self.draft["items"])
        self.box_panel.setEnabled(has)
        self.delete.setEnabled(has)
        if self.boxes.currentRow() != index:
            self.boxes.blockSignals(True)
            self.boxes.setCurrentRow(index)
            self.boxes.blockSignals(False)
        widgets = (self.kind, self.words, self.description, *self.position)
        for w in widgets:
            w.blockSignals(True)
        item = self.draft["items"][index] if has else {"label": "object", "caption": "", "bbox": [0, 0, 0, 0]}
        self.kind.setCurrentIndex(list(KINDS).index(item["label"]))
        self.words.setPlainText(item.get("text", ""))
        self.description.setPlainText(item.get("caption", ""))
        x1, y1, x2, y2 = item["bbox"]
        for box, v in zip(self.position, (x1, y1, x2 - x1, y2 - y1)):
            box.setValue(round(v))
        for w in widgets:
            w.blockSignals(False)
        self.box_form.setRowVisible(self.words, item["label"] == "text")

    def _box_edited(self, *_):
        i = self.canvas.current
        if i < 0:
            return
        item = self.draft["items"][i]
        item["label"] = self.kind.currentData()
        item["caption"] = self.description.toPlainText()
        words = self.words.toPlainText()
        if item["label"] == "text" or words.strip():
            item["text"] = words
        else:
            item.pop("text", None)
        self.box_form.setRowVisible(self.words, item["label"] == "text")
        self.canvas.update()
        self._refresh(keep_list=True)

    def _position_edited(self):
        i = self.canvas.current
        if i >= 0:
            x, y, w, h = (b.value() for b in self.position)
            self.canvas.set_box(i, (x, y, x + w, y + h))

    def _refresh(self, keep_list=False):
        """The box list, the selected box's position fields, and the readiness line."""
        items = self.draft["items"]
        if keep_list and self.boxes.count() == len(items):
            for i, it in enumerate(items):
                self.boxes.item(i).setText(list_text(it))
        else:
            self.boxes.blockSignals(True)
            self.boxes.clear()
            self.boxes.addItems([list_text(it) for it in items])
            self.boxes.setCurrentRow(self.canvas.current)
            self.boxes.blockSignals(False)
        i = self.canvas.current
        if 0 <= i < len(items) and not keep_list:
            x1, y1, x2, y2 = items[i]["bbox"]
            for box, v in zip(self.position, (x1, y1, x2 - x1, y2 - y1)):
                box.blockSignals(True)
                box.setValue(round(v))
                box.blockSignals(False)
        try:
            L.check(self.draft)
            self.info.setForegroundRole(QPalette.PlaceholderText)
            self.info.setText(f"{self.draft['width']} × {self.draft['height']} · {len(items)} "
                              f"box{'es' if len(items) != 1 else ''} · ready")
        except ValueError as exc:
            self.info.setForegroundRole(QPalette.WindowText)
            self.info.setText(f"{self.draft['width']} × {self.draft['height']} · Still to do: {exc}")
