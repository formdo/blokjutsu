#!/bin/bash
# Build a self-contained, signed, and notarized Blokjutsu.app and a .dmg holding it.
#
#   scripts/make_dmg.sh --no-sign        assemble the app only, to try it before signing
#   scripts/make_dmg.sh --no-notarize    assemble and sign, without sending anything to Apple
#   scripts/make_dmg.sh                  the release build: assemble, sign, notarize, and staple
#
# Run from the repository root on an Apple silicon Mac with uv and Xcode's Command Line Tools. Signing uses the
# "Developer ID Application" certificate in your keychain; notarization uses the notarytool credentials stored
# under the keychain profile "blokjutsu" (or $NOTARY_PROFILE). Output goes to build/dmg/ and dist/.
set -euo pipefail

PYTHON_VERSION="3.12"
NOTARY_PROFILE="${NOTARY_PROFILE:-blokjutsu}"
SIGN=1
NOTARIZE=1
for arg in "$@"; do
  case "$arg" in
    --no-sign) SIGN=0; NOTARIZE=0 ;;
    --no-notarize) NOTARIZE=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m%s\033[0m\n' "$*"; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

[ -f pyproject.toml ] && [ -d blokjutsu ] || die "run this from the repository root."
[ "$(uname -m)" = arm64 ] || die "build on an Apple silicon Mac."
command -v uv >/dev/null || die "uv is not installed (https://docs.astral.sh/uv/)."
command -v clang >/dev/null || die "Xcode's Command Line Tools are missing: run xcode-select --install."

VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
BUILD="build/dmg"
APP="$BUILD/Blokjutsu.app"
RES="$APP/Contents/Resources"
PY="$RES/python/bin/python3"
DMG="dist/Blokjutsu-$VERSION.dmg"
ENTITLEMENTS="scripts/dmg/entitlements.plist"

if [ "$SIGN" = 1 ]; then
  IDENTITY=$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application: .*\)"/\1/p' | head -1)
  [ -n "$IDENTITY" ] || die "no Developer ID Application certificate in your keychain."
  say "Signing as: $IDENTITY"
fi

say "1/6  A standalone Python $PYTHON_VERSION"
rm -rf "$BUILD" && mkdir -p "$BUILD/python" dist
uv python install --quiet --install-dir "$BUILD/python" "$PYTHON_VERSION"
PYDIR=$(find "$BUILD/python" -maxdepth 1 -type d -name "cpython-$PYTHON_VERSION*" | head -1)
[ -n "$PYDIR" ] || die "uv did not install Python $PYTHON_VERSION."
mkdir -p "$APP"
PYTHONPATH="$PWD" "$PYDIR/bin/python3" -c "import sys; from blokjutsu.macapp import skeleton; skeleton(sys.argv[1])" "$APP"
ditto "$PYDIR" "$RES/python"
rm -rf "$BUILD/python"

say "2/6  Blokjutsu and the library versions it was tested with (a few minutes)"
uv pip install --quiet --python "$PY" --break-system-packages --constraint constraints.txt .
rm -rf "$RES/python/lib/python$PYTHON_VERSION"/{test,idlelib,tkinter,turtledemo,ensurepip}
rm -rf "$RES/python/lib/python$PYTHON_VERSION/site-packages/torch/include"
"$PY" -m compileall -q -j 0 --invalidation-mode unchecked-hash "$RES/python/lib" >/dev/null || true

say "3/6  The launcher"
clang -O2 -arch arm64 -mmacosx-version-min=12.3 -o "$APP/Contents/MacOS/blokjutsu" scripts/dmg/launcher.c
cp LICENSE NOTICE "$RES/"
touch "$APP"

if [ "$SIGN" = 0 ]; then
  say "Built $APP (unsigned). Try it with: open $APP"
  exit 0
fi

sign() { codesign --force --timestamp --options runtime --sign "$IDENTITY" "$@"; }
export -f sign
export IDENTITY

say "4/6  Signing every program file in the app (several minutes)"
machos() {   # NUL-separated Mach-O files under the app: $1 = outside (not in a framework) or frameworks
  "$PY" - "$APP" "$1" <<'EOF'
import os, sys
MAGIC = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
app, want = sys.argv[1], sys.argv[2]
for root, dirs, files in os.walk(app):
    if root == os.path.join(app, "Contents", "MacOS") or (".framework" in root) != (want == "frameworks"):
        continue
    for name in files:
        path = os.path.join(root, name)
        if not os.path.islink(path):
            with open(path, "rb") as f:
                if f.read(4) in MAGIC:
                    sys.stdout.write(path + "\0")
EOF
}
# Signing a bundle's main executable signs its whole bundle. So the app's launcher is signed last, with the app,
# and the Qt frameworks (whose wheel layout holds several copies of each binary) one file at a time.
machos outside | xargs -0 -n 50 -P 8 bash -c 'for f; do sign "$f" >/dev/null 2>&1 || sign "$f"; done' _
machos frameworks | xargs -0 -n 1 bash -c 'sign "$1" >/dev/null 2>&1 || sign "$1"' _
PYBIN=$(cd "$RES/python/bin" && readlink python3 || echo python3)
sign --entitlements "$ENTITLEMENTS" "$RES/python/bin/$PYBIN"
sign --entitlements "$ENTITLEMENTS" "$APP"
codesign --verify --deep --strict "$APP"

notarize() {
  local file="$1" result
  result=$(xcrun notarytool submit "$file" --keychain-profile "$NOTARY_PROFILE" --wait --output-format json)
  echo "$result" | "$PY" -c 'import json, sys; r = json.load(sys.stdin); print(r["status"], r["id"])' | {
    read -r status id
    if [ "$status" != "Accepted" ]; then
      xcrun notarytool log "$id" --keychain-profile "$NOTARY_PROFILE" "$BUILD/notary-$id.json" || true
      die "Apple did not accept $file ($status). Details: $BUILD/notary-$id.json"
    fi
  }
}

if [ "$NOTARIZE" = 1 ]; then
  say "5/6  Notarizing the app (uploads about 1 GB; Apple usually answers in a few minutes)"
  ditto -c -k --keepParent "$APP" "$BUILD/Blokjutsu.zip"
  notarize "$BUILD/Blokjutsu.zip"
  xcrun stapler staple "$APP"
  rm "$BUILD/Blokjutsu.zip"
fi

say "6/6  The disk image"
STAGE="$BUILD/stage"
rm -rf "$STAGE" "$DMG" && mkdir -p "$STAGE"
ditto "$APP" "$STAGE/Blokjutsu.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname "Blokjutsu $VERSION" -srcfolder "$STAGE" -fs HFS+ -format ULFO "$DMG"
rm -rf "$STAGE"
codesign --force --timestamp --sign "$IDENTITY" "$DMG"
if [ "$NOTARIZE" = 1 ]; then
  notarize "$DMG"
  xcrun stapler staple "$DMG"
  spctl --assess --type open --context context:primary-signature -v "$DMG"
fi
say "Built $DMG ($(du -h "$DMG" | cut -f1))"
