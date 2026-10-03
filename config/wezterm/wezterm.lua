local wezterm = require 'wezterm'
local config = wezterm.config_builder()

-- Keep all user-managed terminal assets on D:, including the private font copy.
config.font_dirs = { 'D:/terminal-workbench/fonts' }
config.font = wezterm.font_with_fallback({
  'Maple Mono NF CN',
  'Maple Mono NF',
  'JetBrains Mono',
})
config.font_size = 11.0
config.line_height = 1.08
config.initial_cols = 150
config.initial_rows = 44
config.scrollback_lines = 10000
-- Used only when an alternate-screen app has not claimed mouse wheel events.
config.alternate_buffer_wheel_scroll_speed = 2

config.color_scheme = 'Catppuccin Macchiato'
local settings_path = 'D:/terminal-workbench/config/wezterm/appearance.json'
wezterm.add_to_config_reload_watch_list(settings_path)
local appearance = { image = 'terminal-background.png' }
local settings_file = io.open(settings_path, 'r')
if settings_file then
  local raw = settings_file:read('*a')
  settings_file:close()
  local ok, parsed = pcall(wezterm.json_parse, raw)
  if ok and type(parsed) == 'table' then
    for key, value in pairs(parsed) do appearance[key] = value end
  end
end
config.window_background_opacity = 1.0
local image_name = tostring(appearance.image or 'terminal-background.png')
-- A solid first layer prevents the desktop wallpaper from bleeding through.
config.background = {
  { source = { Color = '#24273a' }, width = '100%', height = '100%', opacity = 1.0 },
}
if image_name ~= 'none' then
  local image_path = 'D:/terminal-workbench/images/' .. image_name
  local image_file = io.open(image_path, 'rb')
  if image_file then
    image_file:close()
    table.insert(config.background, {
      source = { File = image_path }, width = '100%', height = '100%',
      repeat_x = 'NoRepeat', repeat_y = 'NoRepeat',
      opacity = 0.82,
    })
  end
end
table.insert(config.background, {
  source = { Color = '#24273a' }, width = '100%', height = '100%',
  opacity = 0.16,
})
config.text_background_opacity = 0.84
config.window_padding = { left = 10, right = 10, top = 8, bottom = 8 }
-- Keep Zellij as the main workspace; expose a separate native WezTerm tab only
-- for true Yazi image rendering, which Zellij cannot reliably pass through.
config.enable_tab_bar = true
config.hide_tab_bar_if_only_one_tab = true
config.use_fancy_tab_bar = false
config.tab_max_width = 24
config.colors = {
  tab_bar = {
    background = '#1e2030',
    active_tab = { bg_color = '#8aadf4', fg_color = '#1e2030', intensity = 'Bold' },
    inactive_tab = { bg_color = '#363a4f', fg_color = '#cad3f5' },
    inactive_tab_hover = { bg_color = '#494d64', fg_color = '#f5bde6' },
    new_tab = { bg_color = '#1e2030', fg_color = '#8bd5ca' },
    new_tab_hover = { bg_color = '#363a4f', fg_color = '#f5bde6' },
  },
}
config.window_close_confirmation = 'NeverPrompt'
-- Never discard a failed startup message: keep the terminal open for diagnosis.
config.exit_behavior = 'Hold'
config.exit_behavior_messaging = 'Verbose'
config.default_cwd = 'D:/workspace-for-everything'
config.default_prog = { 'C:/Windows/System32/cmd.exe' }
config.keys = {
  {
    key = 'I', mods = 'CTRL|SHIFT',
    action = wezterm.action.SpawnCommandInNewTab {
      cwd = 'D:/workspace-for-everything',
      args = { 'D:/terminal-workbench/apps/yazi/yazi-x86_64-pc-windows-msvc/yazi.exe' },
      set_environment_variables = {
        YAZI_CONFIG_HOME = 'D:/terminal-workbench/config/yazi',
        YAZI_FILE_ONE = 'C:/Program Files/Git/usr/bin/file.exe',
      },
    },
  },
}

-- The window title stays readable instead of displaying the active executable path.
wezterm.on('format-window-title', function()
  return 'Terminal Workbench'
end)

return config
