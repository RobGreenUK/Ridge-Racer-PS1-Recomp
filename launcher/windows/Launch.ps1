$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$created=$false
$launchMutex=New-Object System.Threading.Mutex($true,'Local\RidgeRacerWindowsTest',[ref]$created)
if(!$created){[System.Windows.Forms.MessageBox]::Show('Ridge Racer is already running. Close it before launching again.') | Out-Null;exit}
$root = $PSScriptRoot
Set-Location -LiteralPath $root
. (Join-Path $root 'ProcessHost.ps1')
$configPath = Join-Path $root 'launcher-settings.json'
$settings = @{ Aspect='16:9'; Resolution='1920 x 1080'; FPS='Match display'; Fullscreen=$true; VSync=$true; Perspective=$true; FullScene=$true; Graph=$false; Renderer='Enhanced'; LowLatency=$true }
if (Test-Path $configPath) {
    try { $saved = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json; foreach($key in @($settings.Keys)) { if($null -ne $saved.$key){$settings[$key]=$saved.$key} } } catch {}
}
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Ridge Racer - Windows test build'
$form.ClientSize = New-Object System.Drawing.Size(480,540)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object System.Drawing.Font('Segoe UI',10)
function Add-Choice($label,$items,$selected,$y) {
    $l=New-Object System.Windows.Forms.Label; $l.Text=$label; $l.SetBounds(22,$y+4,170,25); $form.Controls.Add($l)
    $c=New-Object System.Windows.Forms.ComboBox; $c.DropDownStyle='DropDownList'; $c.SetBounds(200,$y,250,28)
    $c.Items.AddRange([object[]]$items); $c.SelectedItem=$selected; if($c.SelectedIndex -lt 0){$c.SelectedIndex=0}; $form.Controls.Add($c); return $c
}
$renderer=Add-Choice 'Renderer' @('Enhanced','Original') $settings.Renderer 20
$aspect=Add-Choice 'Aspect ratio' @('4:3','16:9') $settings.Aspect 62
$resolution=Add-Choice 'Render resolution' @($settings.Resolution) $settings.Resolution 104
function Update-Resolutions {
    $old=$resolution.Text; $resolution.Items.Clear()
    if($aspect.Text -eq '4:3'){$options=@('960 x 720','1440 x 1080','1920 x 1440','2880 x 2160')}else{$options=@('1280 x 720','1920 x 1080','2560 x 1440','3840 x 2160')}
    $resolution.Items.AddRange([object[]]$options); $resolution.SelectedItem=$old; if($resolution.SelectedIndex -lt 0){$resolution.SelectedIndex=1}
}
Update-Resolutions
$aspect.Add_SelectedIndexChanged({Update-Resolutions})
$fps=Add-Choice 'Frame-rate target' @('Match display','60','75','90','120','144','165','240') $settings.FPS 146
function Add-Check($text,$checked,$y){$c=New-Object System.Windows.Forms.CheckBox;$c.Text=$text;$c.Checked=[bool]$checked;$c.SetBounds(22,$y,430,28);$form.Controls.Add($c);return $c}
$fullscreen=Add-Check 'Fullscreen' $settings.Fullscreen 195
$vsync=Add-Check 'Synchronise with display (V-sync)' $settings.VSync 228
$perspective=Add-Check 'Perspective-correct textures' $settings.Perspective 261
$fullScene=Add-Check 'Render full course and all cars' $settings.FullScene 294
$graph=Add-Check 'Developer frame-time graph (G toggles)' $settings.Graph 327
$lowLatency=Add-Check 'Low latency input sampling' $settings.LowLatency 360
$help=New-Object System.Windows.Forms.Label;$help.Text='Enter: Start | Arrows: steer | X / Space: accelerate | Z: brake' + "`n" + 'P: capture issue | G: graph | Esc: close';$help.SetBounds(22,400,440,50);$form.Controls.Add($help)
$play=New-Object System.Windows.Forms.Button;$play.Text='Save and play';$play.SetBounds(285,477,165,38);$play.DialogResult='OK';$form.Controls.Add($play);$form.AcceptButton=$play
if($form.ShowDialog() -ne 'OK'){exit}
$settings=@{Aspect=$aspect.Text;Resolution=$resolution.Text;FPS=$fps.Text;Fullscreen=$fullscreen.Checked;VSync=$vsync.Checked;Perspective=$perspective.Checked;FullScene=$fullScene.Checked;Graph=$graph.Checked;Renderer=$renderer.Text;LowLatency=$lowLatency.Checked}
$settings | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
$form.Dispose()
$scene=$null;$game=$null;$check=$null;$session=$null;$recording=$null;$stage='Preparing settings'
try {
    $dimensions=$settings.Resolution -split ' x ';$width=[int]$dimensions[0];$height=[int]$dimensions[1]
    $native=$settings.Renderer -eq 'Enhanced';$target=0;if($settings.FPS -ne 'Match display'){$target=[int]$settings.FPS}
    $runtimeFullscreen=0;if(!$native -and $settings.Fullscreen){$runtimeFullscreen=1}
    $runtimeWidth=640;if(!$native){$runtimeWidth=$width}
    $sync='off';if($settings.VSync){$sync='on'}
    $correct=$settings.Perspective.ToString().ToLowerInvariant();$latency=$settings.LowLatency.ToString().ToLowerInvariant()
    @"
[video]
renderer = "opengl"
fullscreen = $runtimeFullscreen
window_width = $runtimeWidth
supersampling = 1
aspect_ratio = "$($settings.Aspect)"
vsync = "$sync"
perspective_texturing = $correct
low_latency_input = $latency
frame_interpolation = false
frame_interpolation_fps = 0
"@ | Set-Content -LiteralPath (Join-Path $root 'settings.toml') -Encoding ASCII
    $wide=($settings.Aspect -eq '16:9').ToString().ToLowerInvariant()
    @"
format_version = 2
package = [{id = "ridge.presentation", version = "1.0.0"}]
feature = [{package_id = "ridge.presentation", id = "view", enabled = $wide, values = {mode = "wide"}}, {package_id = "ridge.presentation", id = "motion", enabled = false, values = {target = "0"}}]
"@ | Set-Content -LiteralPath (Join-Path $root 'mods\state.toml') -Encoding ASCII
    $cue=Join-Path $root 'Ridge Racer (USA)\Ridge Racer (USA).cue'
    if(!(Test-Path -LiteralPath $cue)){throw "Game disc files are missing: $cue"}
    $env:RIDGERACERRECOMP_BUILD_DIR=$root
    $env:SDL_RENDER_DRIVER='opengl'
    foreach($name in @('RIDGE_PHYSICS_ENGINE','RIDGE_PHYSICS_TRACE','RIDGE_PHYSICS_SHADOW','RIDGE_PHYSICS_CAPTURE','RIDGE_INPUT_REPLAY','RIDGE_SCENE_CAPTURE','RIDGE_TEST_DRIVE','RIDGE_TEST_SPEED','RIDGE_NATIVE_SCENE','RIDGE_SCENE_SOCKET','RIDGE_SCENE_INPUT')){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
    $recording=Join-Path $root ('diagnostics\'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Path $recording | Out-Null
    $recorded=@{nativeWidth=$width;nativeHeight=$height;nativeFps=$target;vsync=$sync;fullscreen=[int]$settings.Fullscreen;nativeScene=$native;aspect=$settings.Aspect;frameGraph=$settings.Graph;nativeFullCourse=$settings.FullScene;perspective=$settings.Perspective}
    $recorded | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $recording 'settings.json') -Encoding ASCII
    $env:PSX_HIDDEN_COMPANION='0'
    if($native){
        $env:PSX_HIDDEN_COMPANION='1'
        $session=Join-Path ([IO.Path]::GetTempPath()) ('ridge-'+[guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $session | Out-Null
        $stage='Checking scene transport'
        $check=Start-GameProcess 'RidgeTransportCheck.exe' @((Join-Path $session 'check')) (Join-Path $recording 'transport-check')
        if(!$check.WaitForExit(10000)){$check.Kill();throw 'Scene transport check timed out.'}
        Assert-GameExit $check 'Scene transport check'
        Complete-GameProcess $check; $check=$null
        $endpoint=Join-Path $session 'scene'
        $env:RIDGE_SCENE_SOCKET=$endpoint;$env:RIDGE_NATIVE_SCENE='1';$env:RIDGE_SCENE_INPUT='1'
        $env:RIDGE_SCENE_FULL_COURSE='0';if($settings.FullScene){$env:RIDGE_SCENE_FULL_COURSE='1'}
        $env:RIDGE_SCENE_CAR_DISTANCE='0'
        $arguments=@('--live',$endpoint,'--assets',(Join-Path $root 'native-scene\course.rrassets'),'--metrics',(Join-Path $recording 'frames.csv'),'--game-camera','--control','--fps',"$target",'--vsync',$sync,'--width',"$width",'--height',"$height")
        if($settings.Fullscreen){$arguments+='--fullscreen'}
        if($settings.Graph){$arguments+='--frame-graph'}
        if(!$settings.Perspective){$arguments+='--affine-textures'}
        if(!$settings.FullScene){$arguments+='--legacy-distance'}
        $stage='Starting enhanced renderer'
        $scene=Start-GameProcess 'RidgeScenePreview.exe' $arguments (Join-Path $recording 'renderer')
        $deadline=[DateTime]::UtcNow.AddSeconds(15)
        while(!(Test-Path -LiteralPath $endpoint)){
            if($scene.HasExited -or [DateTime]::UtcNow -gt $deadline){throw 'Enhanced renderer failed to start. See the diagnostics folder.'}
            Start-Sleep -Milliseconds 30
        }
    }
    $stage='Starting game engine'
    $game=Start-GameProcess 'RidgeRacer_Recompiled.exe' @('--game',(Join-Path $root 'game.toml'),'--disc',$cue,'--no-launcher') (Join-Path $recording 'engine')
    $stage='Running game'
    while(!$game.HasExited -and ($null -eq $scene -or !$scene.HasExited)){Start-Sleep -Milliseconds 100}
    if($game.HasExited){Assert-GameExit $game 'Game engine'}
    if($null -ne $scene -and $scene.HasExited){Assert-GameExit $scene 'Enhanced renderer'}
} catch {
    $detail="Stage: $stage`r`n$($_ | Out-String)`r`n$($_.ScriptStackTrace)"
    $errorPath=Join-Path $root 'launcher-error.log'
    $detail | Set-Content -LiteralPath $errorPath -Encoding UTF8
    if($null -ne $recording){$detail | Set-Content -LiteralPath (Join-Path $recording 'launcher-error.log') -Encoding UTF8}
    [System.Windows.Forms.MessageBox]::Show("$($_.Exception.Message)`r`n`r`nDetails saved to $errorPath",'Ridge Racer launch error') | Out-Null
} finally {
    foreach($process in @($check,$game,$scene)){
        try { Complete-GameProcess $process } catch { $_ | Out-String | Add-Content -LiteralPath (Join-Path $root 'launcher-error.log') }
    }
    if($null -ne $session -and (Test-Path -LiteralPath $session)){Remove-Item -LiteralPath $session -Recurse -Force}
}
