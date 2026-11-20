"""One-line explanations shown when a control's label is clicked. Technical detail lives in docs/controls.md."""

HELP = {
    "prompt": "Describe the picture you want, in words, tags, or a JSON layout.",
    "negative_prompt": "Things you want kept out of the picture.",
    "size": "Picture size in pixels; the rotate button switches between portrait and landscape.",
    "aspect": "Pick a shape and a size; the width and height update to match.",
    "num_images": "How many pictures to make with these settings.",
    "seed": "Start number for the randomness; reuse it to get the same picture again. Random picks a new one each time.",
    "input_image": "Start from a picture of your own: repaint it from the prompt, or edit it as the prompt instructs.",
    "input_how": "Repaint: MOSS-Image redraws the picture from the prompt, as much as Change says. Edit: an editing "
                 "model changes it as the prompt instructs (\"make it night\"), keeping the rest.",
    "init_strength": "How much the picture may change: low keeps your picture, high reinvents it.",
    "variations": "Make small variations of a picture instead of entirely new ones.",
    "variation": "How different each variation is from the original picture.",
    "model_name": "The model's name, as shown under Model and on each picture's card.",
    "lora_name": "The LoRA's name, as shown in the controls and on each picture's card.",
    "lora_trigger": "The word the LoRA was trained to respond to. It is put at the start of the prompt when you "
                    "add the LoRA to a picture. Leave it empty if the LoRA has none: it then applies to the "
                    "whole picture.",
    "lora_strength": "The strength the LoRA starts at when you add it to a picture: 1 is as it was trained.",
    "lora_settings": "Steps, adherence and schedule this LoRA needs, as on its page (\"4 steps, adherence 1\"); "
                     "Use its settings under LoRAs applies them. Fast (distilled) LoRAs need theirs.",
    "model_settings": "Steps and adherence this model needs, as on its page (\"8 steps, adherence 1\"); "
                      "Use its settings under Model applies them.",
    "sigmas": "A fixed list of noise levels, one per step, that some fast LoRAs are trained for; leave empty for the "
              "sampler's own. While it is set, Steps follows it.",
    "loras": "Add styles or subjects the model was taught separately (LoRAs); each has a strength.",
    "variation_seed": "Which variations you get; Random picks new ones every time.",
    "steps": "More steps give more polish but take longer.",
    "cfg": "How strictly the picture follows the prompt; higher is more literal. At 1 it is twice as fast and the negative prompt isn't used.",
    "output_dir": "Folder where pictures and their settings are saved.",
    "model": "Which model makes the picture: SFT is the polished one, Base is for training your own, and "
             "Change… also lists the models in your library.",
    "sampler": "The method used to turn noise into a picture; Euler is the recommended default.",
    "sde_eta": "How much fresh randomness Euler SDE adds at each step.",
    "shift": "Balances effort between overall layout (higher) and fine detail (lower).",
    "uncond_skip_layers": "A built-in quality boost; leave at 22 unless experimenting.",
    "slg_layers": "Optional extra quality guidance; slower, off when empty.",
    "slg_scale": "Strength of that extra guidance (off at 0).",
    "slg_interval": "Which part of the generation the quality guidance applies to.",
    "think_first": "Describe image and Enhance prompt plan before writing: slower, but more accurate.",
    "embed_metadata": "Also write the prompt and settings inside each PNG file, so they travel with the picture.",
    "size_step": "How much the size arrows change width and height.",
    "max_sequence_length": "Longest prompt the model will read; longer prompts are cut off.",
    "live_preview": "Show a rough preview while each picture is being made.",
    "low_memory": "Set the 17 GB text encoder aside after reading each prompt; a short pause when the prompt changes.",
    "image_cache": "Memory used to keep history pictures ready for instant scrolling.",
    "app_data": "Folder with the app's settings, logs and (by default) your pictures.",
}
