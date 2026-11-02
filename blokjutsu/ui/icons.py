"""Icons: macOS SF Symbols, each drawn once into bitmaps through AppKit (PyObjC) and tinted.

Qt's own theme-icon engine asked AppKit to redraw symbols on every repaint, and one such redraw crashed the app.
Here AppKit is used only once per icon, on the main thread; Qt only ever sees plain pixmaps. Where a symbol is
unavailable (not macOS, or rendering fails) the button simply has no icon.
"""
from __future__ import annotations

import logging
import math
import sys

from PySide6.QtGui import QColor, QIcon, QPixmap

log = logging.getLogger(__name__)
BLUE = "#3662e3"
RED = "#d70015"
SYMBOLS = {"rotate": "rotate.right", "folder": "folder", "copy": "doc.on.doc", "trash": "trash",
           "remove": "xmark", "photo": "photo"}
POINT_SIZE = 13
_cache = {}


def _png(name, color, scale):
    """PNG bytes of SF Symbol `name` tinted `color` at `scale` pixels per point, or None."""
    from AppKit import (
        NSBitmapImageRep, NSCalibratedRGBColorSpace, NSColor, NSCompositingOperationSourceAtop,
        NSCompositingOperationSourceOver, NSFontWeightRegular, NSGraphicsContext, NSImage,
        NSImageSymbolConfiguration, NSPNGFileType, NSRectFillUsingOperation,
    )
    from Foundation import NSMakeRect, NSZeroRect

    image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if image is None:
        return None
    config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(POINT_SIZE, NSFontWeightRegular)
    image = image.imageWithSymbolConfiguration_(config)
    size = image.size()
    w, h = math.ceil(size.width * scale), math.ceil(size.height * scale)
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(  # noqa: E501
        None, w, h, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 32)
    rep.setSize_(size)
    NSGraphicsContext.saveGraphicsState()
    try:
        NSGraphicsContext.setCurrentContext_(NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        rect = NSMakeRect(0, 0, size.width, size.height)
        image.drawInRect_fromRect_operation_fraction_(rect, NSZeroRect, NSCompositingOperationSourceOver, 1.0)
        c = QColor(color)
        NSColor.colorWithCalibratedRed_green_blue_alpha_(c.redF(), c.greenF(), c.blueF(), 1.0).set()
        NSRectFillUsingOperation(rect, NSCompositingOperationSourceAtop)      # tint the symbol's own pixels
    finally:
        NSGraphicsContext.restoreGraphicsState()
    return bytes(rep.representationUsingType_properties_(NSPNGFileType, {}))


def _render(name, color):
    result = QIcon()
    for scale in (1, 2, 3):
        data = _png(name, color, scale)
        pixmap = QPixmap()
        if data is None or not pixmap.loadFromData(data, "PNG"):
            return QIcon()
        pixmap.setDevicePixelRatio(scale)
        result.addPixmap(pixmap)
    return result


def icon(shape, color=BLUE):
    """The system symbol for `shape` tinted `color`; an empty icon off macOS or on failure."""
    key = (shape, color)
    if key not in _cache:
        _cache[key] = QIcon()
        if sys.platform == "darwin":
            try:
                _cache[key] = _render(SYMBOLS[shape], color)
            except Exception:
                log.exception("System symbol %s could not be rendered.", SYMBOLS.get(shape))
    return _cache[key]
