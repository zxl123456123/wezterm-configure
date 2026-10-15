-- Run with NATIVE_TABS_TEST_OUTPUT pointing at an existing temporary directory.
local real = require 'wezterm'
local root = assert(os.getenv('NATIVE_TABS_TEST_OUTPUT')):gsub('\\', '/')
local results = {}
for _, scenario in ipairs({'direct-shell', 'nested-grok', 'workbench', 'reported-shell'}) do
  local calls, callbacks = {}, {}
  local path = root .. '/' .. scenario .. '.json'
  local vars = scenario == 'reported-shell' and {native_tabs_kind='shell', native_tabs_status='ready'} or {}
  local pane = {}
  function pane:pane_id() return 1 end
  function pane:get_domain_name() return 'local' end
  function pane:get_user_vars() return vars end
  function pane:get_current_working_dir() return {scheme='file',file_path='/C:/fixture'} end
  function pane:get_foreground_process_info()
    calls[#calls+1] = 'foreground'
    assert(scenario ~= 'reported-shell', 'Reported shell must not query processes')
    if scenario == 'workbench' then
      return {pid=2,ppid=999,executable='D:/terminal-workbench/apps/zellij/zellij.exe',
        argv={'attach','workbench-v4','--create','--force-run-commands'}}
    end
    return {pid=2,ppid=scenario == 'nested-grok' and 3 or 999,executable='C:/Windows/powershell.exe'}
  end
  local tab = {panes=function() return {pane} end,get_title=function() return 'Fixture' end}
  local window = {window_id=function() return 0 end,tabs_with_info=function() return {{index=0,is_active=true,tab=tab}} end}
  local proxy = setmetatable({GLOBAL={['native-tabs:'..path]={owner=0}},on=function(e,f) callbacks[e]=f end,
    procinfo={pid=function() return 999 end,get_info_for_pid=function(pid)
      calls[#calls+1]=pid
      assert(pid ~= 999, 'Must stop before querying the GUI process tree')
      assert(pid == 3)
      return {pid=3,ppid=999,executable='C:/fixture/grok.exe'}
    end},mux={all_windows=function() return {window} end},log_error=function(message)
      local f=assert(io.open(root .. '/failure.txt','wb')); f:write(message); f:close()
      error(message)
    end}, {__index=real})
  package.loaded.wezterm=proxy
  dofile(real.config_dir .. '/../config/wezterm/native-tabs.lua').setup({}, {state_path=path,helper_path='C:/fixture/helper.ps1'})
  callbacks['update-status']({mux_window=function() return window end})
  local f=assert(io.open(path,'rb')); local saved=real.json_parse(f:read('*a')); f:close()
  local expected=scenario == 'nested-grok' and 'grok' or scenario == 'workbench' and 'workbench' or 'shell'
  assert(saved.tabs[1].kind == expected)
  results[#results+1]={scenario=scenario,calls=calls,saved_kind=expected}
end
package.loaded.wezterm=real
local f=assert(io.open(root .. '/result.json','wb')); f:write(real.json_encode(results)); f:close()
return {}
