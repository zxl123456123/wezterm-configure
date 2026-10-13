param(
    [ValidateSet('workbench','grok','shell','yazi')][string]$Kind,
    [string]$Cwd,
    [switch]$CheckWorkbenchSnapshot
)
$ErrorActionPreference = 'Stop'
if ($CheckWorkbenchSnapshot) {
    foreach ($path in @('D:\terminal-workbench\data\native-tabs.json', 'D:\terminal-workbench\data\native-tabs.json.bak')) {
        try {
            $s = [IO.File]::ReadAllText($path) | ConvertFrom-Json
            $versionNumeric = $s.version -is [int] -or $s.version -is [long] -or $s.version -is [double] -or $s.version -is [decimal]
            $activeNumeric = $s.active -is [int] -or $s.active -is [long] -or $s.active -is [double] -or $s.active -is [decimal]
            if (-not $versionNumeric -or $s.version -ne 1 -or $s.tabs -isnot [array] -or $s.tabs.Count -eq 0 -or
                -not $activeNumeric -or $s.active -ne [Math]::Floor($s.active) -or
                $s.active -lt 1 -or $s.active -gt $s.tabs.Count) { continue }
            $valid = $true
            foreach ($t in $s.tabs) {
                if ($t.kind -isnot [string] -or $t.kind -cnotin @('workbench','grok','shell','yazi') -or $t.title -isnot [string] -or
                    $t.cwd -isnot [string] -or $t.cwd -notmatch '^[A-Za-z]:[/\\]' -or $t.cwd -match '[\x00\r\n]') { $valid = $false; break }
            }
            if ($valid) { if (@($s.tabs | Where-Object { $_.kind -ceq 'workbench' }).Count -eq 0) { exit 0 }; exit 1 }
        } catch { }
    }
    exit 1
}
function Set-NativeTabStatus([string]$Status) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Status))
    [Console]::Write(([string][char]27 + ']1337;SetUserVar=native_tabs_status=' + $encoded + [char]7))
}
function Set-NativeTabKind([string]$Value) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Value))
    [Console]::Write(([string][char]27 + ']1337;SetUserVar=native_tabs_kind=' + $encoded + [char]7))
}
try {
    if (-not $Kind -or $Cwd -notmatch '^[A-Za-z]:[/\\]' -or $Cwd -match '[\x00\r\n]' -or
        -not (Test-Path -LiteralPath $Cwd -PathType Container)) { throw 'Native tab directory is unavailable.' }
    if ($Kind -eq 'grok' -or $Kind -eq 'shell') { . 'D:\terminal-workbench\Start-WorkShell.ps1' }
    Set-Location -LiteralPath $Cwd
    $program = switch ($Kind) {
        'workbench' { 'D:\terminal-workbench\apps\zellij\zellij.exe' }
        'yazi' { 'D:\terminal-workbench\apps\yazi\yazi-x86_64-pc-windows-msvc\yazi.exe' }
        'grok' { (Get-Command grok -CommandType Application -ErrorAction Stop).Source }
    }
    if ($program -and -not (Test-Path -LiteralPath $program -PathType Leaf)) { throw 'Native tab application is unavailable.' }
    Set-NativeTabKind $Kind
    Set-NativeTabStatus 'ready'
    switch ($Kind) {
        'workbench' { & $program attach workbench-v4 --create --force-run-commands }
        'grok' { Remove-Item Env:ZELLIJ, Env:ZELLIJ_SESSION_NAME -ErrorAction SilentlyContinue; & $program --continue }
        'yazi' {
            $env:YAZI_CONFIG_HOME = 'D:\terminal-workbench\config\yazi'
            $env:YAZI_FILE_ONE = 'C:\Program Files\Git\usr\bin\file.exe'
            & $program
        }
    }
    if ($program -and $LASTEXITCODE -ne 0) { throw "Native tab application exited with code $LASTEXITCODE." }
    Set-NativeTabKind 'shell'
} catch {
    Set-NativeTabStatus 'failed'
    [Console]::Error.WriteLine("Native tab startup failed: $($_.Exception.Message)")
    exit 1
}
