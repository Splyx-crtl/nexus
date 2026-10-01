# NEXUS // TERMINAL - Windows installer (runs from the self-extracting NEXUS-Setup.exe)
# Usage (silent): install.ps1 -Silent -InstallDir "C:\Games\NEXUS" [-NoDesktopShortcut] [-NoLaunch]
param(
    [switch]$Silent,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\NEXUS"),
    [switch]$NoDesktopShortcut,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
# Updating: default to the folder of the existing installation (found via the uninstall entry)
if (-not $PSBoundParameters.ContainsKey("InstallDir")) {
    $existing = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXUS" -ErrorAction SilentlyContinue).InstallLocation
    if ($existing -and (Test-Path $existing)) { $InstallDir = $existing }
}
$AppName = "NEXUS // TERMINAL"
$Version = "__VERSION__"
$Zip = Join-Path $PSScriptRoot "NEXUS-app.zip"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXUS"

function New-Shortcut([string]$Path, [string]$Target, [string]$WorkDir, [string]$Description) {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut($Path)
    $lnk.TargetPath = $Target
    $lnk.WorkingDirectory = $WorkDir
    $lnk.Description = $Description
    $lnk.IconLocation = "$Target,0"
    $lnk.Save()
}

function Install-Nexus([string]$Dest, [bool]$Desktop, [scriptblock]$Report) {
    if (-not (Test-Path $Zip)) { throw "Installer payload NEXUS-app.zip not found." }
    & $Report "Preparing files..."
    $tmp = Join-Path $env:TEMP ("nexus_setup_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        & $Report "Extracting NEXUS..."
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($Zip, $tmp)
        New-Item -ItemType Directory -Force -Path $Dest | Out-Null
        & $Report "Copying to $Dest ..."
        # /E copies everything; existing saves in $Dest are never touched (the payload contains none)
        $null = & robocopy $tmp $Dest /E /NFL /NDL /NJH /NJS /NC /NS /NP
        if ($LASTEXITCODE -ge 8) { throw "File copy failed (robocopy exit code $LASTEXITCODE)." }
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $Dest "saves") | Out-Null
    $exe = Join-Path $Dest "NEXUS.exe"

    & $Report "Creating shortcuts..."
    $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
    New-Shortcut (Join-Path $startMenu "NEXUS.lnk") $exe $Dest "NEXUS // TERMINAL - Tactical Cyber Operations"
    if ($Desktop) {
        New-Shortcut (Join-Path ([Environment]::GetFolderPath("Desktop")) "NEXUS.lnk") $exe $Dest "NEXUS // TERMINAL"
    }

    & $Report "Registering uninstaller..."
    Copy-Item (Join-Path $PSScriptRoot "uninstall.ps1") (Join-Path $Dest "uninstall.ps1") -Force
    $uninstallCmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $Dest 'uninstall.ps1')`""
    New-Item -Path $UninstallKey -Force | Out-Null
    $props = @{
        DisplayName = $AppName; DisplayVersion = $Version; Publisher = "Toto"; InstallLocation = $Dest
        DisplayIcon = $exe; UninstallString = $uninstallCmd; NoModify = 1; NoRepair = 1
    }
    foreach ($k in $props.Keys) { New-ItemProperty -Path $UninstallKey -Name $k -Value $props[$k] -Force | Out-Null }
    & $Report "Done."
    return $exe
}

if ($Silent) {
    $exe = Install-Nexus $InstallDir (-not $NoDesktopShortcut) { param($m) Write-Host $m }
    if (-not $NoLaunch) { Start-Process $exe -WorkingDirectory (Split-Path $exe) }
    exit 0
}

# ------------------------------------------------------------------ GUI wizard
# hide the console window that hosts this script (the WinForms window stays visible)
Add-Type -Name Win -Namespace Native -MemberDefinition '[DllImport("kernel32.dll")] public static extern IntPtr GetConsoleWindow(); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);'
[void][Native.Win]::ShowWindow([Native.Win]::GetConsoleWindow(), 0)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$bg = [System.Drawing.ColorTranslator]::FromHtml("#05100f")
$panel = [System.Drawing.ColorTranslator]::FromHtml("#0a1a1c")
$green = [System.Drawing.ColorTranslator]::FromHtml("#00ff9c")
$cyan = [System.Drawing.ColorTranslator]::FromHtml("#22d3ee")
$dim = [System.Drawing.ColorTranslator]::FromHtml("#6fa89a")
$mono = New-Object System.Drawing.Font("Consolas", 10)

$form = New-Object System.Windows.Forms.Form
$form.Text = "NEXUS Setup"
$form.ClientSize = New-Object System.Drawing.Size(560, 380)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = $bg
$form.ForeColor = $green
$form.Font = $mono
$iconPath = Join-Path $PSScriptRoot "nexus.ico"
if (Test-Path $iconPath) { $form.Icon = New-Object System.Drawing.Icon($iconPath) }

function Add-Label($text, $x, $y, $w, $h, $color, $size, $bold) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text; $l.Location = New-Object System.Drawing.Point($x, $y); $l.Size = New-Object System.Drawing.Size($w, $h)
    $l.ForeColor = $color
    $style = if ($bold) { [System.Drawing.FontStyle]::Bold } else { [System.Drawing.FontStyle]::Regular }
    $l.Font = New-Object System.Drawing.Font("Consolas", $size, $style)
    $form.Controls.Add($l)
    return $l
}

$null = Add-Label "NEXUS" 24 18 300 44 $green 26 $true
$null = Add-Label "TACTICAL CYBER OPERATIONS  -  v$Version" 26 64 500 20 $cyan 9 $false
$null = Add-Label "Install location:" 26 112 300 20 $dim 9 $false

$path = New-Object System.Windows.Forms.TextBox
$path.Text = $InstallDir; $path.Location = New-Object System.Drawing.Point(26, 136); $path.Size = New-Object System.Drawing.Size(400, 26)
$path.BackColor = $panel; $path.ForeColor = $green; $path.BorderStyle = "FixedSingle"
$form.Controls.Add($path)

$browse = New-Object System.Windows.Forms.Button
$browse.Text = "Browse..."; $browse.Location = New-Object System.Drawing.Point(436, 134); $browse.Size = New-Object System.Drawing.Size(98, 28)
$browse.FlatStyle = "Flat"; $browse.ForeColor = $green; $browse.BackColor = $panel
$browse.Add_Click({
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($fb.ShowDialog() -eq "OK") { $path.Text = Join-Path $fb.SelectedPath "NEXUS" }
})
$form.Controls.Add($browse)

$chkDesktop = New-Object System.Windows.Forms.CheckBox
$chkDesktop.Text = "Create a desktop shortcut"; $chkDesktop.Checked = $true
$chkDesktop.Location = New-Object System.Drawing.Point(26, 182); $chkDesktop.Size = New-Object System.Drawing.Size(400, 24); $chkDesktop.ForeColor = $green
$form.Controls.Add($chkDesktop)

$chkLaunch = New-Object System.Windows.Forms.CheckBox
$chkLaunch.Text = "Launch NEXUS when setup finishes"; $chkLaunch.Checked = $true
$chkLaunch.Location = New-Object System.Drawing.Point(26, 210); $chkLaunch.Size = New-Object System.Drawing.Size(400, 24); $chkLaunch.ForeColor = $green
$form.Controls.Add($chkLaunch)

$null = Add-Label "Everything in NEXUS is a simulation. The game never touches real networks." 26 246 520 20 $dim 8 $false

$status = Add-Label "Ready to install." 26 284 500 22 $cyan 9 $false
$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(26, 310); $bar.Size = New-Object System.Drawing.Size(508, 14); $bar.Style = "Continuous"
$form.Controls.Add($bar)

$install = New-Object System.Windows.Forms.Button
$install.Text = "Install"; $install.Location = New-Object System.Drawing.Point(318, 336); $install.Size = New-Object System.Drawing.Size(104, 32)
$install.FlatStyle = "Flat"; $install.ForeColor = $green; $install.BackColor = $panel
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = "Cancel"; $cancel.Location = New-Object System.Drawing.Point(430, 336); $cancel.Size = New-Object System.Drawing.Size(104, 32)
$cancel.FlatStyle = "Flat"; $cancel.ForeColor = [System.Drawing.ColorTranslator]::FromHtml("#ff3860"); $cancel.BackColor = $panel
$cancel.Add_Click({ $form.Close() })
$form.Controls.Add($install)
$form.Controls.Add($cancel)

$script:installed = $null
$install.Add_Click({
    $install.Enabled = $false; $browse.Enabled = $false; $path.Enabled = $false
    try {
        $steps = 0
        $report = { param($m) $status.Text = $m; $script:steps++; $bar.Value = [Math]::Min(95, 15 * $script:steps); [System.Windows.Forms.Application]::DoEvents() }
        $running = Get-Process -Name NEXUS -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$($path.Text)*" }
        if ($running) { throw "NEXUS is currently running. Please close it and try again." }
        $script:installed = Install-Nexus $path.Text $chkDesktop.Checked $report
        $bar.Value = 100
        $status.Text = "NEXUS was installed successfully."
        $install.Text = "Finish"; $install.Enabled = $true
        $install.Add_Click({ if ($chkLaunch.Checked -and $script:installed) { Start-Process $script:installed -WorkingDirectory (Split-Path $script:installed) }; $form.Close() })
    } catch {
        $status.Text = "Setup failed."
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "NEXUS Setup", "OK", "Error") | Out-Null
        $install.Enabled = $true; $browse.Enabled = $true; $path.Enabled = $true
    }
})
[void]$form.ShowDialog()
