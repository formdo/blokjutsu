#!/bin/sh
# Blokjutsu installer for macOS (Apple silicon).
#
#   curl -LsSf https://formdo.github.io/blokjutsu/install.sh | sh                   install or update
#   curl -LsSf https://formdo.github.io/blokjutsu/install.sh | sh -s -- --uninstall  remove the app (keeps pictures)
#
# Everything goes into ~/Library/Application Support/Blokjutsu.noindex (uv, Python, the app's environment, and,
# later, the model and your images), kept out of Time Machine and Spotlight, plus ~/Applications/Blokjutsu.app.
# Nothing else is changed.
# The model itself (about 30 GB) is downloaded later, from inside the app, after you confirm.
set -eu

VERSION="1.0.0rc3"
SOURCE="${BLOKJUTSU_SOURCE:-https://github.com/formdo/blokjutsu/archive/refs/tags/v${VERSION}.tar.gz}"   # or a local folder
PYTHON_VERSION="3.12"
SUPPORT="${BLOKJUTSU_HOME:-$HOME/Library/Application Support/Blokjutsu.noindex}"
APPS="$HOME/Applications"
TOOLS="$SUPPORT/tools"               # uv, the Python it installs, and its download cache
RUNTIME="$SUPPORT/runtime"           # the environment Blokjutsu runs in

say() { printf '\033[1m%s\033[0m\n' "$*"; }
warn() { printf 'Note: %s\n' "$*" >&2; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

uninstall() {
  rm -rf "$APPS/Blokjutsu.app" "$TOOLS" "$RUNTIME"
  say "Blokjutsu is uninstalled."
  echo "Kept: the model, your settings and pictures in the default Output folder, all in $SUPPORT."
  echo "To remove those too:  rm -rf \"$SUPPORT\""
  exit 0
}

[ "${1:-}" = "--uninstall" ] && uninstall
[ "$(uname -s)" = Darwin ] || die "Blokjutsu runs on macOS only."
[ "$(uname -m)" = arm64 ] || die "Blokjutsu needs a Mac with Apple silicon (M1 or later)."

memory_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
[ "$memory_gb" -ge 32 ] || warn "this Mac has ${memory_gb} GB of memory; MOSS-Image needs about 30 GB, so pictures will be slow."
free_gb=$(( $(df -k "$HOME" | awk 'NR==2 {print $4}') / 1048576 ))
[ "$free_gb" -ge 45 ] || warn "only ${free_gb} GB free; the app needs about 5 GB and the model about 30 GB more."

say "Installing Blokjutsu ${VERSION} into $SUPPORT"
if [ ! -d "$SUPPORT" ]; then
  mkdir -p "$SUPPORT"
  tmutil addexclusion "$SUPPORT" 2>/dev/null || true   # first install only; your later choice is kept
fi
mkdir -p "$TOOLS" "$APPS"
export UV_CACHE_DIR="$TOOLS/cache" UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PYTHON_PREFERENCE=only-managed

if [ ! -x "$TOOLS/bin/uv" ]; then
  say "1/4  Getting uv (a small, self-contained Python installer from astral.sh)"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$TOOLS/bin" sh >/dev/null
fi
UV="$TOOLS/bin/uv"

say "2/4  Getting Python ${PYTHON_VERSION}"
"$UV" python install --quiet "$PYTHON_VERSION"

say "3/4  Installing Blokjutsu and the library versions it was tested with (about 2 GB; a few minutes)"
SRC="$TOOLS/src"
rm -rf "$RUNTIME" "$SRC"
mkdir -p "$SRC"
if [ -d "$SOURCE" ]; then
  cp -R "$SOURCE"/. "$SRC"
else
  curl -LsSf "$SOURCE" | tar -xz -C "$SRC" --strip-components 1
fi
[ -f "$SRC/constraints.txt" ] || die "the download has no constraints.txt; is $SOURCE a Blokjutsu release?"
"$UV" venv --quiet --python "$PYTHON_VERSION" "$RUNTIME"
"$UV" pip install --quiet --python "$RUNTIME/bin/python" --constraint "$SRC/constraints.txt" "$SRC"
rm -rf "$SRC"

say "4/4  Adding Blokjutsu to $APPS"
"$RUNTIME/bin/python" -m blokjutsu.macapp --dest "$APPS" --python "$RUNTIME/bin/python" >/dev/null
"$UV" cache prune --quiet || true

say "Done."
echo "Open Blokjutsu from your Applications folder, Launchpad or Spotlight."
echo "On first launch it asks before downloading the model (about 30 GB)."
open "$APPS/Blokjutsu.app" 2>/dev/null || true
