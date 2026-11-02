"""Describe Image: caption an image with MOSS's own text encoder (Qwen3.5-9B, a vision-language model).

The MOSS checkpoint ships the encoder without its output layer; fetch.py downloads lm_head.weight from the
Qwen checkpoint whose weights are verified identical, and this module re-attaches it to the loaded encoder.
PROMPT is adapted from MOSS's recaptioning prompt (USERGUIDE.md, Image Captioning; Apache-2.0): the reference
caption and the watermark boxes and borders fields are removed, and watermarks are listed by text only.
Enhance Prompt asks the same model to expand a short request into captions of the same three lengths, the
kind of detailed prompt with which the technical report's renderer scored best.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import logging

from .fetch import HEAD, HEAD_FILE, SOURCE_FILE
from .settings import app_home

log = logging.getLogger(__name__)
MAX_PIXELS = 1024 * 1024
MAX_TOKENS = {False: 1536, True: 8192}
SAMPLING = {False: dict(temperature=0.7, top_p=0.8, top_k=20),     # Qwen's non-thinking recommendation
            True: dict(temperature=1.0, top_p=0.95)}                # MOSS's captioning settings

PROMPT = """You are an image recaptioner. Return exactly one JSON object with this schema:
{
  "caption": {
    "long": "a detailed image description, including all non-watermark visible text",
    "medium": "a one-paragraph image description",
    "short": "a one-sentence image description"
  },
  "watermark": ["watermark text"]
}

Rules:
- caption.long:
    - Describe the composition, key subjects, actions, setting, colors, lighting, and artistic style in detail. Include only information visible in the image.
    - Preserve visible text exactly, excluding watermarks. Do not translate, paraphrase, romanize, or normalize image text.
    - Describe text layout as much as possible: line breaks, ordering, relative position, alignment, size hierarchy, font/style, color, spacing, and how text blocks are arranged.
- caption.medium: compress long into one paragraph.
- caption.short: summarize the main subject, action, or relationship in one sentence.
- Do not describe watermarks in any caption field. Record them only in watermark.
- watermark: the visible text of each watermark, or a short description if unreadable. Use [] if there are none.
- All three caption fields must be non-empty strings.
- Return only the JSON object, without Markdown or explanations."""


ENHANCE = """You write prompts for a text-to-image model that was trained on detailed image captions. Expand the user's image request below into image descriptions. Return exactly one JSON object with this schema:
{
  "caption": {
    "long": "a detailed image description",
    "medium": "a one-paragraph image description",
    "short": "a one-sentence image description"
  }
}

Rules:
- Keep every element of the request, including its subject, setting, mood and style. Do not contradict it.
- Add concrete, plausible visual detail consistent with the request: composition and viewpoint, key subjects and their appearance, actions, setting, colors, lighting, and artistic or photographic style.
- Reproduce any text the request asks to appear in the image exactly, in quotation marks, with its placement.
- Describe only what would be visible; no story, sounds, smells or intentions.
- caption.long: a detailed description. caption.medium: compress long into one paragraph. caption.short: one sentence.
- All three caption fields must be non-empty strings.
- Return only the JSON object, without Markdown or explanations.

The user's image request:
"""


def caption_dir():
    return app_home() / "caption"


def head_ready(folder=None):
    folder = Path(folder or caption_dir())
    return (folder / HEAD_FILE).is_file() and (folder / SOURCE_FILE).is_file()


def prepare_image(path):
    """Upright RGB, at most MAX_PIXELS (bounds the number of vision tokens)."""
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    scale = min(1.0, (MAX_PIXELS / (image.width * image.height)) ** 0.5)
    if scale < 1:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    return image


def watermarks(reply):
    """Watermark texts from a reply's "watermark" list (strings, or MOSS's {"label": …} objects)."""
    items = reply.get("watermark") or []
    labels = [item.get("label", "") if isinstance(item, dict) else item for item in items if item]
    return [str(label).strip() for label in labels if str(label).strip()]


def parse(text):
    """{'short', 'medium', 'long', 'watermarks'} from the model's reply; tolerant of thinking text and prose."""
    text = text.split("</think>")[-1].strip()
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            reply = json.loads(match.group(0))
            caption = reply.get("caption", {})
            found = {k: str(caption.get(k, "")).strip() for k in ("short", "medium", "long")}
            if any(found.values()):
                filled = {k: v or found["medium"] or found["long"] or found["short"] for k, v in found.items()}
                return {**filled, "watermarks": watermarks(reply)}
        except (ValueError, AttributeError):
            pass
    return {"short": text, "medium": text, "long": text, "watermarks": []}


