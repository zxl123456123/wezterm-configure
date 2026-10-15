local wezterm = require 'wezterm'
local M = {}
local kinds = { workbench = true, grok = true, shell = true, yazi = true }

local function valid(s)
  if type(s) ~= 'table' or s.version ~= 1 or type(s.tabs) ~= 'table' or #s.tabs == 0
    or type(s.active) ~= 'number' or s.active % 1 ~= 0 or s.active < 1 or s.active > #s.tabs then return false end
  for _, t in ipairs(s.tabs) do
    if type(t) ~= 'table' or not kinds[t.kind] or type(t.title) ~= 'string'
      or type(t.cwd) ~= 'string' or not t.cwd:match('^%a:[/\\]')
      or t.cwd:find('[%z\r\n]') then return false end
  end
  return true
end

local function read(path)
  local f = io.open(path, 'rb')
  if not f then return nil end
  local raw = f:read('*a'); f:close()
  local ok, s = pcall(wezterm.json_parse, raw)
  if ok and valid(s) then return s, raw end
  return nil
end

local function write(path, raw)
  local f = assert(io.open(path, 'wb'))
  local ok, err = f:write(raw)
  local closed, close_err = f:close()
  assert(ok, err); assert(closed, close_err)
end

local function basename(path)
  return (path or ''):gsub('\\', '/'):match('([^/]+)$') or ''
end

local function is_workbench(executable, argv)
  if type(executable) ~= 'string' or executable:gsub('\\', '/'):lower()
    ~= 'd:/terminal-workbench/apps/zellij/zellij.exe' or type(argv) ~= 'table' then return false end
  local offset = #argv == 5 and 1 or 0
  return #argv == 4 + offset and argv[1 + offset] == 'attach'
    and argv[2 + offset] == 'workbench-v4' and argv[3 + offset] == '--create'
    and argv[4 + offset] == '--force-run-commands'
end

local function ancestor_kind(pane)
  local info = pane:get_foreground_process_info()
  local seen = {}
  local gui_pid = wezterm.procinfo.pid()
  local kind
  while info and info.pid ~= gui_pid and not seen[info.pid] do
    seen[info.pid] = true
    if is_workbench(info.executable, info.argv) then return 'workbench' end
    local name = basename(info.executable):lower()
    if name == 'grok.exe' then kind = 'grok'
    elseif name == 'yazi.exe' and not kind then kind = 'yazi' end
    -- The GUI is the boundary; do not query its entire child process tree.
    if not info.ppid or info.ppid == 0 or info.ppid == gui_pid then break end
    info = wezterm.procinfo.get_info_for_pid(info.ppid)
  end
  return kind
end

