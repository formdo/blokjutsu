"""Input-image well: shows a thumbnail, accepts dropped image files, opens a file chooser when clicked."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QImageReader, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.bmp)"
SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}


def mask_overlay(path, alpha=0.45, size=600):
    """Mask file → translucent red QImage (alpha ∝ mask), at most `size` px."""
    import numpy as np
    from PIL import Image, ImageOps

    from PySide6.QtGui import QImage

    with Image.open(path) as mask:
        mask = ImageOps.exif_transpose(mask).convert("L")
        mask.thumbnail((size, size))
    a = np.asarray(mask, dtype=np.float32) * alpha
    rgba = np.zeros(a.shape + (4,), dtype=np.uint8)
    rgba[..., 0] = 230
    rgba[..., 1] = 40
    rgba[..., 2] = 40
    rgba[..., 3] = a.astype(np.uint8)
    h, w = a.shape
    return QImage(np.ascontiguousarray(rgba).data, w, h, 4 * w, QImage.Format_RGBA8888).copy()


class ImageWell(QWidget):
    changed = Signal(str)          # path, or "" when cleared
    activated = Signal()           # clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.path = ""
        self.pixmap = None
        self.overlay = None
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(132)

    def set_path(self, path):
        self.path = path or ""
        self.pixmap = None
        if self.path:
            reader = QImageReader(self.path)
            reader.setAutoTransform(True)
            reader.setScaledSize(reader.size().scaled(QSize(600, 600), Qt.KeepAspectRatio))
            image = reader.read()
            self.pixmap = QPixmap.fromImage(image) if not image.isNull() else None
        self.update()
        self.changed.emit(self.path)

    def set_mask(self, path):
        """Show an inpainting mask over the image (translucent red where it may change)."""
        self.overlay = mask_overlay(path) if path else None
        self.update()

    def choose(self):
        start = str(Path(self.path).parent) if self.path else str(Path.home() / "Pictures")
        path, _ = QFileDialog.getOpenFileName(self, "Choose input image", start, IMAGE_FILTER)
        if path:
            self.set_path(path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit()

    def dragEnterEvent(self, event):
        if self._dropped_path(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self._dropped_path(event)
        if path:
            self.set_path(path)
            event.acceptProposedAction()

    @staticmethod
    def _dropped_path(event):
        for url in event.mimeData().urls():
            if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in SUFFIXES:
                return url.toLocalFile()
        return None

    def paintEvent(self, _):
        painter = QPainter(self)
        try:
            self._paint(painter)
        finally:
            painter.end()     # an exception must never leave the painter active (that crashes Qt)

    def _paint(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.pixmap is not None:
            size = QSizeF(self.pixmap.size()).scaled(rect.size(), Qt.KeepAspectRatio)
            target = QRectF(0, 0, size.width(), size.height())
            target.moveCenter(rect.center())
            painter.drawPixmap(target.toRect(), self.pixmap)
            if self.overlay is not None:
                painter.drawImage(target, self.overlay)
            return
        pen = QPen(self.palette().color(QPalette.PlaceholderText))
        pen.setWidthF(1.2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10.0, 10.0)
        painter.drawText(rect, int(Qt.AlignCenter), "Drop an image here\nor click to choose")
