@echo off
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter 'Name=''wezterm-gui.exe''' | Where-Object { $_.CommandLine -like '*terminal-workbench*wezterm.lua*' -and $_.CommandLine -like '*attach workbench-v4*' } | Select-Object -First 1; if($p){exit 0}else{exit 1}"
if not errorlevel 1 (
  powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter 'Name=''wezterm-gui.exe''' | Where-Object { $_.CommandLine -like '*terminal-workbench*wezterm.lua*' -and $_.CommandLine -like '*attach workbench-v4*' } | Select-Object -First 1; if($p){(New-Object -ComObject WScript.Shell).AppActivate($p.ProcessId) | Out-Null}"
  powershell -NoProfile -ExecutionPolicy Bypass -File "D:\terminal-workbench\Ensure-WorkbenchTabs.ps1" >> "D:\terminal-workbench\data\startup.log" 2>&1
  if errorlevel 1 goto startup_failed
  exit /b 0
)
set "WEZTERM_CONFIG_FILE=D:\terminal-workbench\config\wezterm\wezterm.lua"
set "ZELLIJ_CONFIG_DIR=D:\terminal-workbench\config\zellij"
set "YAZI_FILE_ONE=C:\Program Files\Git\usr\bin\file.exe"
set "YAZI_CONFIG_HOME=D:\terminal-workbench\config\yazi"
set "CNMPLAYER_ASSET_DIR=D:\terminal-workbench\data\cnmplayer"
set "PATH=D:\terminal-workbench\apps\chafa\chafa-1.18.3-1-x86_64-win;D:\terminal-workbench\apps\zellij;D:\terminal-workbench\apps\yazi\yazi-x86_64-pc-windows-msvc;D:\terminal-workbench\apps\fastfetch;D:\terminal-workbench\apps\zoxide;D:\terminal-workbench\apps\fzf;D:\terminal-workbench\apps\bottom;%PATH%"
start "" "D:\terminal-workbench\apps\wezterm\wezterm-gui.exe" --config-file "D:\terminal-workbench\config\wezterm\wezterm.lua" start --always-new-process --cwd "D:\workspace-for-everything" -- "D:\terminal-workbench\apps\zellij\zellij.exe" attach workbench-v4 --create --force-run-commands
powershell -NoProfile -Command "Start-Sleep -Seconds 3"
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\terminal-workbench\Ensure-WorkbenchTabs.ps1" >> "D:\terminal-workbench\data\startup.log" 2>&1
if errorlevel 1 goto startup_failed
exit /b 0

:startup_failed
set "workbench_startup_exit=%errorlevel%"
echo Workbench startup failed: exit=%workbench_startup_exit%. See D:\terminal-workbench\data\startup.log 1>&2
>> "D:\terminal-workbench\data\startup.log" echo Workbench startup failed: exit=%workbench_startup_exit%.
exit /b %workbench_startup_exit%
