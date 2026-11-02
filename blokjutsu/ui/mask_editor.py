"""Select area to change: inpainting, outpainting and cropping.

Paint where the image may change (Erase, or hold ⌥, to take paint away); extend any side to outpaint or pull it
in to crop, with the margin boxes or by dragging the dashed frame. The editor works on the input fitted to the generation size (≤ 2.1 MP, multiples of 16), so the
saved mask and image line up with what the model sees.
"""
from __future__ import annotations

import uuid

import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QRadioButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .. import img2img as I
from ..settings import app_home

RED = QColor(230, 40, 40, 115)
MARGIN_STEP = 64
MAX_MARGIN = 2048     # px added on one side
MIN_SIDE = 64         # smallest side of the new picture
VIEW_PAD = 36         # room around the picture to drag the frame outwards
GRAB = 6              # px either side of a frame edge that grabs it
CROP_VEIL = 205       # alpha of the window color laid over cropped-away parts


def to_qimage(image):
    rgb = np.ascontiguousarray(np.asarray(image.convert("RGB")))
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def gray_array(qimage):
    """Grayscale8 QImage → float32 [h, w] in [0, 1] (rows may be padded)."""
    h, w = qimage.height(), qimage.width()
    bits = np.frombuffer(qimage.constBits(), dtype=np.uint8, count=qimage.bytesPerLine() * h)
    return bits.reshape(h, qimage.bytesPerLine())[:, :w].astype(np.float32) / 255.0


def work_image(path):
    """The input as the model will see it: upright, covered to its fitted generation size."""
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    return I.cover(image, *I.fit_size(*image.size))


