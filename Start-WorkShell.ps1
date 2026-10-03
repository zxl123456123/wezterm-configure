$global:WorkbenchCwdFile = 'D:\terminal-workbench\data\work-windows-shell.cwd'
$fallback = 'D:\workspace-for-everything'
if (Test-Path -LiteralPath $global:WorkbenchCwdFile -PathType Leaf) {
    $candidate = [System.IO.File]::ReadAllText($global:WorkbenchCwdFile,
                                                [System.Text.Encoding]::UTF8).Trim()
    if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
        $fallback = $candidate
    }
}
Set-Location -LiteralPath $fallback

$global:WorkbenchFzfPath = 'D:\terminal-workbench\apps\fzf\fzf.exe'
$global:WorkbenchZoxidePath = 'D:\terminal-workbench\apps\zoxide\zoxide.exe'
if (Test-Path -LiteralPath $global:WorkbenchFzfPath -PathType Leaf) {
    $fzfDir = Split-Path -Parent $global:WorkbenchFzfPath
    if (($env:PATH -split ';') -notcontains $fzfDir) { $env:PATH = $fzfDir + ';' + $env:PATH }
}
if (Test-Path -LiteralPath $global:WorkbenchZoxidePath -PathType Leaf) {
    $env:_ZO_DATA_DIR = 'D:\terminal-workbench\data\zoxide'
    Set-Alias -Name zoxide -Value $global:WorkbenchZoxidePath -Scope Global
    # Use upstream commands without its prompt wrapper: keep one prompt owner.
    Invoke-Expression (& $global:WorkbenchZoxidePath init powershell --hook none | Out-String)
}

# Search is on demand and only inserts a selected single-line command.
function global:Search-WorkbenchHistory {
    $line = ''; $cursor = 0
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    $history = @([Microsoft.PowerShell.PSConsoleReadLine]::GetHistoryItems() |
        ForEach-Object { $_.CommandLine } |
        Where-Object { $_ -and $_ -notmatch '[\r\n]' })
    if ($history.Count -eq 0) { return }
    $encoding = [Console]::OutputEncoding
    $pipeEncoding = $global:OutputEncoding
    try {
        # PowerShell 5.1 native pipes ignore a function-local OutputEncoding.
        $global:OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        [Console]::OutputEncoding = $global:OutputEncoding
        $selected = $history | & $global:WorkbenchFzfPath --height=50% --layout=reverse --border --tac --no-sort --no-multi "--query=$line" '--prompt=History > ' '--color=fg:#cad3f5,bg:#24273a,hl:#8aadf4,fg+:#cad3f5,bg+:#494d64,hl+:#a6da95,pointer:#f5bde6,border:#c6a0f6'
        $searchExitCode = $LASTEXITCODE
        # Redraw once after the native UI, including cancellation; never accept.
        [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
        if ($searchExitCode -eq 0 -and $selected -is [string] -and $selected.Length -gt 0) {
            [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
            [Microsoft.PowerShell.PSConsoleReadLine]::Insert($selected)
        }
    } finally {
        $global:OutputEncoding = $pipeEncoding
        [Console]::OutputEncoding = $encoding
    }
}

# PowerShell 5.1 + Zellij did not reliably render PSReadLine 2.4 predictions.
# Use the shell's built-in line editor instead of forcing a newer module here.
if (-not (Get-Module -Name PSReadLine) -and
    (Test-Path -LiteralPath 'C:/Program Files/WindowsPowerShell/Modules/PSReadLine/2.0.0/PSReadLine.psd1')) {
    Import-Module 'C:/Program Files/WindowsPowerShell/Modules/PSReadLine/2.0.0/PSReadLine.psd1'
}
if (Get-Module -Name PSReadLine) {
    Set-PSReadLineOption -Colors @{
        Command = '#8aadf4'; Parameter = '#c6a0f6'; String = '#a6da95'
        Number = '#eed49f'; Comment = '#939ab7'; Keyword = '#c6a0f6'
        Operator = '#91d7e3'; Variable = '#f5bde6'; Type = '#8bd5ca'
        Error = '#ed8796'
        Selection = ([string][char]27 + '[38;2;202;211;245;48;2;73;77;100m')
    }
    Set-PSReadLineKeyHandler -Key Tab -Function MenuComplete
    Set-PSReadLineKeyHandler -Key UpArrow -Function HistorySearchBackward
    Set-PSReadLineKeyHandler -Key DownArrow -Function HistorySearchForward
    if (Test-Path -LiteralPath $global:WorkbenchFzfPath -PathType Leaf) {
        Set-PSReadLineKeyHandler -Key F2 -BriefDescription WorkbenchHistory -ScriptBlock {
            Search-WorkbenchHistory
        }
    }
}

# On-demand AI coding helper; no agent process runs until the user types ai.
function global:ai { & codex @args }

function global:prompt {
    $location = Get-Location
    if ($location.Provider.Name -eq 'FileSystem') {
        if ($global:LastSavedWorkbenchCwd -ne $location.ProviderPath) {
            try {
                [System.IO.File]::WriteAllText($global:WorkbenchCwdFile,
                                               $location.ProviderPath,
                                               (New-Object System.Text.UTF8Encoding($false)))
                $global:LastSavedWorkbenchCwd = $location.ProviderPath
            } catch { }
        }
        if ($global:LastZoxideWorkbenchCwd -ne $location.ProviderPath -and
            (Test-Path -LiteralPath $global:WorkbenchZoxidePath -PathType Leaf)) {
            $previousExitCode = $global:LASTEXITCODE
            try {
                $null = & $global:WorkbenchZoxidePath add -- $location.ProviderPath
                $global:LastZoxideWorkbenchCwd = $location.ProviderPath
            } finally { $global:LASTEXITCODE = $previousExitCode }
        }
    }
    return ('WIN ' + $location.Path + ' > ')
}
