#!/bin/zsh
set -eu

SCRIPT_DIR=${0:A:h:h}

if ! command -v uv >/dev/null 2>&1; then
  echo "File Cleaner needs the 'uv' Python installer. Install uv, then run this installer again."
  echo "Nothing was changed."
  read "?Press Return to close."
  exit 1
fi

echo "Installing the isolated file-cleaner command from: $SCRIPT_DIR"
uv tool install --force "$SCRIPT_DIR"

echo
read "install_launcher?Also install the double-click launcher in your Applications folder? [y/N] "
case "$install_launcher" in
  y|Y|yes|YES)
    mkdir -p "$HOME/Applications"
    install -m 755 "$SCRIPT_DIR/scripts/File Cleaner.command" "$HOME/Applications/File Cleaner.command"
    echo "Installed: $HOME/Applications/File Cleaner.command"
    ;;
  *)
    echo "Launcher skipped. Your shell configuration was not changed."
    ;;
esac

BIN_DIR=$(uv tool dir --bin)
echo
echo "Installed command: $BIN_DIR/file-cleaner"
echo "First safe preview: $BIN_DIR/file-cleaner scan \"$HOME/Downloads\""
read "?Press Return to close."