class Canvas(QWidget):
    """The picture with the selection over it. Paints the selection with the mouse; the dashed frame is the new
    picture's edge, and dragging a side extends (outwards) or crops (inwards), as do the margin boxes."""
    changed = Signal()
    margins_dragged = Signal(tuple)

    def __init__(self, image, mask=None, parent=None):
        super().__init__(parent)
        self.image = image                                   # PIL, as the model sees it
        self.base = to_qimage(image)
        w, h = image.size
        self.mask = QImage(w, h, QImage.Format_Grayscale8)
        self.mask.fill(0)
        self.overlay = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        self.overlay.fill(Qt.transparent)
        if mask is not None:
            self._load(mask)
        self.margins = (0, 0, 0, 0)                          # left, top, right, bottom; negative = crop
        self.extended = self.base
        self.brush, self.erase, self.last, self.pointer = 48, False, None, None
        self.drag, self.hover_edge = None, None
        self.setMouseTracking(True)
        self.setMinimumSize(480, 360)

    def _load(self, mask):
        a = np.ascontiguousarray((np.asarray(mask, dtype=np.float32) * 255 + 0.5).astype(np.uint8))
        h, w = a.shape
        self.mask = QImage(a.data, w, h, w, QImage.Format_Grayscale8).copy()
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        alpha = (a.astype(np.float32) * RED.alphaF()).astype(np.uint8)
        for c, v in enumerate((RED.red(), RED.green(), RED.blue())):
            rgba[..., c] = (v * alpha.astype(np.uint16) // 255).astype(np.uint8)    # premultiplied
        rgba[..., 3] = alpha
        self.overlay = QImage(rgba.data, w, h, 4 * w, QImage.Format_RGBA8888_Premultiplied).convertToFormat(
            QImage.Format_ARGB32_Premultiplied)

    # geometry: "view" = the picture plus any added space; the frame (new picture) lies inside it

    def pads(self):
        return tuple(max(0, m) for m in self.margins)

    def view_size(self):
        pl, pt, pr, pb = self.pads()
        return self.image.width + pl + pr, self.image.height + pt + pb

    def frame(self):
        """The new picture's rectangle in view coordinates."""
        l, t, r, b = self.margins
        vw, vh = self.view_size()
        return QRectF(max(0, -l), max(0, -t), vw - max(0, -l) - max(0, -r), vh - max(0, -t) - max(0, -b))

    def size_with_margins(self):
        l, t, r, b = self.margins
        return self.image.width + l + r, self.image.height + t + b

    def target(self):
        """Where the view is drawn, with room around it to drag the frame outwards."""
        vw, vh = self.view_size()
        room = QRectF(self.rect()).adjusted(VIEW_PAD, VIEW_PAD, -VIEW_PAD, -VIEW_PAD)
        scale = min(room.width() / vw, room.height() / vh)
        rect = QRectF(0, 0, vw * scale, vh * scale)
        rect.moveCenter(room.center())
        return rect, scale

    def to_image(self, pos, transform=None):
        rect, scale, pl, pt = transform or (*self.target(), *self.pads()[:2])
        return QPointF((pos.x() - rect.left()) / scale - pl, (pos.y() - rect.top()) / scale - pt)

    def edge_at(self, pos):
        """'left', 'top', 'right' or 'bottom' if `pos` is on that side of the frame, else None."""
        rect, scale = self.target()
        f = self.frame()
        x0, y0 = rect.left() + f.left() * scale, rect.top() + f.top() * scale
        x1, y1 = rect.left() + f.right() * scale, rect.top() + f.bottom() * scale
        x, y = pos.x(), pos.y()
        within_y, within_x = y0 - GRAB <= y <= y1 + GRAB, x0 - GRAB <= x <= x1 + GRAB
        for edge, near in (("left", within_y and abs(x - x0) <= GRAB), ("right", within_y and abs(x - x1) <= GRAB),
                           ("top", within_x and abs(y - y0) <= GRAB), ("bottom", within_x and abs(y - y1) <= GRAB)):
            if near:
                return edge
        return None

    # editing

    def set_margins(self, margins):
        self.margins = tuple(int(m) for m in margins)
        if any(self.pads()):
            canvas, _ = I.reframe(self.image, *self.pads())
            self.extended = to_qimage(canvas)
        else:
            self.extended = self.base
        self.update()
        self.changed.emit()

    def clear(self):
        self.mask.fill(0)
        self.overlay.fill(Qt.transparent)
        self.update()
        self.changed.emit()

    def _stroke(self, a, b, erase):
        grey = QColor(0, 0, 0) if erase else QColor(255, 255, 255)
        layers = ((self.mask, grey, QPainter.CompositionMode_Source),
                  (self.overlay, RED, QPainter.CompositionMode_Clear if erase else QPainter.CompositionMode_Source))
        for target, color, mode in layers:
            painter = QPainter(target)
            try:
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setCompositionMode(mode)
                painter.setPen(QPen(color, self.brush, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                if a == b:
                    painter.drawPoint(a)
                else:
                    painter.drawLine(a, b)
            finally:
                painter.end()
        self.update()

    def _drag_to(self, pos):
        edge, transform = self.drag
        p = self.to_image(pos, transform)
        w, h = self.image.size
        l, t, r, b = self.margins
        snap = lambda v: int(16 * round(v / 16))                  # noqa: E731
        if edge == "left":
            l = max(min(snap(-p.x()), MAX_MARGIN), MIN_SIDE - w - r)
        elif edge == "right":
            r = max(min(snap(p.x() - w), MAX_MARGIN), MIN_SIDE - w - l)
        elif edge == "top":
            t = max(min(snap(-p.y()), MAX_MARGIN), MIN_SIDE - h - b)
        else:
            b = max(min(snap(p.y() - h), MAX_MARGIN), MIN_SIDE - h - t)
        if (l, t, r, b) != self.margins:
            self.set_margins((l, t, r, b))
            self.margins_dragged.emit(self.margins)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        edge = self.edge_at(event.position())
        if edge:
            self.drag = (edge, (*self.target(), *self.pads()[:2]))
            return
        self.last = self.to_image(event.position())
        self._stroke(self.last, self.last, self._erasing(event))

    def mouseMoveEvent(self, event):
        self.pointer = event.position()
        if self.drag is not None:
            self._drag_to(event.position())
            return
        if self.last is not None:
            point = self.to_image(event.position())
            self._stroke(self.last, point, self._erasing(event))
            self.last = point
        else:
            self.hover_edge = self.edge_at(event.position())
            self.setCursor({"left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor, "top": Qt.SizeVerCursor,
                            "bottom": Qt.SizeVerCursor}.get(self.hover_edge, Qt.BlankCursor))
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            self.drag = None
            return
        if self.last is not None:
            self.last = None
            self.changed.emit()

    def leaveEvent(self, event):
        self.pointer = None
        self.update()

    def _erasing(self, event):
        return self.erase or bool(event.modifiers() & Qt.AltModifier)

    def paintEvent(self, _):
        painter = QPainter(self)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter):
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect, scale = self.target()
        pl, pt, _, _ = self.pads()
        vw, vh = self.view_size()
        painter.save()
        painter.translate(rect.topLeft())
        painter.scale(scale, scale)
        painter.drawImage(QRectF(0, 0, vw, vh), self.extended)
        picture = QRectF(pl, pt, self.image.width, self.image.height)
        frame = self.frame()
        painter.setPen(Qt.NoPen)
        added = QPainterPath()
        added.addRect(frame)
        hole = QPainterPath()
        hole.addRect(picture)
        painter.fillPath(added.subtracted(hole), RED)                      # new space, to be filled in
        painter.drawImage(picture, self.overlay)                            # painted selection
        whole = QPainterPath()
        whole.addRect(QRectF(0, 0, vw, vh))
        veil = self.palette().color(QPalette.Window)
        veil.setAlpha(CROP_VEIL)
        painter.fillPath(whole.subtracted(added), veil)                     # cropped away: very faint
        painter.restore()
        edge = QRectF(rect.left() + frame.left() * scale, rect.top() + frame.top() * scale,
                      frame.width() * scale, frame.height() * scale)
        for color, style in ((QColor(255, 255, 255, 220), Qt.SolidLine), (QColor(40, 40, 40, 230), Qt.DashLine)):
            pen = QPen(color, 1.5, style)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(edge)
        if self.pointer is not None and self.drag is None and self.hover_edge is None:
            radius = self.brush * scale / 2
            for color, width in ((QColor(0, 0, 0, 160), 3), (QColor(255, 255, 255), 1.2)):
                painter.setPen(QPen(color, width))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.pointer, radius, radius)

    # result

    def result(self, feather):
        """(new picture PIL or None if unchanged in extent, selection float32 [H, W]), at the generation size."""
        painted = gray_array(self.mask)
        if any(self.margins):
            l, t, r, b = self.margins
            canvas, mask = I.reframe(self.image, l, t, r, b)
            I.place(mask, painted, l, t)
        else:
            canvas, mask = None, painted
        mask = I.feather(mask, feather)
        if canvas is not None:
            size = I.fit_size(*canvas.size)
            if size != canvas.size:
                canvas = I.cover(canvas, *size)
                mask_image = Image.fromarray((mask * 255 + 0.5).astype(np.uint8))
                mask = np.asarray(ImageOps.fit(mask_image, size, Image.LANCZOS), dtype=np.float32) / 255.0
        return canvas, mask


class MaskEditor(QDialog):
    """Sets `paths` = (image_path, mask_path) however it is closed (Close, Esc or the window's close button);
    mask_path is '' if nothing is selected."""

    def __init__(self, image_path, mask_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select area to change")
        self.image_path, self.paths = image_path, None
        image = work_image(image_path)
        mask = None
        if mask_path:
            with Image.open(mask_path) as m:
                mask = np.asarray(ImageOps.fit(m.convert("L"), image.size, Image.LANCZOS), dtype=np.float32) / 255
        self.canvas = Canvas(image, mask)
        self.canvas.changed.connect(self._update_info)
        self.canvas.margins_dragged.connect(self._margins_dragged)

        paint, erase = QRadioButton("Paint"), QRadioButton("Erase")
        paint.setChecked(True)
        erase.toggled.connect(lambda on: setattr(self.canvas, "erase", on))
        paint.setToolTip("Paint over the part of the picture to redo")
        erase.setToolTip("Take paint away (or hold ⌥ while painting)")
        clear = QPushButton("Clear")
        clear.setToolTip("Remove all paint")
        clear.clicked.connect(self.canvas.clear)
        self.brush = self._slider(4, 400, self.canvas.brush, lambda v: setattr(self.canvas, "brush", v))
        self.feather = self._slider(0, 64, 12, lambda v: None)
        self.feather.setToolTip("How softly the new part blends into the rest")

        tools = QHBoxLayout()
        tools.setSpacing(6)
        for group in ((paint, erase, clear), (QLabel("Brush size"), self.brush),
                      (QLabel("Feather size"), self.feather)):
            for w in group:
                tools.addWidget(w)
            tools.addSpacing(22)
        tools.addStretch(1)

        self.margin_boxes = []
        extend = QHBoxLayout()
        extend.setSpacing(6)
        extend.addWidget(QLabel("Extend (+) or crop (−):"))
        for name in ("Left", "Top", "Right", "Bottom"):
            box = QSpinBox(minimum=-4096, maximum=MAX_MARGIN, singleStep=MARGIN_STEP, suffix=" px")
            box.setToolTip("Positive adds new space on this side, filled in to match; negative crops it off. "
                           "You can also drag the dashed edge.")
            box.valueChanged.connect(self._margins_changed)
            self.margin_boxes.append(box)
            extend.addSpacing(10)
            extend.addWidget(QLabel(name))
            extend.addWidget(box)
        extend.addStretch(1)

        hint = QLabel("Paint over the part to redo; it shows in red. Hold ⌥ to erase. Drag the dashed edge out to "
                      "extend the picture or in to crop it. Everything is kept when you close this window.")
        hint.setForegroundRole(QPalette.PlaceholderText)
        self.info = QLabel()
        self.info.setForegroundRole(QPalette.PlaceholderText)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(self.info, 1)
        bottom.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addLayout(extend)
        layout.addWidget(hint)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(bottom)
        self.resize(1100, 860)
        self._update_info()

    @staticmethod
    def _slider(lo, hi, value, on_change):
        slider = QSlider(Qt.Horizontal, minimum=lo, maximum=hi, value=value)
        slider.setFixedWidth(140)
        slider.valueChanged.connect(on_change)
        return slider

    def _margins_changed(self):
        self.canvas.set_margins([16 * round(b.value() / 16) for b in self.margin_boxes])

    def _margins_dragged(self, margins):
        for box, value in zip(self.margin_boxes, margins):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)

    def _update_info(self):
        w, h = self.canvas.size_with_margins()
        fw, fh = I.fit_size(w, h)
        painted = float(gray_array(self.canvas.mask).mean())
        parts = [f"New picture {fw} × {fh} ({fw * fh / 1e6:.1f} MP)"]
        if any(m > 0 for m in self.canvas.margins):
            parts.append("the added space will be filled in")
        if any(m < 0 for m in self.canvas.margins):
            parts.append("cropped")
        parts.append(f"{painted:.0%} of the picture selected")
        self.info.setText(" · ".join(parts))

    def done(self, result):
        if self.paths is None:
            self._save()
        super().done(QDialog.Accepted)

    def _save(self):
        canvas, mask = self.canvas.result(self.feather.value())
        folder = app_home() / "work"
        folder.mkdir(parents=True, exist_ok=True)
        stem = uuid.uuid4().hex[:12]
        image_path, mask_path = self.image_path, ""
        if canvas is not None:                       # extended or cropped: a new picture
            image_path = str(folder / f"{stem}-input.png")
            canvas.save(image_path)
        if float(mask.max()) > 0.0:
            mask_path = str(folder / f"{stem}-mask.png")
            Image.fromarray((mask * 255 + 0.5).astype(np.uint8)).save(mask_path)
        self.paths = (image_path, mask_path)
