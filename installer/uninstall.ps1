# NEXUS // TERMINAL - uninstaller (registered in Windows "Installed apps")
param([switch]$Silent, [switch]$KeepSaves)

$ErrorActionPreference = "SilentlyContinue"
$Dest = $PSScriptRoot
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXUS"

Add-Type -AssemblyName System.Windows.Forms
$removeSaves = $true
if (-not $Silent) {
    $ask = [System.Windows.Forms.MessageBox]::Show("Remove NEXUS from this computer?", "NEXUS Uninstall", "YesNo", "Question")
    if ($ask -ne "Yes") { exit 0 }
    $saves = [System.Windows.Forms.MessageBox]::Show("Also delete your save games and settings?`n`nChoose 'No' to keep them in:`n$Dest\saves", "NEXUS Uninstall", "YesNo", "Question")
    $removeSaves = ($saves -eq "Yes")
} elseif ($KeepSaves) {
    $removeSaves = $false
}

Get-Process -Name NEXUS | Where-Object { $_.Path -like "$Dest*" } | Stop-Process -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath("Desktop")) "NEXUS.lnk") -Force
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\NEXUS.lnk") -Force
Remove-Item -Path $UninstallKey -Recurse -Force

# This script lives inside $Dest, so the removal runs from a detached cmd after we exit.
if ($removeSaves) {
    $cmd = "ping -n 3 127.0.0.1 >nul & rmdir /s /q `"$Dest`""
} else {
    $cmd = "ping -n 3 127.0.0.1 >nul & for /d %d in (`"$Dest\*`") do @if /i not `"%~nxd`"==`"saves`" rmdir /s /q `"%d`" & del /q `"$Dest\*.*`""
}
Start-Process cmd.exe -ArgumentList "/c $cmd" -WindowStyle Hidden
if (-not $Silent) { [System.Windows.Forms.MessageBox]::Show("NEXUS was removed.", "NEXUS Uninstall") | Out-Null }
