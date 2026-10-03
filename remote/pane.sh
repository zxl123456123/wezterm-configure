#!/usr/bin/env bash
set -e

slot="${1:-}"
case "$slot" in
  main) default="$HOME/projects/workbench" ;;
  dev) default="$HOME" ;;
  files) default="$HOME/projects/workbench/publish" ;;
  *) echo "Unknown workbench pane" >&2; exit 2 ;;
esac

state_dir="$HOME/.local/state/terminal-workbench"
mkdir -p "$state_dir"
state_file="$state_dir/$slot.cwd"
target="$default"
if [[ -s "$state_file" ]]; then
  IFS= read -r saved < "$state_file" || true
  if [[ -d "$saved" ]]; then target="$saved"; fi
fi
if ! cd -- "$target"; then cd -- "$HOME"; fi
export TWB_CWD_FILE="$state_file"
exec bash --rcfile "$HOME/.local/share/terminal-workbench/rc.sh" -i
