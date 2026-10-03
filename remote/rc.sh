if [[ -r "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc"
fi

__twb_save_cwd() {
  [[ -n "${TWB_CWD_FILE:-}" ]] && printf '%s\n' "$PWD" > "$TWB_CWD_FILE"
}
PROMPT_COMMAND="__twb_save_cwd${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
