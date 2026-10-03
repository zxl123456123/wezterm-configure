$ErrorActionPreference = 'Stop'
$root = 'D:\terminal-workbench'
$env:YAZI_CONFIG_HOME = Join-Path $root 'config\yazi'
$env:YAZI_FILE_ONE = 'C:\Program Files\Git\usr\bin\file.exe'
$env:PATH = (Join-Path $root 'apps\chafa\chafa-1.18.3-1-x86_64-win') + ';' + $env:PATH
$saved = Join-Path $root 'data\work-windows-yazi.cwd'
$startDir = 'D:\workspace-for-everything'
if (Test-Path -LiteralPath $saved -PathType Leaf) {
    $candidate = [System.IO.File]::ReadAllText($saved, [System.Text.Encoding]::UTF8).Trim()
    if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
        $startDir = $candidate
    }
}
& (Join-Path $root 'apps\yazi\yazi-x86_64-pc-windows-msvc\yazi.exe') $startDir
