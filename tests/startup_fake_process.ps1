# Test-only prefix. Production Process.Start is replaced exactly once by the driver.
$script:startupScenario = $env:STARTUP_TEST_SCENARIO
$script:startupListCount = 0
$script:startupTabs = @(
    @{Id=10;Position=0;Name='Work-Windows';Active=$false},
    @{Id=11;Position=1;Name='Work-for-Linux';Active=$true},
    @{Id=12;Position=2;Name='Monitor';Active=$false},
    @{Id=13;Position=3;Name='Music';Active=$false},
    @{Id=14;Position=4;Name='Control';Active=$false}
)
if ($script:startupScenario -in @('missing','newfail','movefail','create-timeout')) {
    $script:startupTabs[2].Name = 'Custom'
}
function Write-StartupTrace($Record) {
    [Console]::Error.WriteLine('@@TRACE@@' + ($Record | ConvertTo-Json -Compress))
}
function Start-Sleep {
    param([int]$Milliseconds)
    if ($Milliseconds -ne 400) { throw 'Unexpected sleep budget' }
    Write-StartupTrace @{type='sleep';milliseconds=$Milliseconds}
}
function New-StartupFakeProcess($Info) {
    $actionMatch = [regex]::Match($Info.Arguments, '"action" "([^"]+)"')
    if (-not $actionMatch.Success) { throw 'Unrecognized fake command' }
    $action = $actionMatch.Groups[1].Value
    Write-StartupTrace @{type='start';action=$action;arguments=$Info.Arguments}
    if ($script:startupScenario -eq 'startfail') { throw 'fake start failure' }
    $code = 0
    $output = ''
    $errorText = ''
    $waitResult = $true
    if ($action -eq 'list-tabs') {
        $script:startupListCount++
        if ($script:startupScenario -eq 'nativefail' -or
            ($script:startupScenario -eq 'recovery' -and $script:startupListCount -le 2)) {
            $code = 7
            $output = "ready-out-$script:startupListCount"
            $errorText = "ready-error-$script:startupListCount"
        } elseif ($script:startupScenario -eq 'empty') {
            $output = ''
        } elseif ($script:startupScenario -eq 'unparsed') {
            $output = 'not a tab row'
        } elseif ($script:startupScenario -eq 'timeout') {
            $waitResult = $false
        } else {
            $output = ($script:startupTabs | Sort-Object Position | ForEach-Object {
                '{0} {1} {2} {3} extra' -f $_.Id,$_.Position,$_.Name,([string]$_.Active).ToLower()
            }) -join "`n"
        }
    } elseif ($action -eq 'new-tab') {
        if ($script:startupScenario -eq 'newfail') { $code=7 }
        elseif ($script:startupScenario -eq 'create-timeout') { $waitResult=$false }
        else { $script:startupTabs += @{Id=15;Position=5;Name='Monitor';Active=$false} }
    } elseif ($action -eq 'move-tab') {
        if ($script:startupScenario -eq 'movefail') { $code=7 }
        else {
            $moving = $script:startupTabs | Where-Object Id -eq 15
            $left = $script:startupTabs | Where-Object Position -eq ($moving.Position - 1)
            $left.Position++
            $moving.Position--
        }
    } elseif ($action -eq 'go-to-tab') {
        if ($script:startupScenario -eq 'restorefail') { $code=7 }
    } else { throw "Unexpected action: $action" }
    if ($code -ne 0 -and $action -ne 'list-tabs') {
        $output = 'action-out'
        $errorText = 'action-error'
    }
    $fake = [pscustomobject]@{
        ExitCode=$code
        StandardOutput=[System.IO.StringReader]::new($output)
        StandardError=[System.IO.StringReader]::new($errorText)
        WaitResult=$waitResult
        Action=$action
    }
    $fake | Add-Member ScriptMethod WaitForExit {
        param($TimeoutMs)
        Write-StartupTrace @{type='wait';action=$this.Action;timeout=$TimeoutMs}
        return $this.WaitResult
    }
    $fake | Add-Member ScriptMethod Kill { Write-StartupTrace @{type='kill';action=$this.Action} }
    $fake | Add-Member ScriptMethod Dispose {
        $this.StandardOutput.Dispose()
        $this.StandardError.Dispose()
        Write-StartupTrace @{type='dispose';action=$this.Action}
    }
    return $fake
}