def complete_json(text, thinking):
    """Whether the reply already holds a whole JSON object (after the thinking, if any): stop generating there,
    rather than relying on the model to emit its end token."""
    if thinking and "</think>" not in text:
        return False
    body = text.split("</think>")[-1]
    start = body.find("{")
    if start < 0:
        return False
    depth, in_string, escaped = 0, False, False
    for i, ch in enumerate(body[start:], start):
        if in_string:
            escaped, in_string = (False, in_string) if escaped else (ch == "\\", ch != '"')
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    json.loads(body[start:i + 1])
                    return True
                except ValueError:
                    return False
    return False


def load_head(device, dtype, folder=None):
    import torch
    from safetensors.torch import load_file

    weight = load_file(str(Path(folder or caption_dir()) / HEAD_FILE))[HEAD]
    head = torch.nn.Linear(weight.shape[1], weight.shape[0], bias=False, device="meta")
    head.weight = torch.nn.Parameter(weight.to(device=device, dtype=dtype), requires_grad=False)
    return head


def generator(encoder, head):
    """A Qwen3.5 ForConditionalGeneration sharing the loaded encoder's weights (no copy, no extra memory)."""
    import torch
    import transformers

    cls = getattr(transformers, type(encoder).__name__.replace("Model", "ForConditionalGeneration"))
    with torch.device("meta"):
        model = cls(encoder.config)
    model.model = encoder
    model.lm_head = head
    folder = caption_dir()
    if (folder / "generation_config.json").is_file():
        model.generation_config = transformers.GenerationConfig.from_pretrained(folder)
    return model.eval()


def chat_inputs(processor, image, text, thinking):
    content = ([{"type": "image", "image": image}] if image is not None else []) + [{"type": "text", "text": text}]
    messages = [{"role": "user", "content": content}]
    kwargs = dict(tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt")
    try:
        return processor.apply_chat_template(messages, enable_thinking=thinking, **kwargs)
    except TypeError:
        return processor.apply_chat_template(messages, **kwargs)


def describe(encoder, path, thinking, on_token, cancelled, request=None):
    """Captions {'short', 'medium', 'long'} of the image at `path`, or, given `request` instead, of an imagined
    image expanding that prompt. on_token(n, limit) after each generated token; cancelled() stops."""
    import torch
    import transformers

    from .backend import Cancelled

    import importlib.util
    if importlib.util.find_spec("torchvision") is None:     # Qwen's processor needs it, even for still images
        raise RuntimeError("Describing and enhancing need torchvision. In the app's Python environment run: "
                           "pip install \"torch==$(python -c 'import torch; print(torch.__version__)')\" torchvision")
    device, dtype = next(encoder.parameters()).device, next(encoder.parameters()).dtype
    processor = transformers.AutoProcessor.from_pretrained(caption_dir())
    model = generator(encoder, load_head(device, dtype))
    limit = MAX_TOKENS[thinking]
    count, start = [0], [0]

    class Watch(transformers.StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs):
            count[0] += 1
            on_token(count[0], limit)
            if cancelled():
                return True
            if count[0] % 8:
                return False
            text = processor.tokenizer.decode(input_ids[0, start[0]:], skip_special_tokens=True)
            return complete_json(text, thinking)

    try:
        if request is None:
            inputs = chat_inputs(processor, prepare_image(path), PROMPT, thinking)
        else:
            inputs = chat_inputs(processor, None, ENHANCE + request.strip(), thinking)
        inputs = inputs.to(device)
        start[0] = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=limit, do_sample=True, **SAMPLING[thinking],
                                 stopping_criteria=transformers.StoppingCriteriaList([Watch()]))
        if cancelled():
            raise Cancelled
        reply = processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        log.info("%s reply (%d tokens): %s", "Enhance" if request is not None else "Describe", count[0],
                 reply[-4000:])
        return parse(reply)
    finally:
        model.lm_head = model.model = None     # free the 2 GB head; the encoder stays with the pipeline
