#!/bin/bash
# Preview the User's Guide at http://127.0.0.1:4000/blokjutsu/, rebuilding on every save. Ctrl-C stops it.
# Needs Homebrew's Ruby (brew install ruby); the first run installs Jekyll into docs/vendor.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$(brew --prefix ruby)/bin:$PATH"
cp ../blokjutsu/resources/icon.png ../blokjutsu/resources/icon.svg assets/
bundle config set --local path vendor/bundle >/dev/null
bundle check >/dev/null || bundle install
exec bundle exec jekyll serve --livereload "$@"
