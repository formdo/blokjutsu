---
title: Install and Uninstall
nav_order: 2
---

# Install and Uninstall

## Download

[Download for Mac](https://github.com/formdo/blokjutsu/releases/download/v1.0.0rc2/Blokjutsu-1.0.0rc2.dmg){: .btn .btn-primary }

Blokjutsu 1.0.0rc2, 375 MB, for Macs with Apple silicon (M1 or later).

1. Open the downloaded `Blokjutsu-1.0.0rc2.dmg`. A window opens with Blokjutsu and your Applications folder.
2. Drag **Blokjutsu** onto **Applications**.
3. Eject the disk image (in the Finder sidebar), and move it to the Trash if you like.
4. Open Blokjutsu from Applications, Launchpad, or Spotlight. The first time, macOS says it was downloaded from
   the internet and asks whether to open it; click **Open**. Apple has checked it, so this is the only question.

Blokjutsu then asks before downloading the model (see [below](#the-model-download)).

## The installer

The installer does the same from Terminal, without a disk image.

1. Open **Terminal** (in Applications → Utilities, or press ⌘-Space and type *Terminal*).
2. Paste this line and press Return:

   ```sh
   curl -LsSf https://formdo.github.io/blokjutsu/install.sh | sh
   ```

3. Wait a few minutes. The installer downloads about 2 GB and prints four steps.
4. Blokjutsu opens by itself when it's done. Next time, open it from Applications, Launchpad, or Spotlight.

The installer puts everything in two places and changes nothing else:

| what | where |
|---|---|
| the app | `~/Applications/Blokjutsu.app` |
| Python and the libraries Blokjutsu uses | `~/Library/Application Support/Blokjutsu.noindex/` |

It does not ask for your password, edit your Terminal settings, or install anything system-wide.
[Read the installer](install.sh) before running it if you like; it is short.

## The model download

The first time Blokjutsu opens, it asks before downloading the MOSS-Image model: about 30 GB from
[Hugging Face](https://huggingface.co), a site that hosts open AI models. The dialog says exactly what is fetched and what is sent. Click **Download**, or **Not now** to
do it later from **File → Download Model…**.

![The download dialog: what is downloaded (MOSS-Image-SFT with its text encoder and image decoder), its size, where it comes from, where it is saved, and what is sent, with Not now and Download buttons](assets/screenshots/download.webp){: width="520" }

The download takes a while on a typical home connection. You can cancel it; when you start again it carries on
where it left off. The model is stored in Blokjutsu's own folder, which is kept out of Time Machine backups and
Spotlight ([why, and how to change it](local.md#backups-and-spotlight)).

[Describe image and Enhance prompt](controls.md#describe-image-and-enhance-prompt) need one more, smaller
download (2 GB), offered the first time you use them.

## Updating

Run the installer line again. Your pictures and settings are kept. Each Blokjutsu release uses the model version
it was tested with and fetches a newer one only if that release moves to it.

## If you already use Python

`pip install blokjutsu` works in any Python 3.10+ environment; run it with `blokjutsu`. See
[For developers](developers.md).

## Uninstalling

In Terminal:

```sh
curl -LsSf https://formdo.github.io/blokjutsu/install.sh | sh -s -- --uninstall
```

This removes the app and the Python it runs on but **keeps your pictures, your settings, and the model**. If you
installed from the disk image, drag Blokjutsu from Applications to the Trash instead; that removes the app, Python
included, and also keeps your pictures, your settings, and the model.

The model takes about 30 GB. To remove it as well, with everything else Blokjutsu keeps:

1. In Finder, choose **Go → Go to Folder…**, type `~/Library/Application Support`, and press Return.
2. Move the folder `Blokjutsu.noindex` to the Trash, and empty the Trash.

That folder also holds the pictures in the default Output folder, so move any you want to keep first. Pictures in
an Output folder you chose yourself are not in it.
