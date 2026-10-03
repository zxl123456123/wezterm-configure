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

# PowerShell 5.1 + Zellij did not reliably render PSReadLine 2.4 predictions.
# Use the shell's built-in line editor instead of forcing a newer module here.
if (-not (Get-Module -Name PSReadLine) -and
    (Test-Path -LiteralPath 'C:/Program Files/WindowsPowerShell/Modules/PSReadLine/2.0.0/PSReadLine.psd1')) {
    Import-Module 'C:/Program Files/WindowsPowerShell/Modules/PSReadLine/2.0.0/PSReadLine.psd1'
}
if (Get-Module -Name PSReadLine) {
    Set-PSReadLineOption -Colors @{
        Command = 'Cyan'; Parameter = 'Magenta'; String = 'Green'
        Number = 'Yellow'; Comment = 'DarkGray'; Keyword = 'Magenta'
        Operator = 'Cyan'; Variable = 'Yellow'; Type = 'Green'
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
    }
    return ('WIN ' + $location.Path + ' > ')
}
