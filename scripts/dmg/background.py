"""Draw the disk image window's background: an arrow from the app to Applications, and how to install.

Usage: python background.py OUT.png SCALE   (the window is 520 × 320 points; SCALE 2 for Retina)
"""
import sys

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 520, 320
APP_X, APPS_X, ICON_Y = 130, 390, 125   # icon centers, as placed by make_dmg.sh
TEXT = "Drag Blokjutsu onto Applications to install it."
GREY = (120, 120, 120)


def font(size):
    for path in ("/System/Library/Fonts/HelveticaNeue.ttc", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def draw(scale):
    s = lambda v: round(v * scale)
    image = Image.new("RGB", (s(WIDTH), s(HEIGHT)), (246, 246, 246))
    d = ImageDraw.Draw(image)
    x0, x1, y = s(APP_X + 80), s(APPS_X - 80), s(ICON_Y)
    d.line([(x0, y), (x1 - s(6), y)], fill=GREY, width=s(4))
    d.polygon([(x1, y), (x1 - s(16), y - s(10)), (x1 - s(16), y + s(10))], fill=GREY)
    d.text((s(WIDTH / 2), s(HEIGHT - 70)), TEXT, fill=(60, 60, 60), font=font(s(15)), anchor="mm")
    return image


if __name__ == "__main__":
    draw(float(sys.argv[2])).save(sys.argv[1])
