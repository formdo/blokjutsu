"""Left-hand control panel: prompt, main parameters, output folder, collapsible advanced section."""
from __future__ import annotations

import math
import json
import os
import secrets
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QPalette, QPixmap, QRegularExpressionValidator, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QLabel, QSlider, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from .. import layout as L
from .. import lora as R
from .. import models as M
from .. import params as P
from .. import img2img as I
from .. import sizes as S
from ..samplers import SAMPLERS
from .icons import icon
from .theme import CONTROL_HEIGHT, MARGIN, enlarge, medium
from .image_input import IMAGE_FILTER, ImageWell
from .resize_handle import ResizeHandle
from .loras import LoraRow, TriggerHighlighter
from .toggle import ToggleSwitch
from .widgets import labelled


PROMPT_HEIGHT, NEGATIVE_HEIGHT = 96, 56
SLIDER_STEPS = 1000        # variation strength = (position / SLIDER_STEPS)²


def indented(label, pixels=3):
    """Nudge a caption right so it lines up optically with the rounded box below it."""
    label.setContentsMargins(pixels, 0, 0, 0)
    return label


def toggle_row(text, help_key, switch, summary=None):
    """Section header: medium-weight title (clickable help if help_key), its on/off switch, and a muted summary of
    what the closed section holds."""
    row = QHBoxLayout()
    title = medium(labelled(text, help_key) if help_key else QLabel(text))
    title.setObjectName("sectionTitle")
    row.addWidget(title)
    row.addSpacing(10)
    row.addWidget(switch)
    if summary is not None:
        summary.setForegroundRole(QPalette.PlaceholderText)
        summary.setMinimumWidth(1)
        row.addSpacing(10)
        row.addWidget(summary, 1)
    else:
        row.addStretch(1)
    return row


class SeedField(QWidget):
    """A Random checkbox and, when it is unticked, the seed to keep. value() is 0 for Random. The number's space is
    kept while it is hidden, so the row doesn't change height."""
    edited = Signal()

    def __init__(self, tooltip, parent=None):
        super().__init__(parent)
        self.random = QCheckBox("Random")
        self.random.setToolTip(tooltip)
        self.box = QLineEdit()
        self.box.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}")))
        self.box.setFixedWidth(120)
        policy = self.box.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.box.setSizePolicy(policy)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.random)
        row.addWidget(self.box)
        row.addStretch(1)
        self.random.toggled.connect(self._toggled)
        self.box.textEdited.connect(lambda _: self.edited.emit())
        self.box.editingFinished.connect(lambda: self.value() or self.set_value(0))
        self.set_value(0)

    def value(self):
        return 0 if self.random.isChecked() else int(self.box.text() or 0)

    def set_value(self, seed):
        if seed:
            self.box.setText(str(seed))
        self.random.blockSignals(True)
        self.random.setChecked(not seed)
        self.random.blockSignals(False)
        self.box.setVisible(bool(seed))

    def _toggled(self, random_):
        self.box.setVisible(not random_)
        if not random_:
            if not int(self.box.text() or 0):
                self.box.setText(str(secrets.randbelow(P.SEED_MAX) + 1))
            self.box.setFocus()
            self.box.selectAll()
        self.edited.emit()


