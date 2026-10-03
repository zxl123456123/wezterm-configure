@echo off
tasklist /FI "IMAGENAME eq yasb.exe" | find /I "yasb.exe" >nul
if errorlevel 1 call "D:\terminal-workbench\Start-DesktopBar.cmd"
tasklist /FI "IMAGENAME eq glazewm.exe" | find /I "glazewm.exe" >nul
if errorlevel 1 call "D:\terminal-workbench\Start-Tiling.cmd"
call "D:\terminal-workbench\Start-TerminalWorkbench.cmd"
