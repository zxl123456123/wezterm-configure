param(
    [string]$Source = (Join-Path $PSScriptRoot '..\Start-WorkShell.ps1'),
    [string]$ToolRoot = 'D:\terminal-workbench\apps'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Run in Windows PowerShell 5.1' }
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([IO.Path]::GetPathRoot($repo) -ne 'D:\') { throw 'Tests require a D-drive checkout' }
$root = Join-Path $repo ('.validation\shell-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $root
$env:TEMP = $root; $env:TMP = $root
$code = [IO.File]::ReadAllText([IO.Path]::GetFullPath($Source), [Text.Encoding]::UTF8)
$fzf = Join-Path $ToolRoot 'fzf\fzf.exe'
$zoxide = Join-Path $ToolRoot 'zoxide\zoxide.exe'
foreach ($tool in @($fzf, $zoxide)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Missing test tool: $tool" }
}
Import-Module 'C:/Program Files/WindowsPowerShell/Modules/PSReadLine/2.0.0/PSReadLine.psd1'
Set-PSReadLineOption -HistorySaveStyle SaveNothing -HistorySavePath (Join-Path $root 'history.txt')
$env:FZF_DEFAULT_OPTS = $null; $env:FZF_DEFAULT_OPTS_FILE = $null
$env:_ZO_FZF_OPTS = $null; $env:_ZO_EXCLUDE_DIRS = $null; $env:_ZO_ECHO = $null
$checks = 0
function Assert-That($condition, $message) {
    if (-not $condition) { throw "FAIL: $message" }
    $script:checks++
    Write-Output "PASS: $message"
}
function Initialize-Fixture([string]$name, [bool]$tools = $true) {
    $base = Join-Path $root $name
    $default = Join-Path $base 'project'
    $null = New-Item -ItemType Directory -Path (Join-Path $base 'data'), $default -Force
    $text = $code.Replace('D:\terminal-workbench', $base).Replace('D:\workspace-for-everything', $default)
    if ($tools) {
        $text = $text.Replace((Join-Path $base 'apps\fzf\fzf.exe'), $fzf)
        $text = $text.Replace((Join-Path $base 'apps\zoxide\zoxide.exe'), $zoxide)
    }
    $global:LastSavedWorkbenchCwd = $null; $global:LastZoxideWorkbenchCwd = $null
    . ([scriptblock]::Create($text))
    return $base
}

$base = Initialize-Fixture 'normal'
Assert-That ((Get-Location).Path -eq (Join-Path $base 'project')) 'Missing cwd falls back to isolated default'
Assert-That ((Get-Module PSReadLine).Version.ToString() -eq '2.0.0') 'Existing PSReadLine 2.0.0 retained'
$keys = Get-PSReadLineKeyHandler -Bound
foreach ($entry in @(@('Tab','MenuComplete'), @('UpArrow','HistorySearchBackward'), @('DownArrow','HistorySearchForward'), @('F2','WorkbenchHistory'))) {
    Assert-That (@($keys | Where-Object { $_.Key -eq $entry[0] -and $_.Function -eq $entry[1] }).Count -eq 1) "Key binding $($entry[0]) -> $($entry[1])"
}
$esc = [string][char]27
$options = Get-PSReadLineOption
Assert-That ($options.CommandColor -eq ($esc + '[38;2;138;173;244m')) 'RGB command highlighting'
Assert-That ($options.SelectionColor -eq ($esc + '[38;2;202;211;245;48;2;73;77;100m')) 'Readable selection foreground and background'
Assert-That ($function:ai.ToString().Trim() -eq '& codex @args') 'AI remains on demand'
Assert-That ($function:prompt.ToString() -notmatch '__zoxide_prompt_old|__zoxide_hook') 'No upstream prompt wrapper'
$global:LASTEXITCODE = 37
$output = @(prompt)
Assert-That ($output.Count -eq 1 -and $output[0] -eq ('WIN ' + (Get-Location).Path + ' > ')) 'Prompt produces exactly one unchanged line'
Assert-That ($global:LASTEXITCODE -eq 37) 'Prompt preserves native command exit status'
$cwdFile = $global:WorkbenchCwdFile
$db = Join-Path $env:_ZO_DATA_DIR 'db.zo'
$cwdStamp = (Get-Item -LiteralPath $cwdFile).LastWriteTimeUtc
$dbHash = (Get-FileHash -LiteralPath $db).Hash
for ($i = 0; $i -lt 20; $i++) { $null = prompt }
Assert-That ((Get-Item -LiteralPath $cwdFile).LastWriteTimeUtc -eq $cwdStamp -and (Get-FileHash -LiteralPath $db).Hash -eq $dbHash) 'Repeated prompts do not rewrite cwd or relearn directory'
$unicode = [string][char]0x5F00 + [char]0x53D1
$target = Join-Path $base ('project space ' + $unicode)
$null = New-Item -ItemType Directory -Path $target
Set-Location -LiteralPath $target
$null = prompt
Assert-That ([IO.File]::ReadAllText($cwdFile, [Text.Encoding]::UTF8) -eq $target) 'Cwd memory handles spaces and Chinese'
Set-Location -LiteralPath (Join-Path $base 'project')
$null = prompt
$null = z $unicode
Assert-That ((Get-Location).Path -eq $target) 'Real zoxide keyword jump handles Chinese'
Set-Location -LiteralPath (Join-Path $base 'project')
$env:_ZO_FZF_OPTS = '--filter=' + $unicode
$null = zi $unicode
Assert-That ((Get-Location).Path -eq $target) 'Real zi selects from isolated database via fzf'
$env:_ZO_FZF_OPTS = '--filter=unmatched-workbench-fixture'
$expectedError = & { $ErrorActionPreference = 'Continue'; zi 'unmatched-workbench-fixture' 2>&1 }
Assert-That ("$expectedError" -match 'no match found') 'No-match zoxide reports its expected rejection'
Assert-That ((Get-Location).Path -eq $target) 'Cancelled/no-match zi keeps directory'
$env:_ZO_FZF_OPTS = $null
$null = prompt
$restored = Initialize-Fixture 'normal'
Assert-That ((Get-Location).Path -eq $target) 'Valid saved cwd is restored'
[IO.File]::WriteAllText($global:WorkbenchCwdFile, (Join-Path $base 'deleted'), [Text.Encoding]::UTF8)
$restored = Initialize-Fixture 'normal'
Assert-That ((Get-Location).Path -eq (Join-Path $base 'project')) 'Deleted saved directory falls back safely'

# Exercise the actual search body with synthetic editor state and real fzf.
# No real history is loaded, displayed, accepted or executed by this fixture.
Add-Type -TypeDefinition @'
public class WorkbenchHistoryItem { public string CommandLine; }
public static class WorkbenchTestReadLine {
    public static string Buffer = "";
    public static int Cursor, Redraws, Reverts, Inserts;
    public static WorkbenchHistoryItem[] History;
    public static void GetBufferState(ref string line, ref int cursor) { line = Buffer; cursor = Cursor; }
    public static WorkbenchHistoryItem[] GetHistoryItems() { return History; }
    public static void InvokePrompt() { Redraws++; }
    public static void RevertLine() { Reverts++; Buffer = ""; }
    public static void Insert(string text) { Inserts++; Buffer = text; }
}
'@
$body = ${function:Search-WorkbenchHistory}.ToString().Replace('Microsoft.PowerShell.PSConsoleReadLine', 'WorkbenchTestReadLine')
$search = [scriptblock]::Create($body)
$marker = Join-Path $root 'must-not-execute.txt'
$dangerous = "[IO.File]::WriteAllText('$marker','executed')"
$commands = @("Write-Output '$unicode'", $dangerous, "Write-Output first`nWrite-Output second")
[WorkbenchTestReadLine]::History = @($commands | ForEach-Object { $item = New-Object WorkbenchHistoryItem; $item.CommandLine = $_; $item })
[WorkbenchTestReadLine]::Buffer = 'original input'; [WorkbenchTestReadLine]::Cursor = 4
$encoding = [Console]::OutputEncoding
$pipeEncoding = $global:OutputEncoding
$env:FZF_DEFAULT_OPTS = '--filter=' + $unicode
& $search
Assert-That ([WorkbenchTestReadLine]::Buffer -eq $commands[0]) 'F2 inserts exact Chinese selection through real fzf'
Assert-That ([Console]::OutputEncoding.CodePage -eq $encoding.CodePage) 'Search restores console encoding'
Assert-That ($global:OutputEncoding.CodePage -eq $pipeEncoding.CodePage) 'Search restores native-pipe encoding'
$env:FZF_DEFAULT_OPTS = '--filter=WriteAllText'
& $search
Assert-That ([WorkbenchTestReadLine]::Buffer -eq $dangerous -and -not (Test-Path -LiteralPath $marker)) 'Selection inserts but never executes a command'
[WorkbenchTestReadLine]::Buffer = 'keep this'; [WorkbenchTestReadLine]::Cursor = 2
$env:FZF_DEFAULT_OPTS = '--filter=unmatched-workbench-fixture'
& $search
Assert-That ([WorkbenchTestReadLine]::Buffer -eq 'keep this' -and [WorkbenchTestReadLine]::Cursor -eq 2) 'F2 cancellation preserves input and cursor'
$env:FZF_DEFAULT_OPTS = '--filter=second'
& $search
Assert-That ([WorkbenchTestReadLine]::Buffer -eq 'keep this') 'Multiline history is not split into partial commands'
Assert-That ([WorkbenchTestReadLine]::Redraws -eq 4 -and [WorkbenchTestReadLine]::Inserts -eq 2) 'One redraw per native search; no polling or accept loop'
[WorkbenchTestReadLine]::History = @()
& $search
Assert-That ([WorkbenchTestReadLine]::Redraws -eq 4) 'Empty history leaves editor untouched'
$env:FZF_DEFAULT_OPTS = $null
Remove-PSReadLineKeyHandler -Key F2
Remove-Item Alias:z, Alias:zi, Alias:zoxide -ErrorAction SilentlyContinue
$missing = Initialize-Fixture 'without-tools' $false
$output = @(prompt)
Assert-That ($output.Count -eq 1 -and $output[0] -eq ('WIN ' + (Join-Path $missing 'project') + ' > ')) 'Optional tools absent: basic shell and cwd memory still work'
Assert-That (@(Get-PSReadLineKeyHandler -Bound | Where-Object Key -eq 'F2').Count -eq 0) 'Optional fzf absent: no F2 binding installed'
Write-Output ("RESULT: {0} assertions passed; PowerShell {1}; isolated root {2}" -f $checks, $PSVersionTable.PSVersion, $root)