class ReferenceThumb(QWidget):
    """An extra picture for Edit: a thumbnail, what the prompt calls it ("picture 2"), and Remove."""
    removed = Signal(str)
    SIDE = 72

    def __init__(self, path, number, parent=None):
        super().__init__(parent)
        self.path = path
        image = QLabel()
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            image.setPixmap(pixmap.scaled(self.SIDE, self.SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        image.setFixedSize(self.SIDE, self.SIDE)
        image.setAlignment(Qt.AlignCenter)
        image.setToolTip(path)
        name = QLabel(f"Picture {number}")
        name.setAlignment(Qt.AlignCenter)
        name.setForegroundRole(QPalette.PlaceholderText)
        remove = QPushButton("Remove")
        remove.setProperty("card", True)
        remove.setToolTip("Take this picture out (the file is not deleted)")
        remove.clicked.connect(lambda: self.removed.emit(self.path))
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        column.addWidget(image, 0, Qt.AlignHCenter)
        column.addWidget(name)
        column.addWidget(remove)


class Summary(QLabel):
    """One line, elided at the right, with the whole text as its tooltip."""

    def setText(self, text):
        self.full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        super().setText(self.fontMetrics().elidedText(getattr(self, "full", ""), Qt.ElideRight, self.width()))


ADVANCED_LABELS = {"sampler": "Sampler", "sde_eta": "SDE noise", "shift": "Shift", "uncond_skip_layers": "Uncond skip",
                   "slg_layers": "SLG layers", "slg_scale": "SLG scale", "slg_start": "Skip interval",
                   "slg_stop": "Skip interval", "max_sequence_length": "Max tokens", "sigmas": "Schedule"}


def changed_advanced(p):
    """Names of the advanced settings in p that differ from the defaults, each named once."""
    d = P.Params()
    names = [ADVANCED_LABELS[k] for k in ADVANCED_LABELS if getattr(p, k) != getattr(d, k)
             and (k != "sde_eta" or p.sampler == "Euler SDE")]
    return list(dict.fromkeys(names))


def hairline():
    line = QFrame(objectName="hairline")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def spin(lo, hi, step=1):
    box = QSpinBox()
    box.setRange(lo, hi)
    box.setSingleStep(step)
    return box


def dspin(lo, hi, step, decimals=2):
    box = QDoubleSpinBox()
    box.setRange(lo, hi)
    box.setSingleStep(step)
    box.setDecimals(decimals)
    return box


def separator(text):
    label = QLabel(text)
    label.setForegroundRole(QPalette.PlaceholderText)
    label.setAlignment(Qt.AlignCenter)
    label.setFixedWidth(14)
    return label


def pair(left, label, right):
    """Two fields on one form row: left, then a label and right field taking equal width."""
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(left, 1)
    row.addSpacing(6)
    row.addWidget(label)
    row.addWidget(right, 1)
    return row


def char_count(edit):
    """Muted 'n characters' label that follows a text box."""
    label = QLabel()
    label.setForegroundRole(QPalette.PlaceholderText)

    def update():
        n = len(edit.toPlainText())
        label.setText(f"{n:,} character{'s' if n != 1 else ''}" if n else "")

    edit.textChanged.connect(update)
    return label


def heading(label, *right):
    """Caption row: label on the left, widgets on the right."""
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(label, 0, Qt.AlignBottom)       # labels sit just above their box whatever else is in the row
    row.addStretch(1)
    for w in right:
        row.addWidget(w, 0, Qt.AlignBottom)
    return row


def captioned(label, widget, handle):
    box = QVBoxLayout()
    box.setSpacing(3)
    box.addLayout(label)
    box.addWidget(widget)
    box.addWidget(handle)
    return box


def form_label(text, key):
    """Form label as tall as a single-line control, so it lines up with the first line of its field."""
    label = labelled(text, key)
    label.setFixedHeight(CONTROL_HEIGHT)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return label


def unit(text):
    label = QLabel(text)
    label.setForegroundRole(QPalette.PlaceholderText)
    return label


CUSTOM = "custom"


class ClickLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def form():
    f = QFormLayout()
    f.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
    f.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    f.setHorizontalSpacing(14)
    f.setVerticalSpacing(10)
    f.setRowWrapPolicy(QFormLayout.DontWrapRows)
    f.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    return f


class ControlsPanel(QWidget):
    generateRequested = Signal()
    outputDirEdited = Signal(str)
    describeRequested = Signal(str)          # image path
    enhanceRequested = Signal(str)           # prompt text
    maskRequested = Signal()
    layoutRequested = Signal()
    lorasRequested = Signal()
    modelsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_prompts()
        self._build_main()
        self._build_advanced()
        self._build_model()
        self._build_loras()
        self.generate_button = QPushButton("Generate", objectName="primary")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setToolTip("⌘↩")
        self.generate_button.clicked.connect(self.generateRequested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN, 10, MARGIN, MARGIN)
        layout.setSpacing(8)
        self.prompt_count = char_count(self.prompt)
        prompt_box = captioned(heading(indented(labelled("Prompt", "prompt")), self.prompt_count,
                                       self.enhance_button, self.layout_button), self.prompt, self.prompt_handle)
        prompt_box.insertWidget(2, self.layout_summary)
        prompt_box.insertWidget(4, self.layout_note)
        layout.addLayout(prompt_box)
        layout.addSpacing(2)
        layout.addLayout(captioned(heading(indented(labelled("Negative prompt", "negative_prompt")),
                                           char_count(self.negative)), self.negative, self.negative_handle))
        layout.addSpacing(12)
        layout.addLayout(self.main_form)
        layout.addSpacing(14)
        layout.addWidget(hairline())
        layout.addSpacing(10)
        layout.addLayout(self.input_row)
        layout.addWidget(self.input_block)
        layout.addSpacing(14)
        layout.addWidget(hairline())
        layout.addSpacing(10)
        layout.addLayout(self.variations_row)
        layout.addWidget(self.variations)
        layout.addSpacing(14)
        layout.addWidget(hairline())
        layout.addSpacing(10)
        layout.addLayout(self.model_row)
        layout.addWidget(self.model_block)
        layout.addSpacing(14)
        layout.addWidget(hairline())
        layout.addSpacing(10)
        layout.addLayout(self.loras_row)
        layout.addWidget(self.loras_block)
        layout.addSpacing(14)
        layout.addWidget(hairline())
        layout.addSpacing(10)
        layout.addLayout(self.advanced_row)
        layout.addWidget(self.advanced)
        layout.addStretch(1)
        self._align_section_switches()
        self.set_params(P.Params())

    def _build_prompts(self):
        self.prompt = QPlainTextEdit(objectName="promptEdit")
        self.prompt.setPlaceholderText("Describe the image, or paste a JSON layout")
        self.prompt_handle = ResizeHandle(self.prompt)
        self.prompt_handle.set_height(PROMPT_HEIGHT)
        enlarge(self.prompt)
        self.negative = QPlainTextEdit(objectName="promptEdit")
        self.negative.setPlaceholderText("What to avoid")
        self.negative_handle = ResizeHandle(self.negative)
        self.negative_handle.set_height(NEGATIVE_HEIGHT)
        enlarge(self.negative)
        self.enhance_button = QPushButton("Enhance prompt…")
        self.enhance_button.setProperty("card", True)
        self.enhance_button.setToolTip("Let the model rewrite your prompt with more detail; you pick which version to use")
        self.enhance_button.clicked.connect(
            lambda: self.prompt.toPlainText().strip() and self.enhanceRequested.emit(self.prompt.toPlainText()))
        self.use_layout = False              # whether the draft is the prompt, or only kept for later
        self.draft = None                    # a layout draft (layout.py); when set, it is the prompt
        self.layout_button = QPushButton("Layout…")
        self.layout_button.setProperty("card", True)
        self.layout_button.setToolTip("Place text and things in boxes on the picture")
        self.layout_button.clicked.connect(self.layoutRequested)
        self.layout_summary = ClickLabel(objectName="textBox")
        self.layout_summary.setWordWrap(True)
        self.layout_summary.setToolTip("Click to edit the layout")
        self.layout_summary.clicked.connect(self.layoutRequested)
        self.layout_summary.setVisible(False)
        self.layout_note = ClickLabel()
        self.layout_note.setForegroundRole(QPalette.PlaceholderText)
        self.layout_note.setWordWrap(True)
        self.layout_note.setToolTip("Click to open the layout")
        self.layout_note.clicked.connect(self.layoutRequested)
        self.layout_note.setVisible(False)

    def _build_main(self):
        self._scale_base = (0, 0)
        self.width_box, self.height_box = spin(16, 99999, S.DEFAULT_STEP), spin(16, 99999, S.DEFAULT_STEP)
        for box in (self.width_box, self.height_box):
            box.setFixedWidth(96)
            box.editingFinished.connect(self._snap_size)
            box.valueChanged.connect(lambda _: self._update_size_info())
        self.rotate = QToolButton(icon=icon("rotate"),
                                  toolTip="Swap width and height", objectName="folderButton")
        self.rotate.clicked.connect(lambda: self._set_size(self.height_box.value(), self.width_box.value()))
        self.aspect = QComboBox()
        self.aspect.addItems(S.ASPECTS)
        self.aspect.setPlaceholderText("Aspect")
        self.preset = QComboBox()
        self.preset.setPlaceholderText("MP")
        self.aspect.activated.connect(self._choose_aspect)
        self.preset.activated.connect(lambda i: self._set_size(*map(int, self.preset.itemData(i).split("x"))))
        presets = QHBoxLayout()
        presets.setSpacing(6)
        presets.addWidget(self.aspect, 1)
        presets.addWidget(self.preset, 1)
        dims = QHBoxLayout()
        dims.setSpacing(6)
        dims.addWidget(self.width_box)
        dims.addWidget(unit("W"))
        dims.addWidget(separator("×"))
        dims.addWidget(self.height_box)
        dims.addWidget(unit("H"))
        dims.addSpacing(4)
        dims.addWidget(self.rotate)
        dims.addStretch(1)
        size_field = dims

        self.count = spin(1, 64)
        self.seed = SeedField("A new seed for each picture; untick to keep one and get the same picture again")
        self.seed.edited.connect(self._clear_variation_base)
        self._build_variation()
        self._build_input()
        self.steps = spin(1, 500)
        self.cfg = dspin(1, 30, 0.5)
        self.cfg.valueChanged.connect(self._update_negative)
        for box in (self.steps, self.cfg):
            box.setFixedWidth(120)

        self.output_dir = QLineEdit()
        self.output_dir.returnPressed.connect(lambda: self.outputDirEdited.emit(self.output_dir.text()))
        choose = QToolButton(icon=icon("folder"), toolTip="Choose folder…",
                             objectName="folderButton")
        choose.clicked.connect(self._choose_dir)
        self.out_row = QHBoxLayout()
        self.out_row.addWidget(self.output_dir, 1)
        self.out_row.addWidget(choose)

        f = self.main_form = form()
        f.addRow(form_label("Size", "size"), size_field)
        f.addRow(form_label("Aspect", "aspect"), presets)
        self.count.setFixedWidth(120)
        f.addRow(form_label("Images", "num_images"), self.count)
        f.addRow(form_label("Seed", "seed"), self.seed)
        f.addRow(form_label("Steps", "steps"), self.steps)
        f.addRow(form_label("Adherence", "cfg"), self.cfg)

    def _update_negative(self, cfg):
        """At Adherence 1 there is no negative pass, so the negative prompt isn't read."""
        used = cfg != 1
        self.negative.setEnabled(used)
        self.negative.setPlaceholderText("What to avoid" if used else "Not used at Adherence 1")
        self.negative.setToolTip("" if used else "Adherence 1 skips the negative pass, so the negative prompt has no effect")

    def _build_variation(self):
        self.variation_slider = QSlider(Qt.Horizontal)
        self.variation_slider.setRange(0, SLIDER_STEPS)
        self.variation = dspin(0, 1, 0.01)
        self.variation.setFixedWidth(84)
        self.variation_slider.valueChanged.connect(
            lambda v: self._set_variation((v / SLIDER_STEPS) ** 2, from_slider=True))
        self.variation.valueChanged.connect(lambda s: self._set_variation(s, from_spin=True))
        self.variation_row = QHBoxLayout()
        self.variation_row.addWidget(self.variation_slider, 1)
        self.variation_row.addWidget(self.variation)

        self.variation_seed = SeedField("New variations each time; untick to keep one and get the same variations again")
        self.variation_hint = QLabel(self)
        self.variation_hint.setForegroundRole(QPalette.PlaceholderText)
        self.variation_seed.edited.connect(self._update_variation_hint)
        self.variation_seed_row = QHBoxLayout()
        self.variation_seed_row.setSpacing(10)
        self.variation_seed_row.addWidget(self.variation_seed)
        self.variation_seed_row.addWidget(self.variation_hint, 1)
        self._variation_base = ""

        self.variations_toggle = ToggleSwitch()
        self.variations_toggle.toggled.connect(self.set_variations_open)
        self.variations_summary = Summary()
        self.variations_row = toggle_row("Variations", "variations", self.variations_toggle, self.variations_summary)
        vf = form()
        vf.setContentsMargins(0, 6, 0, 0)
        vf.addRow(form_label("Strength", "variation"), self.variation_row)
        vf.addRow(form_label("Variation seed", "variation_seed"), self.variation_seed_row)
        self.variations = QWidget()
        self.variations.setLayout(vf)
        self.variations.setVisible(False)
        self._set_variation(P.DEFAULT_VARIATION)

    def _build_input(self):
        self.input_well = ImageWell()
        self.input_well.changed.connect(self._input_changed)
        self.input_well.activated.connect(self._well_clicked)
        self.input_size = QLabel()
        self.input_size.setForegroundRole(QPalette.PlaceholderText)
        self.input_size.setAlignment(Qt.AlignCenter)
        self.replace_input = QPushButton(icon("photo"), "Replace image…")
        self.replace_input.setToolTip("Choose a different picture to start from")
        self.replace_input.clicked.connect(self.input_well.choose)
        self.remove_input = QPushButton(icon("remove"), "Remove")
        self.remove_input.setToolTip("Take the picture out of this box (the file is not deleted)")
        self.remove_input.clicked.connect(lambda: self.input_well.set_path(""))
        self.match_size = QPushButton("Match image size")
        self.match_size.setToolTip("Make the new picture the same shape and size as this one")
        self.match_size.clicked.connect(self._match_input_size)
        self.describe_input = QPushButton("Describe image…")
        self.describe_input.setToolTip("Write a description of this picture that you can use as a prompt")
        self.describe_input.clicked.connect(
            lambda: self.input_well.path and self.describeRequested.emit(self.input_well.path))
        self.mask_path = ""
        self.paint_mask = QPushButton("Select area to change…")
        self.paint_mask.setToolTip("Paint over the part to redo, or add space around the picture to fill in")
        self.paint_mask.clicked.connect(self.maskRequested)
        self.clear_mask = QPushButton("Clear selection")
        self.clear_mask.setToolTip("Let the whole picture change again")
        self.clear_mask.clicked.connect(lambda: self.set_mask(""))
        self.clear_mask.setVisible(False)
        self.input_strength_slider = QSlider(Qt.Horizontal)
        self.input_strength_slider.setRange(round(I.MIN_CHANGE * 100), 100)
        self.input_strength = dspin(I.MIN_CHANGE, 1, 0.05)
        self.input_strength.setFixedWidth(84)
        self.input_strength_slider.valueChanged.connect(lambda v: self.input_strength.setValue(v / 100))
        self.input_strength.valueChanged.connect(
            lambda s: (self.input_strength_slider.blockSignals(True),
                       self.input_strength_slider.setValue(round(s * 100)),
                       self.input_strength_slider.blockSignals(False)))
        strength_row = QHBoxLayout()
        strength_row.addWidget(self.input_strength_slider, 1)
        strength_row.addWidget(self.input_strength)

        self.how_repaint, self.how_edit = QPushButton("Repaint"), QPushButton("Edit")
        self.how_repaint.setToolTip("Redraw the picture with MOSS-Image from the prompt, changing it as much as Change "
                                    "says; Select area to change keeps the rest")
        self.how_edit.setToolTip("Change the picture as the prompt instructs, with Qwen-Image-Edit: “make it "
                                 "night”, “replace the dog with a cat”, “put the hat from picture 2 on her”")
        how_group = QButtonGroup(self)
        how_row = QHBoxLayout()
        how_row.setSpacing(6)
        for b in (self.how_repaint, self.how_edit):
            b.setCheckable(True)
            b.setProperty("card", True)
            how_group.addButton(b)
            how_row.addWidget(b, 1)
        self.how_repaint.setChecked(True)
        self.how_edit.toggled.connect(lambda _: self._mode_changed())
        self.references = []
        self.reference_row = QHBoxLayout()
        self.reference_row.setSpacing(10)
        self.add_reference = QPushButton(icon("photo"), "Add picture…")
        self.add_reference.setToolTip("Add a picture the instruction can use, called picture 2 (or 3): “put the hat "
                                      "from picture 2 on the cat”")
        self.add_reference.clicked.connect(self._choose_reference)
        reference_box = QVBoxLayout()
        reference_box.setContentsMargins(0, 0, 0, 0)
        reference_box.addLayout(self.reference_row)
        reference_box.addWidget(self.add_reference)
        self.reference_block = QWidget()
        self.reference_block.setLayout(reference_box)
        self._mode_edit = False
        self._stash = {True: {"steps": 30, "cfg": 4.0, "loras": [], "loras_open": False}}

        self.input_toggle = ToggleSwitch()
        self.input_toggle.toggled.connect(self.set_input_open)
        self.input_summary = Summary()
        self.input_row = toggle_row("Start from image", "input_image", self.input_toggle, self.input_summary)
        f = form()
        f.setContentsMargins(0, 6, 0, 0)
        f.addRow(form_label("How", "input_how"), how_row)
        f.addRow(self.input_well)
        f.addRow(self.input_size)
        for pair in ((self.replace_input, self.remove_input), (self.match_size, self.describe_input),
                     (self.paint_mask, self.clear_mask)):
            row = QHBoxLayout()
            for button in pair:
                row.addWidget(button, 1)
            f.addRow(row)
        self.mask_row = row
        f.addRow(form_label("Change", "init_strength"), strength_row)
        self.strength_row = strength_row
        f.addRow(self.reference_block)
        self.input_form = f
        self.input_block = QWidget()
        self.input_block.setLayout(f)
        self.input_block.setVisible(False)
        self.input_strength.setValue(I.sigma_to_change(P.Params().init_strength))
        self._input_changed("")

    def _align_section_switches(self):
        """Section switches in one column: every section title as wide as the widest."""
        titles = self.findChildren(QLabel, "sectionTitle")
        width = max(t.sizeHint().width() for t in titles)
        for t in titles:
            t.setFixedWidth(width)

    def set_input_open(self, open_):
        """Open: repaint or edit the input image; closed: ordinary text-to-image."""
        self.input_toggle.setChecked(open_)
        self.input_block.setVisible(open_)
        self._summarize_input()
        self._mode_changed()

    # Repaint or Edit

    def edit_active(self):
        """Whether Generate edits the picture (Edit chosen under Start from image, and the section on)."""
        return self.input_toggle.isChecked() and self.how_edit.isChecked()

    def edit_picture(self, path):
        """Start an edit of this picture (a card's Edit this picture)."""
        self.input_well.set_path(path)
        self.how_edit.setChecked(True)
        self.set_input_open(True)

    def _mode_changed(self):
        """Repaint and new pictures use MOSS-Image, Edit uses an editing model: each keeps its own steps,
        adherence and LoRAs, swapped in when the mode changes."""
        if not hasattr(self, "lora_rows"):
            return
        edit = self.edit_active()
        if edit != self._mode_edit:
            self._stash[self._mode_edit] = {"steps": self.steps.value(), "cfg": self.cfg.value(),
                                            "loras": [row.item for row in self.lora_rows],
                                            "loras_open": self.loras_toggle.isChecked()}
            self._mode_edit = edit
            kept = self._stash.get(edit)
            if kept:
                self.steps.setValue(kept["steps"])
                self.cfg.setValue(kept["cfg"])
                self.set_lora_entries(kept["loras"])
                self.set_loras_open(kept["loras_open"])
        self._apply_mode()

    def _apply_mode(self):
        edit = self.edit_active()
        self.input_form.setRowVisible(self.strength_row, not edit)
        self.input_form.setRowVisible(self.mask_row, not edit)
        self.reference_block.setVisible(self.how_edit.isChecked())
        self.add_reference.setEnabled(len(self.references) < P.MAX_REFERENCES)
        self.prompt.setPlaceholderText("Describe the change: make it night, replace the dog with a cat, add the word "
                                       "OPEN to the sign" if edit else "Describe the image, or paste a JSON layout")
        if edit and self.use_layout:
            self.set_layout(self.draft, use=False)
        self.layout_button.setEnabled(not edit)
        self.layout_button.setToolTip("Layouts are for new pictures and Repaint" if edit else
                                      "Place text and things in boxes on the picture")
        if edit and self.variations_toggle.isChecked():
            self.set_variations_open(False)
        self.variations_toggle.setEnabled(not edit)
        moss_only = (self.sampler, self.sde_eta, self.shift, self.uncond_layers, self.slg_layers, self.slg_scale,
                     self.slg_start, self.slg_stop, self.max_seq, self.schedule)
        if not hasattr(self, "_moss_tips"):
            self._moss_tips = [w.toolTip() for w in moss_only]
        for w, tip in zip(moss_only, self._moss_tips):
            w.setEnabled(not edit)
            w.setToolTip("Not used by Edit: this is one of MOSS-Image's own settings" if edit else tip)
        self.variations_summary.setText("Not used by Edit" if edit else
                                        "" if self.variations_toggle.isChecked() else "Off")
        self.refresh_models()

    def set_references(self, paths):
        self.references = [p for p in paths if p][:P.MAX_REFERENCES]
        while self.reference_row.count():
            item = self.reference_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, path in enumerate(self.references):
            thumb = ReferenceThumb(path, i + 2)
            thumb.removed.connect(lambda p: self.set_references([q for q in self.references if q != p]))
            self.reference_row.addWidget(thumb)
        self.reference_row.addStretch(1)
        self.add_reference.setEnabled(len(self.references) < P.MAX_REFERENCES)

    def _choose_reference(self):
        start = str(Path(self.input_well.path).parent) if self.input_well.path else str(Path.home() / "Pictures")
        path, _ = QFileDialog.getOpenFileName(self, "Add a picture", start, IMAGE_FILTER)
        if path:
            self.set_references([*self.references, path])

    def _summarize_input(self):
        path = self.input_well.path
        self.input_summary.setText("" if self.input_toggle.isChecked() else
                                   f"Off · {os.path.basename(path)} kept" if path else "Off")

    def set_input_image(self, path):
        self.input_well.set_path(path)
        self.set_input_open(True)

    def set_mask(self, path):
        """Selected area for inpainting/outpainting ('' = none: the whole picture may change)."""
        self.mask_path = path or ""
        self.input_well.set_mask(self.mask_path)
        self.clear_mask.setVisible(bool(self.mask_path))
        self.paint_mask.setText("Edit selection…" if self.mask_path else "Select area to change…")

    def set_input_with_mask(self, image, mask):
        """From the area editor: possibly a new (extended) picture, and its selection; size follows the picture."""
        self.input_well.blockSignals(True)
        self.input_well.set_path(image)
        self.input_well.blockSignals(False)
        self._input_changed(image, keep_mask=True)
        self.set_mask(mask)
        self.set_input_open(True)
        self._match_input_size()

    def _well_clicked(self):
        if self.input_well.path and not self.edit_active():
            self.maskRequested.emit()
        else:
            self.input_well.choose()

    def _input_changed(self, path, keep_mask=False):
        if not keep_mask:
            self.set_mask("")
        for b in (self.match_size, self.describe_input, self.paint_mask, self.remove_input):
            b.setEnabled(bool(path))
        self.replace_input.setText("Replace image…" if path else "Choose image…")
        self.input_size.setText(self._size_text(path))
        self.input_size.setVisible(bool(path))
        self.input_well.setToolTip("Click to select the area to change, or drop a picture here to replace it"
                                   if path else "Click to choose a picture, or drop one here")
        if path and not keep_mask:
            self._match_input_size()

    @staticmethod
    def _size_text(path):
        if not path:
            return ""
        try:
            w, h = I.oriented_size(path)
        except OSError:
            return ""
        return f"{w} × {h} · {w * h / 1e6:.1f} MP"

    def _match_input_size(self):
        if not self.input_well.path:
            return
        try:
            self._set_size(*I.fit_size(*I.oriented_size(self.input_well.path)))
        except OSError:
            pass

    def _input_params(self):
        if self.edit_active():
            return dict(init_image=self.input_well.path, mask_image="",
                        references=json.dumps(self.references, ensure_ascii=False) if self.references else "")
        if not (self.input_toggle.isChecked() and self.input_well.path):
            return dict(init_image="", mask_image="")
        return dict(init_image=self.input_well.path, init_strength=self._sigma(), mask_image=self.mask_path)

    def _sigma(self):
        """σ₀ for the shown Change; an exact σ₀ loaded from settings is kept while the rounded display matches it,
        so Reuse settings reproduces older images exactly."""
        change = self.input_strength.value()
        exact = getattr(self, "loaded_sigma", None)
        if exact is not None and round(I.sigma_to_change(exact), 2) == round(change, 2):
            return exact
        return I.change_to_sigma(change)

    def _set_variation(self, strength, from_slider=False, from_spin=False):
        if not from_spin:
            self.variation.blockSignals(True)
            self.variation.setValue(strength)
            self.variation.blockSignals(False)
        if not from_slider:
            self.variation_slider.blockSignals(True)
            self.variation_slider.setValue(round(math.sqrt(strength) * SLIDER_STEPS))
            self.variation_slider.blockSignals(False)
        self._update_variation_hint()

    def set_variations_open(self, open_):
        """Open shows the variation controls and uses them; closed means no variations."""
        self.variations_toggle.setChecked(open_)
        self.variations.setVisible(open_)
        self.variations_summary.setText("" if open_ else "Off")

    def _update_variation_hint(self):
        self.variation_hint.setText("+ earlier variations" if self._variation_base else "")

    def _clear_variation_base(self):
        self._variation_base = ""
        self._update_variation_hint()

    # LoRAs

    def _build_loras(self):
        self.lora_rows = []
        self.loras_toggle = ToggleSwitch()
        self.loras_toggle.toggled.connect(self.set_loras_open)
        self.loras_summary = Summary()
        self.loras_row = toggle_row("LoRAs", "loras", self.loras_toggle, self.loras_summary)
        self.lora_list = QVBoxLayout()
        self.lora_list.setContentsMargins(0, 0, 0, 0)
        self.lora_list.setSpacing(6)
        add = QPushButton("Choose LoRAs…")
        add.setToolTip("Tick the LoRAs to use; add new ones to your library from Hugging Face or a file")
        add.clicked.connect(self.lorasRequested)
        self.lora_recommended = QPushButton()
        self.lora_recommended.setProperty("card", True)
        self.lora_recommended.setToolTip("Set Steps, Adherence and the schedule to what this LoRA's page recommends")
        self.lora_recommended.clicked.connect(lambda: self.apply_settings(self._lora_settings()[1]))
        self.lora_recommended.setVisible(False)
        block = QVBoxLayout()
        block.setContentsMargins(0, 6, 0, 0)
        block.addLayout(self.lora_list)
        block.addWidget(self.lora_recommended)
        block.addWidget(add)
        self.loras_block = QWidget()
        self.loras_block.setLayout(block)
        self.loras_block.setVisible(False)
        self.highlighter = TriggerHighlighter(self.prompt.document())
        self.prompt.textChanged.connect(self._refresh_triggers)

    def set_loras_open(self, open_):
        """Open uses the listed LoRAs; closed uses none (the list is kept)."""
        self.loras_toggle.setChecked(open_)
        self.loras_block.setVisible(open_)
        names = ", ".join(row.item.get("name") or "unnamed" for row in self.lora_rows)
        self.loras_summary.setText("" if open_ else f"Off · {names} kept" if names else "Off")
        self._refresh_triggers()

    def lora_ids(self):
        return [row.item.get("id") for row in self.lora_rows]

    def set_lora_entries(self, items):
        for row in list(self.lora_rows):
            self._drop_row(row)
        for item in items:
            self._add_row(item)
        self.set_loras_open(bool(items))

    def refresh_loras(self):
        """Pick up name and trigger edits from the library, and LoRAs that went missing."""
        items = []
        for row in self.lora_rows:
            info = R.locate(row.item)
            items.append({**row.item, "name": info.get("name", ""), "trigger": info.get("trigger", "")}
                         if info else row.item)
        open_ = self.loras_toggle.isChecked()
        self.set_lora_entries(items)
        self.set_loras_open(open_)

    def add_lora(self, info):
        item = R.entry(info)
        self._add_row(item)
        if item["trigger"] and item["trigger"] not in self._prompt_text():
            self._insert_trigger(item["trigger"])
        self.set_loras_open(True)

    def remove_lora(self, lora_id):
        for row in list(self.lora_rows):
            if row.item.get("id") == lora_id:
                self._remove_row(row)

    def _add_row(self, item):
        row = LoraRow(item)
        row.changed.connect(self._refresh_triggers)
        row.removed.connect(self._remove_row)
        row.add_trigger.connect(self._insert_trigger)
        self.lora_list.addWidget(row)
        self.lora_rows.append(row)
        self._show_lora_settings()

    def _drop_row(self, row):
        self.lora_rows.remove(row)
        self.lora_list.removeWidget(row)
        row.deleteLater()
        self._show_lora_settings()

    def _lora_settings(self):
        """(name, settings) of the first listed LoRA whose page recommends settings, else ("", {})."""
        for row in self.lora_rows:
            info = R.locate(row.item) or {}
            if info.get("recommended"):
                return info.get("name", ""), info["recommended"]
        return "", {}

    def _show_lora_settings(self):
        name, rec = self._lora_settings()
        self.lora_recommended.setText(f"Use {name}'s settings ({R.settings_text(rec)})" if rec else "")
        self.lora_recommended.setVisible(bool(rec))

    def apply_settings(self, rec):
        """Set Steps, Adherence and the schedule as a model or LoRA recommends (a schedule needs Euler)."""
        self.schedule.setText(", ".join(f"{s:g}" for s in rec.get("sigmas", [])))
        if rec.get("sigmas") and self.sampler.currentText() not in ("Euler", "Euler SDE"):
            self.sampler.setCurrentText("Euler")
        if "steps" in rec and not rec.get("sigmas"):
            self.steps.setValue(rec["steps"])
        if "cfg" in rec:
            self.cfg.setValue(rec["cfg"])
        self._summarize_advanced()

    def _schedule_changed(self, text):
        """A valid schedule fixes the number of steps; Steps follows it and can't be changed while it is set."""
        values = R.schedule(text) if text.strip() else None
        if values:
            self.steps.setValue(len(values))
        self.steps.setEnabled(not values)
        self.steps.setToolTip("Set by the schedule in Advanced options" if values else "")

    def _remove_row(self, row):
        trigger = row.item.get("trigger", "")
        self._drop_row(row)
        if trigger and all(r.item.get("trigger") != trigger for r in self.lora_rows):
            self._take_out_trigger(trigger)
        self._refresh_triggers()

    def _prompt_text(self):
        return self.draft["summary"].get("caption", "") if self.use_layout else self.prompt.toPlainText()

    def _set_prompt_text(self, text):
        """Replace the prompt (or a layout's description) as one undoable edit."""
        if self.use_layout:
            self.draft["summary"]["caption"] = text
            self.set_layout(self.draft)
            return
        cursor = QTextCursor(self.prompt.document())
        cursor.select(QTextCursor.Document)
        cursor.insertText(text)

    def _insert_trigger(self, trigger):
        text = self._prompt_text()
        self._set_prompt_text(f"{trigger}, {text}" if text.strip() else trigger)

    def _take_out_trigger(self, trigger):
        text = self._prompt_text()
        for pattern in (f"{trigger}, ", f", {trigger}", trigger):
            if pattern in text:
                self._set_prompt_text(text.replace(pattern, "", 1).strip())
                return

    def _refresh_triggers(self):
        on = self.loras_toggle.isChecked()
        self.highlighter.set_triggers([r.item.get("trigger", "") for r in self.lora_rows] if on else [])
        text = self._prompt_text()
        for row in self.lora_rows:
            row.show_trigger_missing(text)

    def _loras_params(self):
        if not self.loras_toggle.isChecked():
            return ""
        return R.dumps([row.item for row in self.lora_rows])

    def _build_advanced(self):
        self.advanced_toggle = ToggleSwitch()
        self.advanced_toggle.toggled.connect(self.set_advanced_open)
        self.advanced_summary = Summary()
        self.advanced_row = toggle_row("Advanced options", None, self.advanced_toggle, self.advanced_summary)
        self.advanced = QWidget()

        self.sampler = QComboBox()
        self.sampler.addItems(SAMPLERS)
        self.shift = dspin(0.01, 100, 0.5)
        self.uncond_layers = QLineEdit(placeholderText="none")
        self.slg_layers = QLineEdit(placeholderText="none")
        self.slg_scale = dspin(0, 20, 0.5)
        self.slg_start, self.slg_stop = dspin(0, 1, 0.01), dspin(0, 1, 0.01)
        self.max_seq = spin(1, 4096, 256)
        self.schedule = QLineEdit(placeholderText="the sampler's own")
        self.schedule.setToolTip("A fixed list of noise levels (σ), one per step, as some distilled LoRAs ask for")
        self.schedule.textChanged.connect(self._schedule_changed)
        self._noise_device = P.Params().noise_device
        self.size_step = QComboBox()
        self.size_step.addItems([str(s) for s in S.STEPS])
        self.size_step.setCurrentText(str(S.DEFAULT_STEP))
        self.size_step.activated.connect(lambda i: self.set_size_step(int(self.size_step.itemText(i))))
        self.sde_eta = dspin(0, 1, 0.1)
        reset = QPushButton("Reset advanced")
        reset.clicked.connect(self.reset_advanced)

        interval = QHBoxLayout()
        interval.addWidget(self.slg_start)
        interval.addWidget(separator("–"))
        interval.addWidget(self.slg_stop)

        f = form()
        f.setContentsMargins(0, 0, 0, 0)
        f.addRow(form_label("Output", "output_dir"), self.out_row)
        f.addRow(form_label("Sampler", "sampler"), self.sampler)
        f.addRow(form_label("SDE noise η", "sde_eta"), self.sde_eta)
        f.addRow(form_label("Shift", "shift"), self.shift)
        f.addRow(form_label("Uncond skip", "uncond_skip_layers"), self.uncond_layers)
        f.addRow(form_label("SLG layers", "slg_layers"), self.slg_layers)
        f.addRow(form_label("SLG scale", "slg_scale"), self.slg_scale)
        f.addRow(form_label("Skip interval", "slg_interval"), interval)
        f.addRow(form_label("Max tokens", "max_sequence_length"), self.max_seq)
        f.addRow(form_label("Schedule", "sigmas"), self.schedule)
        f.addRow(form_label("Size step", "size_step"), self.size_step)
        self.think_first = ToggleSwitch()
        think = QHBoxLayout()
        think.setSpacing(10)
        think.addWidget(self.think_first)
        hint = QLabel("(slower, more accurate)")
        hint.setForegroundRole(QPalette.PlaceholderText)
        think.addWidget(hint)
        think.addStretch(1)
        f.addRow(form_label("Think first", "think_first"), think)
        self.low_memory = ToggleSwitch()
        memory = QHBoxLayout()
        memory.setSpacing(10)
        memory.addWidget(self.low_memory)
        memory_hint = QLabel("(on automatically below 48 GB)")
        memory_hint.setForegroundRole(QPalette.PlaceholderText)
        memory.addWidget(memory_hint)
        memory.addStretch(1)
        f.addRow(form_label("Low memory", "low_memory"), memory)
        self.embed_metadata = ToggleSwitch()
        embed = QHBoxLayout()
        embed.setSpacing(10)
        embed.addWidget(self.embed_metadata)
        embed_hint = QLabel("(off: the PNG holds only the picture)")
        embed_hint.setForegroundRole(QPalette.PlaceholderText)
        embed.addWidget(embed_hint)
        embed.addStretch(1)
        f.addRow(form_label("Settings in PNG", "embed_metadata"), embed)
        f.addRow(reset)
        self.advanced.setLayout(f)
        self.advanced_form = f
        self.sampler.currentTextChanged.connect(self._update_sde_row)
        self._update_sde_row()
        self.set_advanced_open(False)

    def set_advanced_open(self, open_):
        self.advanced_toggle.setChecked(open_)
        self.advanced.setVisible(open_)
        self._summarize_advanced()

    def _summarize_advanced(self):
        """Closed, the advanced settings still apply, so say whether any differ from the defaults."""
        if self.advanced_toggle.isChecked() or not hasattr(self, "model_block"):
            self.advanced_summary.setText("")
            return
        names = changed_advanced(self.params())
        self.advanced_summary.setText(f"Changed: {', '.join(names)}" if names else "Defaults")

    def _choose_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", os.path.expanduser(self.output_dir.text()))
        if path:
            self.output_dir.setText(path)
            self.outputDirEdited.emit(path)

    def _snap_size(self):
        self._set_size(*(max(16, round(b.value() / 16) * 16) for b in (self.width_box, self.height_box)))

    def _set_size(self, w, h):
        for box, v in ((self.width_box, w), (self.height_box, h)):
            box.blockSignals(True)
            box.setValue(v)
            box.blockSignals(False)
        self._update_size_info()

    def _update_size_info(self):
        self._sync_presets(self.width_box.value(), self.height_box.value())

    def _fill_presets(self, aspect):
        self.preset.clear()
        for w, h in S.presets(aspect):
            self.preset.addItem(S.label(w, h), f"{w}x{h}")

    def _sync_presets(self, w, h):
        """Both menus always show the current size: its listed aspect, or its ratio rounded to x.xx:1, and its
        megapixels, added to the menu as an extra entry when it isn't one of the presets."""
        custom = self.aspect.findData(CUSTOM)
        if custom >= 0:
            self.aspect.removeItem(custom)
        aspect = S.aspect_of(w, h)
        if aspect is None:
            self.aspect.addItem(S.ratio_label(w, h), CUSTOM)
            self.aspect.setCurrentIndex(self.aspect.count() - 1)
            if (w, h) not in [(sw, sh) for _, sw, sh in S.scaled(*self._scale_base)]:
                self._scale_base = (w, h)            # a new size of its own: the ×1 of the upscaling choices
            self.preset.clear()
            for k, sw, sh in S.scaled(*self._scale_base):
                self.preset.addItem(S.scale_label(k, sw, sh), f"{sw}x{sh}")
        else:
            self.aspect.setCurrentIndex(self.aspect.findText(aspect))
            self._fill_presets(aspect)
        key = f"{w}x{h}"
        if self.preset.findData(key) < 0:
            areas = [int(a) * int(b) for a, b in (self.preset.itemData(i).split("x") for i in range(self.preset.count()))]
            text = S.label(w, h)
            if self.preset.findText(text) >= 0:
                text = f"{text} ({w} × {h})"
            self.preset.insertItem(sum(area < w * h for area in areas), text, key)
        self.preset.setCurrentIndex(self.preset.findData(key))

    def _choose_aspect(self, index):
        """Switch aspect, keeping roughly the current pixel count."""
        if self.aspect.itemData(index) == CUSTOM:
            return
        aspect = self.aspect.itemText(index)
        self._fill_presets(aspect)
        area = self.width_box.value() * self.height_box.value()
        w, h = min(S.presets(aspect), key=lambda s: abs(s[0] * s[1] - area))
        self._set_size(w, h)

    def set_size_step(self, step):
        for box in (self.width_box, self.height_box):
            box.setSingleStep(step)
        self.size_step.setCurrentText(str(step))

    def set_layout(self, draft, use=True):
        """Keep a layout (None: none) and use it as the prompt, or keep it aside for Layout… to bring back.
        Its boxes follow the picture's size. An empty layout (no boxes, no description) counts as none."""
        if draft is not None and L.is_empty(draft):
            draft = None
        self.draft = draft
        self.use_layout = on = use and draft is not None
        for w in (self.prompt, self.prompt_handle, self.prompt_count, self.enhance_button):
            w.setVisible(not on)
        self.layout_summary.setVisible(on)
        self.layout_button.setText("Edit layout…" if on else "Layout…")
        if on:
            self.layout_summary.setText(f"Layout in use: {L.describe(draft)}")
        kept = draft is not None and not on
        self.layout_note.setVisible(kept)
        if kept:
            self.layout_note.setText(f"Layout kept, not in use: {L.describe(draft)}. Layout… brings it back.")
        if hasattr(self, "lora_rows"):
            self._refresh_triggers()

    def layout_draft(self):
        """The current layout at the picture's size, or a new one: from a layout pasted as the prompt, or
        starting from the typed prompt as the description of the whole picture."""
        w, h = self.width_box.value(), self.height_box.value()
        if self.draft is not None:
            return L.scaled(self.draft, w, h)
        text = self.prompt.toPlainText().strip()
        draft = L.from_prompt(text, w, h) if text.startswith("{") else None
        if draft is not None:
            return L.scaled(draft, w, h)
        draft = L.new(w, h)
        draft["summary"]["caption"] = text
        return draft

    def _layout_params(self):
        if not self.use_layout or self.edit_active():
            return dict(prompt=self.prompt.toPlainText(), layout="")
        try:
            prompt = L.compile_prompt(self.draft, self.width_box.value(), self.height_box.value())
        except ValueError:
            prompt = ""                      # validate() says what is missing
        return dict(prompt=prompt, layout=L.dumps(self.draft))

    def params(self):
        return P.Params(
            **self._layout_params(), negative_prompt=self.negative.toPlainText(),
            width=self.width_box.value(), height=self.height_box.value(), steps=self.steps.value(),
            cfg=self.cfg.value(), seed=self.seed.value(), num_images=self.count.value(),
            model=self.current_model(), sampler=self.sampler.currentText(), shift=self.shift.value(),
            uncond_skip_layers=self.uncond_layers.text(), slg_layers=self.slg_layers.text(),
            slg_scale=self.slg_scale.value(), slg_start=self.slg_start.value(), slg_stop=self.slg_stop.value(),
            max_sequence_length=self.max_seq.value(), noise_device=self._noise_device,
            compile_transformer=True, sde_eta=self.sde_eta.value(), sigmas=self.schedule.text().strip(),
            **self._variation_params(), **self._input_params(), loras=self._loras_params(),
        )

    def set_params(self, p):
        edit = P.is_edit(p)
        if p.init_image or edit:
            self.how_edit.blockSignals(True)
            (self.how_edit if edit else self.how_repaint).setChecked(True)
            self.how_edit.blockSignals(False)
        self._mode_edit = edit and bool(p.init_image)      # p's values are this mode's; the other mode keeps its own
        self.set_references(P.references(p))
        if p.layout:
            draft = L.loads(p.layout)
            self.prompt.setPlainText(draft["summary"].get("caption", ""))
            self.set_layout(draft)
        else:
            self.prompt.setPlainText(p.prompt)
            self.set_layout(self.draft, use=False)       # a layout kept aside stays for Layout… to bring back
        self.negative.setPlainText(p.negative_prompt)
        self._set_size(p.width, p.height)
        self.steps.setValue(p.steps)
        self.cfg.setValue(p.cfg)
        self.seed.set_value(p.seed)
        self.count.setValue(p.num_images)
        self.select_model(p.model)
        if p.sampler in SAMPLERS:
            self.sampler.setCurrentText(p.sampler)
        self.shift.setValue(p.shift)
        self.uncond_layers.setText(p.uncond_skip_layers)
        self.slg_layers.setText(p.slg_layers)
        self.slg_scale.setValue(p.slg_scale)
        self.slg_start.setValue(p.slg_start)
        self.slg_stop.setValue(p.slg_stop)
        self.max_seq.setValue(p.max_sequence_length)
        self._noise_device = p.noise_device
        self.sde_eta.setValue(p.sde_eta)
        self.schedule.setText(p.sigmas)
        self._variation_base = p.variation_base
        self.variation_seed.set_value(p.variation_seed)
        if p.variation > 0:
            self._set_variation(p.variation)
        self.set_variations_open(p.variation > 0)
        if p.init_image:
            self.input_well.blockSignals(True)
            self.input_well.set_path(p.init_image)
            self.input_well.blockSignals(False)
            self._input_changed(p.init_image, keep_mask=True)
            self.input_strength.setValue(I.sigma_to_change(p.init_strength))
            self.loaded_sigma = p.init_strength
        self.set_mask(p.mask_image if p.init_image else "")
        self.set_input_open(bool(p.init_image))
        self.set_lora_entries(R.entries(p.loras))
        self._summarize_input()
        self._summarize_advanced()
        self._apply_mode()

    def _variation_params(self):
        if not self.variations_toggle.isChecked() or self.edit_active():
            return dict(variation=0.0, variation_seed=0, variation_base="")
        return dict(variation=self.variation.value(), variation_seed=self.variation_seed.value(),
                    variation_base=self._variation_base)

    # Model

    def _build_model(self):
        self._model_value, self._edit_model = P.DEFAULT_MODEL, P.DEFAULT_EDIT_MODEL
        title = medium(labelled("Model", "model"))
        title.setObjectName("sectionTitle")
        self.model_name = medium(QLabel())
        change = QPushButton("Change…")
        change.setProperty("card", True)
        change.setToolTip("Pick another model; add new ones to your library from Hugging Face or this Mac")
        change.clicked.connect(self.modelsRequested)
        self.model_row = QHBoxLayout()
        self.model_row.addWidget(title)
        self.model_row.addSpacing(10)
        self.model_row.addWidget(self.model_name, 1)
        self.model_row.addWidget(change)
        self.model_facts = QLabel()
        self.model_facts.setForegroundRole(QPalette.PlaceholderText)
        self.model_facts.setWordWrap(True)
        self.use_recommended = QPushButton()
        self.use_recommended.setProperty("card", True)
        self.use_recommended.setToolTip("Set Steps and Adherence to what this model's page recommends")
        self.use_recommended.clicked.connect(self._apply_recommended)
        block = QVBoxLayout()
        block.setContentsMargins(0, 4, 0, 0)
        block.setSpacing(6)
        block.addWidget(self.model_facts)
        block.addWidget(self.use_recommended)
        self.model_block = QWidget()
        self.model_block.setLayout(block)
        self.select_model(P.DEFAULT_MODEL)

    def current_model(self):
        """The model Generate uses: the editing model while Edit is on, else the generation model."""
        return self._edit_model if self.edit_active() else self._model_value

    def generation_model(self):
        return self._model_value

    def select_model(self, value):
        """Choose a model for its family: an editing model for Edit, any other for new pictures and Repaint."""
        if M.family_of(value) == "qwen-image":
            self._edit_model = value
        else:
            self._model_value = value
        self._show_model()

    def _show_model(self):
        value = self.current_model()
        self.model_name.setText(M.display_name(value))
        info = M.find(M.library_id(value)) if M.is_library(value) else None
        if info:
            facts = f"Trained on {info.get('trained_on') or 'a model not stated'}"
        elif M.is_library(value):
            facts = "Not in your model library any more: choose another"
        else:
            facts = {"MOSS-Image-SFT": "The polished original model", "MOSS-Image-Base": "The raw original model, "
                     "the one people train their own versions from",
                     "Qwen-Image-Edit-2511": "Qwen's editing model: changes a picture as the prompt says, with up "
                     "to two extra pictures"}.get(M.display_name(value), "")
        self.model_facts.setText(facts)
        self._show_recommended()

    def refresh_models(self):
        if hasattr(self, "model_name"):
            self._show_model()

    def _recommended(self):
        value = self.current_model()
        info = M.find(M.library_id(value)) if M.is_library(value) else None
        return (info or {}).get("recommended") or {}

    def _show_recommended(self):
        rec = self._recommended()
        self.use_recommended.setText(f"Use its settings ({R.settings_text(rec)})" if rec else "")
        self.use_recommended.setVisible(bool(rec))

    def _apply_recommended(self):
        self.apply_settings(self._recommended())

    def _update_sde_row(self, *_):
        self.advanced_form.setRowVisible(self.sde_eta, self.sampler.currentText() == "Euler SDE")

    def reset_advanced(self):
        d = P.Params()
        self.set_params(replace(self.params(), **{k: getattr(d, k) for k in P.ADVANCED}))
