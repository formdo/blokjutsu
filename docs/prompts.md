---
title: Writing prompts
parent: Making images
nav_order: 1
---

# Writing prompts

MOSS-Image was trained on long, careful descriptions of pictures. It does best when you write like that too.

## Describe, don't command

Say what is in the picture, where, and how it looks: subject, setting, composition, colors, light, and style.

| instead of | try |
|---|---|
| a cat | A ginger cat asleep on a windowsill, curled in a patch of afternoon sun, potted herbs beside it, soft focus background, warm film photograph |
| poster for a jazz night | A 1950s-style jazz poster: a silhouetted saxophonist in deep blue on a mustard background, the title "BLUE NOTE NIGHT" in large white letters at the top, "Friday 9 pm" in small letters at the bottom |

English works best; other languages, Chinese in particular, also work.

## Text in pictures

MOSS-Image is unusually good at writing. Put the exact words in quotation marks and say where they go. To
control line breaks, start new lines in the prompt itself:

```text
A handwritten note on a fridge door:
"Milk
Eggs
Bread"
```

## Negative prompt

**Negative prompt** lists what you don't want. MOSS-Image's authors suggest:

```text
worst quality, bad anatomy, watermark, jpeg artifact
```

Leave it empty if you don't need it.

## Tags

Short comma-separated tags also work, for example `best quality, watercolor, lighthouse, stormy sea, gulls`.
Put quality words first and subject words last.

## Layouts

To say where things go, use a [layout](layouts.md): boxes drawn on the picture, each with a description and, for
text, the exact words.

## Let the model help

- **Enhance prompt** (above the prompt box) rewrites your prompt in three lengths. Pick one with
  **Use as prompt**; ⌘Z brings your own prompt back.
- **Describe image** writes a description of any picture, a good starting prompt for something similar. See
  [Describing images](describing.md).

The character count beside each box is just for reference; MOSS-Image reads up to about 4,000 tokens (roughly
15,000 characters). The limit can be lowered with **Max tokens** in Advanced options.
