"""Left-hand control panel: prompt, main parameters, output folder, collapsible advanced section."""
from __future__ import annotations

import math
import os
from dataclasses import replace

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QPalette, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLabel, QSlider, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from .. import layout as L
from .. import params as P
from .. import img2img as I
from .. import sizes as S
from ..samplers import SAMPLERS
from .icons import RED, icon
from .theme import CONTROL_HEIGHT, MARGIN, enlarge, medium
from .image_input import ImageWell
from .resize_handle import ResizeHandle
from .toggle import ToggleSwitch
from .widgets import labelled


PROMPT_HEIGHT, NEGATIVE_HEIGHT = 96, 56
SLIDER_STEPS = 1000        # variation strength = (position / SLIDER_STEPS)²


def indented(label, pixels=3):
    """Nudge a caption right so it lines up optically with the rounded box below it."""
    label.setContentsMargins(pixels, 0, 0, 0)
    return label


def toggle_row(text, help_key, switch):
    """Section header: medium-weight title (clickable help if help_key) followed by its on/off switch."""
    row = QHBoxLayout()
    title = medium(labelled(text, help_key) if help_key else QLabel(text))
    title.setObjectName("sectionTitle")
    row.addWidget(title)
    row.addSpacing(10)
    row.addWidget(switch)
    row.addStretch(1)
    return row


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
    deleteHistoryRequested = Signal()
    outputDirEdited = Signal(str)
    describeRequested = Signal(str)          # image path
    enhanceRequested = Signal(str)           # prompt text
    maskRequested = Signal()
    layoutRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_prompts()
        self._build_main()
        self._build_advanced()
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
        layout.addLayout(self.advanced_row)
        layout.addWidget(self.advanced)
        layout.addStretch(1)
        layout.addSpacing(16)
        layout.addWidget(self.delete_button)
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
        self.enhance_button = QPushButton("Enhance prompt")
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
        self.delete_button = QPushButton(icon("trash", RED), "Delete all history…",
                                         objectName="destructive")
        self.delete_button.clicked.connect(self.deleteHistoryRequested)

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
        self.seed = QLineEdit()
        self.seed.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}")))
        self.seed.setPlaceholderText("0")
        self.seed_hint = QLabel("(new random seed)", self)
        self.seed_hint.setForegroundRole(QPalette.PlaceholderText)
        self.seed.textChanged.connect(lambda text: self.seed_hint.setVisible(int(text or 0) == 0))
        self.seed.textEdited.connect(lambda _: self._clear_variation_base())
        self._build_variation()
        self._build_input()
        self.steps = spin(1, 500)
        self.cfg = dspin(0, 30, 0.5)
        for box in (self.steps, self.cfg):
            box.setFixedWidth(120)

        self.output_dir = QLineEdit()
        self.output_dir.returnPressed.connect(lambda: self.outputDirEdited.emit(self.output_dir.text()))
        choose = QToolButton(icon=icon("folder"), toolTip="Choose folder…",
                             objectName="folderButton")
        choose.clicked.connect(self._choose_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_dir, 1)
        out_row.addWidget(choose)

        f = self.main_form = form()
        f.addRow(form_label("Size", "size"), size_field)
        f.addRow(form_label("Aspect", "aspect"), presets)
        self.count.setFixedWidth(120)
        self.seed.setFixedWidth(120)
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.seed)
        seed_row.addWidget(self.seed_hint, 1)
        f.addRow(form_label("Images", "num_images"), self.count)
        f.addRow(form_label("Seed", "seed"), seed_row)
        f.addRow(form_label("Steps", "steps"), self.steps)
        f.addRow(form_label("Adherence", "cfg"), self.cfg)
        f.addRow(form_label("Output", "output_dir"), out_row)

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

        self.variation_seed = QLineEdit()
        self.variation_seed.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,10}")))
        self.variation_seed.setPlaceholderText("0")
        self.variation_seed.setFixedWidth(120)
        self.variation_hint = QLabel(self)
        self.variation_hint.setForegroundRole(QPalette.PlaceholderText)
        self.variation_seed.textChanged.connect(lambda _: self._update_variation_hint())
        self.variation_seed_row = QHBoxLayout()
        self.variation_seed_row.addWidget(self.variation_seed)
        self.variation_seed_row.addWidget(self.variation_hint, 1)
        self._variation_base = ""

        self.variations_toggle = ToggleSwitch()
        self.variations_toggle.toggled.connect(self.set_variations_open)
        self.variations_row = toggle_row("Variations", "variations", self.variations_toggle)
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
        self.describe_input = QPushButton("Describe image")
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

        self.input_toggle = ToggleSwitch()
        self.input_toggle.toggled.connect(self.set_input_open)
        self.input_row = toggle_row("Start from image", "input_image", self.input_toggle)
        f = form()
        f.setContentsMargins(0, 6, 0, 0)
        f.addRow(self.input_well)
        f.addRow(self.input_size)
        for pair in ((self.replace_input, self.remove_input), (self.match_size, self.describe_input),
                     (self.paint_mask, self.clear_mask)):
            row = QHBoxLayout()
            for button in pair:
                row.addWidget(button, 1)
            f.addRow(row)
        f.addRow(form_label("Change", "init_strength"), strength_row)
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
        """Open: generate from the input image; closed: ordinary text-to-image."""
        self.input_toggle.setChecked(open_)
        self.input_block.setVisible(open_)

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
        if self.input_well.path:
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

    def _update_variation_hint(self):
        text = "(new variations each time)" if int(self.variation_seed.text() or 0) == 0 else ""
        if self._variation_base:
            text = (text + " " if text else "") + "+ earlier variations"
        self.variation_hint.setText(text)

    def _clear_variation_base(self):
        self._variation_base = ""
        self._update_variation_hint()

    def _build_advanced(self):
        self.advanced_toggle = ToggleSwitch()
        self.advanced_toggle.toggled.connect(self.set_advanced_open)
        self.advanced_row = toggle_row("Advanced options", None, self.advanced_toggle)
        self.advanced = QWidget()

        self.model = QComboBox(editable=True)
        self.model.addItems(P.MODELS.values())
        self.model.setToolTip("Hugging Face repo id or local model folder")
        self.sampler = QComboBox()
        self.sampler.addItems(SAMPLERS)
        self.shift = dspin(0.01, 100, 0.5)
        self.uncond_layers = QLineEdit(placeholderText="none")
        self.slg_layers = QLineEdit(placeholderText="none")
        self.slg_scale = dspin(0, 20, 0.5)
        self.slg_start, self.slg_stop = dspin(0, 1, 0.01), dspin(0, 1, 0.01)
        self.max_seq = spin(1, 4096, 256)
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
        f.addRow(form_label("Model", "model"), self.model)
        f.addRow(form_label("Sampler", "sampler"), self.sampler)
        f.addRow(form_label("SDE noise η", "sde_eta"), self.sde_eta)
        f.addRow(form_label("Shift", "shift"), self.shift)
        f.addRow(form_label("Uncond skip", "uncond_skip_layers"), self.uncond_layers)
        f.addRow(form_label("SLG layers", "slg_layers"), self.slg_layers)
        f.addRow(form_label("SLG scale", "slg_scale"), self.slg_scale)
        f.addRow(form_label("Skip interval", "slg_interval"), interval)
        f.addRow(form_label("Max tokens", "max_sequence_length"), self.max_seq)
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
            self.preset.insertItem(sum(area < w * h for area in areas), S.label(w, h), key)
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
        Its boxes follow the picture's size."""
        self.draft = draft
        self.use_layout = on = use and draft is not None
        for w in (self.prompt, self.prompt_handle, self.prompt_count, self.enhance_button):
            w.setVisible(not on)
        self.layout_summary.setVisible(on)
        self.layout_button.setText("Edit layout…" if on else "Layout…")
        if on:
            self.layout_summary.setText(L.describe(draft))

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
        if not self.use_layout:
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
            cfg=self.cfg.value(), seed=int(self.seed.text() or 0), num_images=self.count.value(),
            model=self.model.currentText().strip(), sampler=self.sampler.currentText(), shift=self.shift.value(),
            uncond_skip_layers=self.uncond_layers.text(), slg_layers=self.slg_layers.text(),
            slg_scale=self.slg_scale.value(), slg_start=self.slg_start.value(), slg_stop=self.slg_stop.value(),
            max_sequence_length=self.max_seq.value(), noise_device=self._noise_device,
            compile_transformer=True, sde_eta=self.sde_eta.value(),
            **self._variation_params(), **self._input_params(),
        )

    def set_params(self, p):
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
        self.seed.setText(str(p.seed))
        self.count.setValue(p.num_images)
        self.model.setCurrentText(p.model)
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
        self._variation_base = p.variation_base
        self.variation_seed.setText(str(p.variation_seed))
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

    def _variation_params(self):
        if not self.variations_toggle.isChecked():
            return dict(variation=0.0, variation_seed=0, variation_base="")
        return dict(variation=self.variation.value(), variation_seed=int(self.variation_seed.text() or 0),
                    variation_base=self._variation_base)

    def _update_sde_row(self, *_):
        self.advanced_form.setRowVisible(self.sde_eta, self.sampler.currentText() == "Euler SDE")

    def reset_advanced(self):
        d = P.Params()
        self.set_params(replace(self.params(), **{k: getattr(d, k) for k in P.ADVANCED}))
