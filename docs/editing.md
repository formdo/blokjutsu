---
title: Editing pictures
parent: Making images
nav_order: 4.5
---

# Editing pictures

**Edit** changes a picture the way you tell it to: "make it night", "replace the dog with a cat", "add the word
OPEN to the sign above the door", "put the hat from picture 2 on her". It keeps the rest of the picture as it was.
Edits are made with Qwen's editing model, Qwen-Image-Edit-2511 (Apache 2.0), which runs locally like MOSS-Image.

## Making an edit

1. Switch on **Start from image** and choose the picture, or click **Edit this picture** on one of your
   pictures.
2. Under **How**, choose **Edit**. (**Repaint** is the other way of working from a picture: MOSS-Image redraws it
   from the prompt; see [Working from a picture](from-a-picture.md).)
3. Write the change as the prompt, as an instruction. Say what to change and, if it helps, what to keep:
   "change the jacket to red leather; keep her face and pose".
4. Click **Generate**.

The first time, Blokjutsu offers to download the editing model (about 58 GB). As with new pictures, the card
shows the edit taking shape as the steps go by.

Edit redraws the whole picture, so even what you didn't ask to change can shift a little; faces especially.
Saying what to keep helps: "sharpen this photo; keep every face exactly as it is".

## Using more than one picture

**Add picture…** adds up to two more pictures, shown as **Picture 2** and **Picture 3**. The picture being edited
is picture 1. Refer to them by number in the instruction: "the woman from picture 1 wearing the dress from picture
2", "put the cat from picture 1 on the sofa from picture 3". These are the names the model itself uses: it is shown
the pictures labelled "Picture 1:", "Picture 2:" and so on.

## Settings

These work as for new pictures:

- **Size**: the edited picture's size, any multiple of 16. It starts at the size of the picture you chose, but can
  be different: larger, smaller, or another shape, which the model recomposes for. Qwen's model does best near
  1 megapixel; much larger takes longer and isn't sharper.
- **Images**: several edits at once, each from its own seed.
- **Seed**, **Steps**, **Adherence** and the **negative prompt** (used when Adherence is above 1).

Under **Advanced options**, the sampler, shift, skip-layer and schedule settings are MOSS-Image's own: they are
greyed out while Edit is chosen.

Edit keeps its own Steps,
Adherence and LoRAs: switching between Repaint and Edit swaps them, so a fast editing LoRA's settings don't carry
over to MOSS-Image. Qwen recommends 40 steps at Adherence 4; 30 steps is usually enough, and is where Edit starts.
At Adherence 1 each step runs the model once instead of twice, the negative prompt isn't used, and the result
follows the instruction less closely, unless a fast LoRA made for that setting is on.

**Change**, **Select area to change**, layouts and Variations are for Repaint and new pictures, so they are hidden
or switched off while Edit is chosen.

## Fast editing LoRAs

LoRAs made for Qwen-Image-Edit-2511 can be added to your LoRA library as usual; Blokjutsu files them under the
editing model, and **Choose LoRAs…** shows them while Edit is chosen. Lightning LoRAs (such as
`lightx2v/Qwen-Image-Edit-2511-Lightning`) make an edit in 4 steps at Adherence 1, many times faster; type their
settings, `4 steps, adherence 1`, as the LoRA's **Settings** if its page doesn't give them, then use **Use its
settings**. See [Fast LoRAs](loras.md#fast-loras-and-their-settings).

## Speed and memory

An edit reads the original picture as well as making the new one, so it costs more than a new picture of the same
size: at 30 steps and Adherence 4, a 1280 × 1088 edit takes about 12 minutes on a Mac Studio (M3 Ultra), and a
fraction of that with a 4-step LoRA. The first edit after starting Blokjutsu also loads the model, which takes a
while before the first step. Editing and generating use different models (about 58 GB and 30 GB). On Macs with about
128 GB of memory or more both stay loaded, so switching between them costs nothing; with less, or with **Low
memory** on, Blokjutsu sets one aside to load the other, which takes a little while each time you switch.

Each edit records its instruction, the pictures it used and its settings; **Reuse settings** puts them back.
