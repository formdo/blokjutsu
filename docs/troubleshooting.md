---
title: Troubleshooting
parent: About
nav_order: 2
---

# Troubleshooting

## Look at the log first

**Help → Show Log** opens Blokjutsu's log. Errors appear there in full. Please include the end of it in a bug
report.

## Common problems

**"The model is not downloaded yet."** Use **File → Download Model…**. If you downloaded it before, the
download only fetches what's missing.

**A download fails or stops.** Click **Try again** or **Resume**; it continues where it stopped. **Show details**
in the download window says what went wrong.

**Pictures take very long, or the Mac becomes sluggish.** Memory is short. Turn on **Low memory**, close other
large apps, and use smaller sizes. See [Speed and memory](performance.md).

**Describing or enhancing seems to run forever.** With **Think first** on it can take several minutes; the token
count shows it's working. Turn Think first off for quicker answers.

**Blokjutsu won't open.** Download it again and replace the copy in Applications. If it still won't open, the
reason is at the end of `console.log` in the `logs` folder of `~/Library/Application Support/Blokjutsu.noindex`;
include it when you report the problem.

**Opening it a second time just brings the window forward.** That's deliberate: only one Blokjutsu runs at once.

## Resetting the settings

Blokjutsu keeps its settings in one file, `settings.json`: the controls as you last left them (prompt included),
the Output folder, the appearance, and the preferences in **Blokjutsu → Settings…**. If the app misbehaves in a
way that seems tied to a setting, you can put all of these back to their defaults:

1. Quit Blokjutsu.
2. In Finder, choose **Go → Go to Folder…**, type `~/Library/Application Support/Blokjutsu.noindex`, and press
   Return.
3. Move `settings.json` to the Trash.

This resets only the settings. Your pictures and the downloaded models are kept. To delete your pictures, use
[Delete all history](history.md#clearing-out); to remove everything, see
[Uninstalling](install.md#uninstalling).

## Reporting a problem

Open an issue at https://github.com/formdo/blokjutsu/issues with what you did, what happened, your Mac model and
memory, and the end of the log.
