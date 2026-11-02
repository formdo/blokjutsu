"""Write the app icon (T1: Froebel blocks, last block landing, tilted clockwise) as SVG and render 1024² PNG.

Apple's macOS icon grid: a 1024² canvas with an 824² rounded square (radius 185) centred, leaving room for the
shadow. Usage: python scripts/make_icon.py   (rendering uses PySide6's SVG renderer)
"""
from pathlib import Path

PAPER, YELLOW, BLUE, RED = "#EFE5CF", "#F2B41C", "#1D4FA3", "#D9302C"
BODY, RADIUS = 824, 185
S, G, R = 288, 20, 10                   # block, gap, corner radius: the blocks span ~72% of the body
X0 = Y0 = (1024 - (2 * S + G)) // 2
TILT, NUDGE = 17, (19, 21)              # degrees clockwise; outward shift of the landing block
RESOURCES = Path(__file__).resolve().parents[1] / "blokjutsu" / "resources"


def cell(c, r, dx=0, dy=0):
    return X0 + c * (S + G) + dx, Y0 + r * (S + G) + dy


def solid(x, y, colour, rot=0):
    return (f'<rect x="{x}" y="{y}" width="{S}" height="{S}" rx="{R}" fill="{colour}" '
            f'transform="rotate({rot} {x + S / 2} {y + S / 2})"/>')


def split(x, y, upper_left, lower_right, uid):
    """Block divided on the '/' diagonal."""
    return (f'<clipPath id="b{uid}"><rect x="{x}" y="{y}" width="{S}" height="{S}" rx="{R}"/></clipPath>'
            f'<g clip-path="url(#b{uid})">'
            f'<polygon points="{x},{y} {x + S},{y} {x},{y + S}" fill="{upper_left}"/>'
            f'<polygon points="{x + S},{y} {x + S},{y + S} {x},{y + S}" fill="{lower_right}"/></g>')


def svg():
    inset = (1024 - BODY) // 2
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">'
        '<defs><filter id="shadow" x="-10%" y="-10%" width="120%" height="125%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#000" flood-opacity="0.28"/></filter></defs>'
        f'<rect x="{inset}" y="{inset}" width="{BODY}" height="{BODY}" rx="{RADIUS}" fill="{PAPER}" '
        'filter="url(#shadow)"/>'
        + solid(*cell(0, 0), YELLOW) + split(*cell(1, 0), BLUE, YELLOW, 1) + split(*cell(0, 1), YELLOW, BLUE, 2)
        + solid(*cell(1, 1, *NUDGE), RED, TILT) + "</svg>")


def render(svg_path, png_path, size=1024):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    QSvgRenderer(str(svg_path)).render(painter)
    painter.end()
    image.save(str(png_path))


if __name__ == "__main__":
    (RESOURCES / "icon.svg").write_text(svg())
    render(RESOURCES / "icon.svg", RESOURCES / "icon.png")
    print("wrote", RESOURCES / "icon.svg", "and icon.png")
