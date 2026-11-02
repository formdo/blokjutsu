"""Background-decoded, display-sized image cache with an LRU byte budget."""
from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap

WIDTH_QUANTUM = 256


def bucket(width):
    return max(WIDTH_QUANTUM, -(-int(width) // WIDTH_QUANTUM) * WIDTH_QUANTUM)


class _Decode(QRunnable):
    def __init__(self, done, path, width):
        super().__init__()
        self.done, self.path, self.width = done, path, width

    def run(self):
        image = QImage(self.path)
        full = image.width() <= self.width
        if not image.isNull() and not full:
            image = image.scaledToWidth(self.width, Qt.SmoothTransformation)
        self.done.emit(self.path, self.width, full, image.convertToFormat(QImage.Format_ARGB32_Premultiplied))


class ImageCache(QObject):
    """get() is non-blocking; request() queues a decode; ready(path) fires when a decode lands."""
    ready = Signal(str)
    _done = Signal(str, int, bool, QImage)

    def __init__(self, budget_mb=4096, threads=4, parent=None):
        super().__init__(parent)
        self.budget = budget_mb << 20
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(threads)
        self.items = OrderedDict()      # path -> (width, full, QPixmap)
        self.pending = {}               # path -> width
        self.bytes = 0
        self._done.connect(self._store)

    def get(self, path):
        item = self.items.get(path)
        if item is None:
            return None
        self.items.move_to_end(path)
        return item[2]

    def satisfied(self, path, width):
        item = self.items.get(path)
        return item is not None and (item[1] or item[0] >= width)

    def request(self, path, width, priority=0):
        width = bucket(width)
        if self.satisfied(path, width) or self.pending.get(path, 0) >= width:
            return
        self.pending[path] = width
        self.pool.start(_Decode(self._done, path, width), priority)

    def clear(self):
        for path in list(self.items):
            self.evict(path)
        self.pending.clear()

    def evict(self, path):
        item = self.items.pop(path, None)
        if item is not None:
            self.bytes -= _size(item[2])

    def _store(self, path, width, full, image):
        if self.pending.get(path) == width:
            del self.pending[path]
        if image.isNull():
            return
        self.evict(path)
        pixmap = QPixmap.fromImage(image)
        self.items[path] = (width, full, pixmap)
        self.bytes += _size(pixmap)
        while self.bytes > self.budget and len(self.items) > 1:
            self.evict(next(iter(self.items)))
        self.ready.emit(path)


def _size(pixmap):
    return pixmap.width() * pixmap.height() * 4
