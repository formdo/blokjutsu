---
title: Menus
nav_order: 6
---

# Menus

Everything in the menus, menu by menu. Items marked *macOS* are added by the Mac to every app.

## Blokjutsu

- **About Blokjutsu**: the version, credits, and license.
- **Settings…** (⌘-comma): preferences that aren't image settings.
  - **Live preview**: show the image forming while it generates.
  - **Image cache**: memory used to keep history images ready for smooth scrolling.
  - **App data**: the folder with Blokjutsu's settings, logs, models, and (by default) your images, with a
    button to show it in Finder.
- **Services** (*macOS*): lets other apps act on what you've selected in Blokjutsu. Select some prompt text, for
  example, and Services offers what your Mac's apps can do with text, such as making a note or searching the web.
  The list depends on the apps you have. **Services Settings…** opens System Settings, where the checkboxes turn
  each service on or off in every app's Services menu and right-click menu. Blokjutsu doesn't use Services
  itself.
- **Hide Blokjutsu** (⌘H), **Hide Others** (⌥⌘H), and **Show All** (*macOS*): hide or show windows.
- **Quit Blokjutsu** (⌘Q).

## File

- **Generate** (⌘-Return): the same as the **Generate** button.
- **Import Parameters…** (⌘O): sets the controls from a `parameters.json` file, or from a PNG made with
  **Settings in PNG** turned on. Use it to repeat or adjust an image someone sent you.
- **Show Output Folder in Finder**: opens the folder your images are saved in.
- **Show App Data in Finder**: opens the folder with Blokjutsu's settings, logs, and models.
- **Download Model…**: downloads the MOSS-Image model, or checks for and fetches only the files that have
  changed. It asks before anything is downloaded.
- **Download Captioning Head…**: downloads the extra piece that Describe image and Enhance prompt need. It asks
  before anything is downloaded.
- **Delete All History…**: permanently deletes your images and everything made from your prompts. See
  [Your history](history.md#clearing-out).

## Edit

These work in whichever text box you're typing in.

- **Undo** (⌘Z) and **Redo** (⇧⌘Z): step back and forward through your typing. After **Use as prompt**,
  ⌘Z brings back your own prompt.
- **Cut** (⌘X), **Copy** (⌘C), and **Paste** (⌘V). **Copy** also works on text you've selected on an image's
  card, such as its prompt.
- **Select All** (⌘A).
- **Start Dictation…** (*macOS*): type by speaking.
- **Emoji & Symbols** (*macOS*): insert special characters.

## View

- **Appearance**: **System** follows your Mac's light or dark setting; **Light** or **Dark** keeps Blokjutsu
  that way whatever the Mac uses.
- **Enter Full Screen** (*macOS*, ⌃⌘F).

## Window

- **Minimize** (⌘M): sends the window to the Dock.
- **Zoom**: makes the window fill the screen without going full screen; choose it again to restore it.
- Anything else in this menu, such as arranging windows on the screen, is added by macOS.

## Help

- **Search** (*macOS*): finds any menu item by name.
- **Blokjutsu User's Guide**: this guide, in your web browser.
- **MOSS-Image User Guide**, **MOSS-Image Technical Report (arXiv)**, and **MOSS-Image on GitHub**: the model
  authors' own pages, in your web browser.
- **Show Log**: opens Blokjutsu's log file. If something goes wrong, the full error is there; include it when
  [reporting a problem](troubleshooting.md).
