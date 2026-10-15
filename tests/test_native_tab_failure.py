"""Verify -NoExit cannot turn a failed restored tab into a saved ready shell."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

repo = Path(__file__).resolve().parents[1]
root = repo / '.validation' / ('native-failure-' + uuid.uuid4().hex)
root.mkdir(parents=True)
exe = Path(r'D:\terminal-workbench\apps\wezterm\wezterm.exe')
for name in ('Start-WorkShell.ps1', 'Start-NativeTab.ps1'):
    text = (repo / name).read_text(encoding='utf-8-sig')
    text = text.replace(r'D:\terminal-workbench', str(root)).replace(r'D:\workspace-for-everything', str(root))
    if name == 'Start-WorkShell.ps1':
        text = text.replace('function global:prompt {', "function global:prompt {\n    [Console]::Write(([string][char]27 + ']1337;SetUserVar=test_prompt=dHJ1ZQ==' + [char]7))")
        # WezTerm may rebuild PATH when spawning; isolate it inside the child too.
        text += "\n$env:PATH = 'C:\\Windows\\System32'\n"
    (root / name).write_text(text, encoding='utf-8-sig')
state = {'version': 1, 'tabs': [{'kind': 'grok', 'title': 'Failed startup fixture', 'cwd': str(root)}], 'active': 1}
state_path = root / 'state.json'
state_path.write_text(json.dumps(state), encoding='utf-8')
initial = state_path.read_bytes()
def lua_path(path):
    return json.dumps(str(path).replace('\\', '/'))
config = "local wezterm=require 'wezterm'\nlocal config=wezterm.config_builder()\n"
config += 'dofile(' + lua_path(repo / 'config/wezterm/native-tabs.lua') + ').setup(config,{state_path=' + lua_path(state_path) + ',helper_path=' + lua_path(root / 'Start-NativeTab.ps1') + '})\n'
config += '''wezterm.on('update-status',function(window)
  local p=window:mux_window():active_pane()
  local f=assert(io.open(RESULT_PATH,'wb'))
  f:write(wezterm.json_encode({vars=p:get_user_vars(),text=p:get_lines_as_text(20),
    state=wezterm.GLOBAL['native-tabs:'..STATE_PATH]}));f:close()
end)
return config
'''.replace('RESULT_PATH', lua_path(root / 'observed.json')).replace('STATE_PATH', lua_path(state_path))
(root / 'wezterm.lua').write_text(config, encoding='utf-8')
env = os.environ.copy()
env['PATH'] = r'C:\Windows\System32'
env['PSModulePath'] = r'C:\Windows\System32\WindowsPowerShell\v1.0\Modules;C:\Program Files\WindowsPowerShell\Modules'
env.pop('ZELLIJ', None)
si = subprocess.STARTUPINFO()
si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = 0
p = subprocess.Popen([str(exe.with_name('wezterm-gui.exe')), '--config-file', str(root / 'wezterm.lua'),
    'start', '--always-new-process', '--class', 'OwnedFailureTest', '--',
    r'D:\terminal-workbench\apps\zellij\zellij.exe', 'attach', 'workbench-v4', '--create', '--force-run-commands'],
    env=env, stdout=(root / 'stdout.txt').open('wb'), stderr=(root / 'stderr.txt').open('wb'), startupinfo=si)
try:
    end = time.monotonic() + 30
    observed = None
    while time.monotonic() < end:
        try:
            observed = json.loads((root / 'observed.json').read_text(encoding='utf-8'))
            if observed['vars'].get('test_prompt') == 'true':
                break
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(.25)
    assert observed and observed['vars'].get('test_prompt') == 'true', 'The -NoExit prompt was not exercised'
    time.sleep(2.5)
    observed = json.loads((root / 'observed.json').read_text(encoding='utf-8'))
    assert observed['vars'].get('native_tabs_status') == 'failed', observed
    assert observed['state'].get('blocked') is True, observed
    assert state_path.read_bytes() == initial, 'Failed restoration overwrote the snapshot'
    print(json.dumps({'exit': 0, 'failed_status_after_prompt': True, 'saving_blocked': True,
        'snapshot_unchanged': True, 'fixture': str(root)}))
finally:
    if p.poll() is None:
        p.terminate()
        p.wait(timeout=10)