function M.setup(config, opts)
  local path, helper = assert(opts.state_path), assert(opts.helper_path)
  local key = 'native-tabs:' .. path
  local function state() return wezterm.GLOBAL[key] or {} end
  local function store(s) wezterm.GLOBAL[key] = s end
  local function warn(message)
    local s = state()
    if s.warning ~= message then wezterm.log_error('Native tabs: ' .. message) end
    s.warning = message; store(s)
  end
  local function command(t)
    return { domain = { DomainName = 'local' }, cwd = t.cwd, args = {
      'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
      '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass',
      '-File', helper, '-Kind', t.kind, '-Cwd', t.cwd,
    } }
  end

  config.status_update_interval = 2000
  wezterm.on('gui-startup', function(cmd)
    -- Only the existing workbench entry restores this private layout.
    if not (cmd and cmd.args and is_workbench(cmd.args[1], cmd.args)) then
      local s = state(); s.owner = false; store(s)
      wezterm.mux.spawn_window(cmd or {}); return
    end
    local snapshot = read(path) or read(path .. '.bak')
    if not snapshot then
      local f = io.open(path, 'rb'); local b = io.open(path .. '.bak', 'rb')
      if f or b then
        if f then f:close() end; if b then b:close() end
        local s = state(); s.blocked = true; store(s)
        warn('invalid snapshots; automatic saving paused for this process')
      end
      local tab, pane, window = wezterm.mux.spawn_window(cmd or {})
      local s = state(); s.owner = window:window_id(); s.workbench_panes = { [tostring(pane:pane_id())] = true }; store(s)
      tab:set_title('工作台')
      if opts.default_grok then
        local grok_tab = tab:window():spawn_tab({ domain = { DomainName = 'local' },
          cwd = 'D:/workspace-for-everything', args = {
            'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass',
            '-File', 'D:/terminal-workbench/Start-GrokShell.ps1',
          } })
        grok_tab:set_title('Grok'); tab:activate()
      end
      return
    end
    local s = state(); s.restoring = true; s.pending = {}; store(s)
    local ok, err = pcall(function()
      local window, tabs
      tabs = {}
      for i, t in ipairs(snapshot.tabs) do
        local tab, pane
        if i == 1 then
          tab, pane, window = wezterm.mux.spawn_window(command(t))
          s.owner = window:window_id()
        else tab, pane = window:spawn_tab(command(t)) end
        tab:set_title(t.title); tabs[i] = tab
        s.pending[#s.pending + 1] = pane:pane_id(); store(s)
      end
      tabs[snapshot.active]:activate()
    end)
    s = state(); s.restoring = false
    if not ok then s.blocked = true end
    store(s)
    if not ok then warn('partial restore; automatic saving paused: ' .. tostring(err)) end
  end)

  wezterm.on('update-status', function(window)
    local s = state()
    if s.blocked or s.restoring then return end
    if s.owner == false then return end
    local mux_window = window:mux_window()
    if s.owner == nil then
      -- Hot reload adopts only a pane with the exact existing Zellij client identity.
      if #wezterm.mux.all_windows() ~= 1 then warn('unowned multiple windows; snapshot preserved'); return end
      for _, tab in ipairs(mux_window:tabs()) do
        for _, pane in ipairs(tab:panes()) do
          if pane:get_domain_name() == 'local' and ancestor_kind(pane) == 'workbench' then
            s.owner = mux_window:window_id()
            s.workbench_panes = { [tostring(pane:pane_id())] = true }
            store(s); break
          end
        end
        if s.owner ~= nil then break end
      end
      if s.owner == nil then warn('workbench identity unavailable; snapshot preserved'); return end
    end
    if s.owner ~= mux_window:window_id() then return end
    if s.pending then
      for _, id in ipairs(s.pending) do
        local pane = wezterm.mux.get_pane(id)
        local status = pane and pane:get_user_vars().native_tabs_status
        if status == 'failed' or not pane then
          s.blocked = true; store(s); warn('partial restore; automatic saving paused'); return
        end
        if status ~= 'ready' then warn('waiting for restored tabs; snapshot preserved'); return end
      end
      s.pending = nil; store(s)
    end
    local ok, result = pcall(function()
      local windows = wezterm.mux.all_windows()
      assert(#windows == 1, 'multiple windows are unsupported; snapshot preserved')
      local snapshot = { version = 1, tabs = {}, active = 1 }
      local info = window:mux_window():tabs_with_info()
      assert(#info > 0, 'empty window; snapshot preserved')
      table.sort(info, function(a, b) return a.index < b.index end)
      for i, item in ipairs(info) do
        local panes = item.tab:panes()
        assert(#panes == 1, 'split panes are unsupported; snapshot preserved')
        local pane = panes[1]
        if pane:get_user_vars().native_tabs_status == 'failed' then
          local blocked = state(); blocked.blocked = true; store(blocked)
          error('tab startup failed; automatic saving paused')
        end
        assert(pane:get_domain_name() == 'local', 'remote domain is unsupported; snapshot preserved')
        local url = pane:get_current_working_dir()
        assert(url and url.scheme == 'file', 'unknown cwd; snapshot preserved')
        -- File URLs encode Windows drive paths with one leading slash.
        local cwd = url.file_path:gsub('^/(%a:/)', '%1')
        local vars = pane:get_user_vars()
        local identities = state().workbench_panes or {}
        -- Reported identities avoid expensive Windows process-tree queries.
        local kind = identities[tostring(pane:pane_id())] and 'workbench'
        if not kind and kinds[vars.native_tabs_kind] and vars.native_tabs_status == 'ready' then
          kind = vars.native_tabs_kind
        end
        kind = kind or ancestor_kind(pane) or 'shell'
        snapshot.tabs[i] = { kind = kind, title = item.tab:get_title(), cwd = cwd }
        if item.is_active then snapshot.active = i end
      end
      assert(valid(snapshot), 'invalid metadata; snapshot preserved')
      local raw = wezterm.json_encode(snapshot)
      local previous, previous_raw = read(path)
      if previous and wezterm.json_encode(previous) == raw then return end
      -- Only a valid primary can replace the last valid backup.
      write(path .. '.tmp', raw)
      if previous then write(path .. '.bak.tmp', previous_raw)
        local backup = io.open(path .. '.bak', 'rb')
        if backup then backup:close(); assert(os.remove(path .. '.bak')) end
        assert(os.rename(path .. '.bak.tmp', path .. '.bak')) end
      local primary = io.open(path, 'rb')
      if primary then primary:close(); assert(os.remove(path)) end
      assert(os.rename(path .. '.tmp', path))
    end)
    if not ok then warn(tostring(result)) else s = state(); s.warning = nil; store(s) end
  end)
end
return M
