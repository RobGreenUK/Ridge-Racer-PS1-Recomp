# Own the Process handle directly. Start-Process -PassThru with redirected
# output can lose ExitCode on Windows, even after WaitForExit (PowerShell #5421).
function ConvertTo-GameArgument([string]$value) {
    # CommandLineToArgvW / C runtime quoting, including embedded quotes and
    # trailing backslashes. Works with Windows PowerShell 5.1's Arguments field.
    return '"' + [regex]::Replace([regex]::Replace($value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Start-GameProcess($file, $arguments, $log) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    if ([IO.Path]::IsPathRooted($file)) { $info.FileName = $file } else { $info.FileName = Join-Path $root $file }
    $info.Arguments = ($arguments | ForEach-Object { ConvertTo-GameArgument ([string]$_) }) -join ' '
    $info.WorkingDirectory = $root
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $child = New-Object System.Diagnostics.Process
    $child.StartInfo = $info
    $stdout = $null; $stderr = $null; $started = $false
    try {
        $stdout = [IO.File]::Open("$log.stdout.log", [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        $stderr = [IO.File]::Open("$log.stderr.log", [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        $started = $child.Start()
        if (!$started) { throw "Could not start $file" }
        # Drain both pipes asynchronously without PowerShell callbacks/runspaces.
        # This avoids deadlock when a child writes more than one pipe buffer.
        $child | Add-Member -NotePropertyName RidgeStdout -NotePropertyValue $stdout
        $child | Add-Member -NotePropertyName RidgeStderr -NotePropertyValue $stderr
        $child | Add-Member -NotePropertyName RidgeStdoutCopy -NotePropertyValue ($child.StandardOutput.BaseStream.CopyToAsync($stdout))
        $child | Add-Member -NotePropertyName RidgeStderrCopy -NotePropertyValue ($child.StandardError.BaseStream.CopyToAsync($stderr))
        return $child
    } catch {
        if ($started -and !$child.HasExited) { $child.Kill(); $child.WaitForExit() }
        if ($null -ne $stdout) { $stdout.Dispose() }
        if ($null -ne $stderr) { $stderr.Dispose() }
        $child.Dispose()
        throw
    }
}

function Complete-GameProcess($child) {
    if ($null -eq $child) { return }
    try {
        if (!$child.HasExited) { $child.Kill() }
        $child.WaitForExit()
        [void]$child.RidgeStdoutCopy.GetAwaiter().GetResult()
        [void]$child.RidgeStderrCopy.GetAwaiter().GetResult()
    } finally {
        $child.RidgeStdout.Dispose()
        $child.RidgeStderr.Dispose()
        $child.Dispose()
    }
}

function Assert-GameExit($child, [string]$name) {
    # Do not coerce an unknown result to zero: genuine failures must still stop.
    $code = $child.ExitCode
    if ($null -eq $code) { throw "$name did not report an exit code." }
    if ($code -ne 0) { throw "$name exited with code $code." }
}
