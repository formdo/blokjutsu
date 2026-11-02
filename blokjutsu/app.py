"""Entry point: `python -m blokjutsu [--fake]` or the `blokjutsu` script."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __version__
from .settings import SUPPORT, use_own_model_folder

ICON = Path(__file__).with_name("resources") / "icon.png"


class _DropSchedulerConfigNoise(logging.Filter):
    """The model's scheduler_config.json carries FlowMatchEuler fields MOSSImageScheduler doesn't take."""

    def filter(self, record):
        return "were passed to MOSSImageScheduler" not in record.getMessage()


TRIAL_HOME = SUPPORT / "Blokjutsu Trial.noindex"   # --fake, kept apart

def set_macos_app_name(name):
    """Menu-bar name when launched through a venv interpreter rather than a real bundle executable."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle
    except ImportError:
        return
    info = NSBundle.mainBundle().localizedInfoDictionary() or NSBundle.mainBundle().infoDictionary()
    if info is not None:
        info["CFBundleName"] = name


UNWANTED_EDIT_ITEMS = {"Writing Tools", "AutoFill"}


def trim_edit_menu():
    """Remove the items macOS adds to every Edit menu that do nothing here; call after launch."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication
    except ImportError:
        return
    item = NSApplication.sharedApplication().mainMenu().itemWithTitle_("Edit")
    menu = item.submenu() if item is not None else None
    if menu is None:
        return
    for entry in list(menu.itemArray()):
        if entry.title() in UNWANTED_EDIT_ITEMS:
            menu.removeItem_(entry)
    while menu.numberOfItems() and menu.itemAtIndex_(menu.numberOfItems() - 1).isSeparatorItem():
        menu.removeItemAtIndex_(menu.numberOfItems() - 1)


def quiet_third_party():
    """Silence known-harmless startup chatter; real warnings and errors still get through."""
    import warnings

    warnings.filterwarnings("ignore", message=r".*`torch_dtype` is deprecated", category=FutureWarning)


def enable_crash_reports():
    """Print the Python stack on native crashes (including macOS 'trace trap') and log Qt's own messages."""
    import faulthandler
    import signal

    faulthandler.enable(all_threads=True)
    for name in ("SIGTRAP", "SIGUSR1"):
        if hasattr(signal, name):
            faulthandler.register(getattr(signal, name), all_threads=True, chain=True)

    from PySide6.QtCore import qInstallMessageHandler

    qt_log = logging.getLogger("qt")

    def handler(kind, context, message):
        qt_log.warning("%s (%s:%s)", message, context.file, context.line)
        sys.stderr.flush()

    qInstallMessageHandler(handler)


def main(argv=None):
    from .network import go_offline

    go_offline()                   # before anything imports huggingface_hub / diffusers / transformers
    enable_crash_reports()
    parser = argparse.ArgumentParser(prog="blokjutsu")
    parser.add_argument("--fake", action="store_true", help="draw placeholder images instead of loading the model")
    parser.add_argument("--first-run", action="store_true",
                        help="with --fake: behave as if nothing is downloaded yet (simulated downloads)")
    parser.add_argument("--home", help="folder for settings and logs (default: $BLOKJUTSU_HOME or "
                                       "~/Library/Application Support/Blokjutsu.noindex; with --fake, "
                                       "…/Blokjutsu Trial.noindex)")
    args, qt_args = parser.parse_known_args(argv)
    if args.home:
        os.environ["BLOKJUTSU_HOME"] = args.home
    elif args.fake and "BLOKJUTSU_HOME" not in os.environ:
        os.environ["BLOKJUTSU_HOME"] = str(TRIAL_HOME)
    use_own_model_folder()
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .logs import log_to_file
    log_to_file()
    quiet_third_party()

    set_macos_app_name("Blokjutsu")
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("Blokjutsu")
    app.setOrganizationName("Blokjutsu")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(ICON)))
    logging.getLogger("diffusers.configuration_utils").addFilter(_DropSchedulerConfigNoise())

    from .settings import app_home
    from .single_instance import SingleInstance

    instance = SingleInstance(app_home())
    if not instance.acquire():
        logging.info("Blokjutsu is already running for %s; activating it.", app_home())
        return

    from .backend import Backend, FakeBackend
    from .ui.main_window import MainWindow

    fake = args.fake or os.environ.get("BLOKJUTSU_FAKE") == "1"
    from .ui import input as input_policy

    input_filters = input_policy.install(app)  # noqa: F841  (kept alive for the app's lifetime)
    from .ui import theme
    button_fitter = theme.install_button_fitter(app)  # noqa: F841
    window = MainWindow(FakeBackend(first_run=args.first_run) if fake else Backend())
    if fake:
        window.setWindowTitle("Blokjutsu (fake backend)")
    instance.listen(window.bring_to_front)
    window.show()
    QTimer.singleShot(0, trim_edit_menu)
    QTimer.singleShot(2000, trim_edit_menu)
    sys.exit(app.exec())
