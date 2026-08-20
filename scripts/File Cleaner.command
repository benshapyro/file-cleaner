#!/bin/zsh
set -eu

if command -v file-cleaner >/dev/null 2>&1; then
  CLEANER=$(command -v file-cleaner)
elif command -v uv >/dev/null 2>&1; then
  CLEANER="$(uv tool dir --bin)/file-cleaner"
else
  CLEANER="$HOME/.local/bin/file-cleaner"
fi

if [[ ! -x "$CLEANER" ]]; then
  echo "File Cleaner is not installed. Run install.command first."
  read "?Press Return to close."
  exit 1
fi

"$CLEANER" clean "$HOME/Downloads"
echo
read "?Press Return to close."
