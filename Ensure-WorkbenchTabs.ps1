$ErrorActionPreference = 'Stop'
$zellij = 'D:\terminal-workbench\apps\zellij\zellij.exe'
$session = 'workbench-v4'
$layoutDir = 'D:\terminal-workbench\config\zellij\layouts'
$env:ZELLIJ_CONFIG_DIR = 'D:\terminal-workbench\config\zellij'

function Invoke-Zellij {
    param([string[]]$Arguments, [int]$TimeoutMs = 2000)
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $zellij
    $info.Arguments = ($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $context = "session=$session action=$($Arguments -join ' ')"
    try {
        $process = [System.Diagnostics.Process]::Start($info)
    } catch {
        throw "Zellij start failed: $context; $($_.Exception.Message)"
    }
    try {
        if (-not $process.WaitForExit($TimeoutMs)) {
            $process.Kill()
            throw "Zellij command timed out: $context timeout=${TimeoutMs}ms"
        }
        $output = $process.StandardOutput.ReadToEnd()
        $errorText = $process.StandardError.ReadToEnd()
        if ($process.ExitCode -ne 0) {
            $stdout = if ($output.Trim()) { $output.Trim() } else { '<empty>' }
            $stderr = if ($errorText.Trim()) { $errorText.Trim() } else { '<empty>' }
            throw "Zellij command failed: $context exit=$($process.ExitCode)`nstdout: $stdout`nstderr: $stderr"
        }
        return $output
    } finally {
        $process.Dispose()
    }
}

function Get-WorkbenchTabs {
    $lines = (Invoke-Zellij -Arguments @('--session', $session, 'action',
                                       'list-tabs', '--state')) -split '\r?\n'
    foreach ($line in $lines) {
        if ($line -match '^\s*(\d+)\s+(\d+)\s+(\S+)\s+(true|false)\s') {
            [pscustomobject]@{
                Id = [int]$Matches[1]
                Position = [int]$Matches[2]
                Name = $Matches[3]
                Active = $Matches[4] -eq 'true'
            }
        }
    }
}

try {
    $stage = 'wait-session'
    $lastError = $null
    $tabs = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $tabs = @(Get-WorkbenchTabs)
            if ($tabs.Count -gt 0) { break }
            $lastError = "session=$session action=list-tabs --state returned no parseable tabs"
        } catch {
            $lastError = $_.Exception.Message
        }
        Start-Sleep -Milliseconds 400
    }
    if (-not $tabs -or $tabs.Count -eq 0) {
        throw "Session not ready after 20 attempts; last error: $lastError"
    }

    $original = ($tabs | Where-Object Active | Select-Object -First 1).Name
    $expected = @(
        @{ Name='Work-Windows'; Layout='work-windows-tab.kdl'; Position=0 },
        @{ Name='Work-for-Linux'; Layout='work-linux-tab.kdl'; Position=1 },
        @{ Name='Monitor'; Layout='monitor.kdl'; Position=2 },
        @{ Name='Music'; Layout='music.kdl'; Position=3 },
        @{ Name='Control'; Layout='control.kdl'; Position=4 }
    )
    foreach ($item in $expected) {
        if ($tabs.Name -contains $item.Name) { continue }
        $layout = Join-Path $layoutDir $item.Layout
        $stage = "create $($item.Name)"
        Invoke-Zellij -Arguments @('--session', $session, 'action', 'new-tab',
                                  '--layout', $layout, '--name', $item.Name) -TimeoutMs 8000 | Out-Null
        $stage = "query after create $($item.Name)"
        $tabs = @(Get-WorkbenchTabs)
        $createdTab = $tabs | Where-Object Name -eq $item.Name | Select-Object -First 1
        $position = $createdTab.Position
        while ($position -gt $item.Position) {
            $stage = "move $($item.Name)"
            Invoke-Zellij -Arguments @('--session', $session, 'action', 'move-tab',
                                      '--tab-id', [string]$createdTab.Id, 'left') | Out-Null
            $position--
        }
        $stage = "query after move $($item.Name)"
        $tabs = @(Get-WorkbenchTabs)
    }
    if ($original) {
        $tab = $tabs | Where-Object Name -eq $original | Select-Object -First 1
        if ($tab) {
            $stage = "restore $original"
            Invoke-Zellij -Arguments @('--session', $session, 'action', 'go-to-tab',
                                      [string]($tab.Position + 1)) | Out-Null
        }
    }
} catch {
    [Console]::Error.WriteLine("[$(Get-Date -Format o)] Workbench startup failed: session=$session stage=$stage`n$($_.Exception.Message)")
    exit 1
}
