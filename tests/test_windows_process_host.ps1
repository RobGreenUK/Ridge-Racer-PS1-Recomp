$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../launcher/windows/ProcessHost.ps1')
$root = Join-Path ([IO.Path]::GetTempPath()) ('ridge process test '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
$runner = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
$childScript=Join-Path $root 'child fixture.ps1'
@'
param([int]$Code=0,[int]$Sleep=0,[int]$Size=0,[string]$Echo='')
if($Sleep){Start-Sleep -Seconds $Sleep}
[Console]::Out.WriteLine('stdout: '+$Echo)
[Console]::Error.WriteLine('stderr: fixture')
if($Size){[Console]::Out.Write(('x' * $Size));[Console]::Error.Write(('y' * $Size))}
exit $Code
'@ | Set-Content -LiteralPath $childScript -Encoding UTF8
$child=$null
try {
    # Rapid exits are the failure mode reported by the Windows startup check.
    for($i=0;$i -lt 8;$i++){
        $child=Start-GameProcess $runner @('-NoProfile','-File',$childScript) (Join-Path $root "fast-$i")
        if(!$child.WaitForExit(10000)){throw 'Fast child timed out'}
        Assert-GameExit $child 'Successful child'
        Complete-GameProcess $child;$child=$null
    }
    $log=Join-Path $root 'failure'
    $child=Start-GameProcess $runner @('-NoProfile','-File',$childScript,'-Code','7') $log
    if(!$child.WaitForExit(10000)){throw 'Failing child timed out'}
    $rejected=$false
    try {Assert-GameExit $child 'Failure fixture'} catch {if($_.Exception.Message -notlike '*code 7*'){throw};$rejected=$true}
    if(!$rejected){throw 'Nonzero exit was accepted'}
    Complete-GameProcess $child;$child=$null
    if((Get-Content -Raw "$log.stderr.log") -notmatch 'stderr: fixture'){throw 'Failure stderr missing'}
    $rejected=$false
    try {Assert-GameExit ([pscustomobject]@{ExitCode=$null}) 'Unknown fixture'} catch {$rejected=$true}
    if(!$rejected){throw 'Unknown exit was accepted'}
    # Large output on both streams must not block; complex arguments round-trip.
    $echo='spaces and "quotes" and trailing slash\'
    $log=Join-Path $root 'large'
    $child=Start-GameProcess $runner @('-NoProfile','-File',$childScript,'-Size','200000','-Echo',$echo) $log
    if(!$child.WaitForExit(10000)){throw 'Pipe drain deadlocked'}
    Assert-GameExit $child 'Large output child'
    Complete-GameProcess $child;$child=$null
    if(!(Get-Content -Raw "$log.stdout.log").Contains($echo)){throw 'Argument quoting failed'}
    if((Get-Item "$log.stdout.log").Length -lt 200000 -or (Get-Item "$log.stderr.log").Length -lt 200000){throw 'Logs truncated'}
    $child=Start-GameProcess $runner @('-NoProfile','-File',$childScript,'-Sleep','60') (Join-Path $root 'timeout')
    if($child.WaitForExit(20)){throw 'Sleep fixture exited unexpectedly'}
    $ownedId=$child.Id
    Complete-GameProcess $child;$child=$null
    if(Get-Process -Id $ownedId -ErrorAction SilentlyContinue){throw 'Owned process survived cleanup'}
    'PASS: fast success, failed/unknown exit, stdout/stderr draining, argument quoting and timeout cleanup.'
} finally {
    if($null -ne $child){Complete-GameProcess $child}
    Remove-Item -LiteralPath $root -Recurse -Force
}
