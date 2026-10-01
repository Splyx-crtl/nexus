# Builds dist\NEXUS-Setup.exe (self-extracting installer via Windows' built-in IExpress) from dist\NEXUS.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root "dist\NEXUS"
if (-not (Test-Path (Join-Path $dist "NEXUS.exe"))) { throw "dist\NEXUS\NEXUS.exe not found - run build_exe.bat first." }

$versionLine = Select-String -Path (Join-Path $root "nexus\version.py") -Pattern '^VERSION\s*=\s*"([^"]+)"'
$version = $versionLine.Matches[0].Groups[1].Value
$work = Join-Path $root "build\installer"
Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $work | Out-Null

Write-Host "[INSTALLER] Zipping application (version $version)..."
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = Join-Path $work "NEXUS-app.zip"
[System.IO.Compression.ZipFile]::CreateFromDirectory($dist, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

(Get-Content (Join-Path $PSScriptRoot "install.ps1") -Raw).Replace("__VERSION__", $version) | Set-Content (Join-Path $work "install.ps1") -Encoding UTF8
Copy-Item (Join-Path $PSScriptRoot "uninstall.ps1") $work
Copy-Item (Join-Path $PSScriptRoot "install.cmd") $work
Copy-Item (Join-Path $root "assets\nexus.ico") $work

$target = Join-Path $root "dist\NEXUS-Setup.exe"
Remove-Item $target -Force -ErrorAction SilentlyContinue
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgressWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$target
FriendlyName=NEXUS Setup $version
AppLaunched=cmd /c install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$work\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
%FILE4%=
[Strings]
FILE0="install.cmd"
FILE1="install.ps1"
FILE2="uninstall.ps1"
FILE3="nexus.ico"
FILE4="NEXUS-app.zip"
"@
$sedPath = Join-Path $work "nexus.sed"
Set-Content -Path $sedPath -Value $sed -Encoding ASCII
Write-Host "[INSTALLER] Running IExpress (this takes a moment)..."
$p = Start-Process -FilePath "$env:WINDIR\System32\iexpress.exe" -ArgumentList @("/N", "/Q", "nexus.sed") -WorkingDirectory $work -Wait -PassThru
if (-not (Test-Path $target)) { throw "IExpress did not produce $target (exit code $($p.ExitCode))." }
$size = [Math]::Round((Get-Item $target).Length / 1MB, 1)
Write-Host "[INSTALLER] Done: dist\NEXUS-Setup.exe ($size MB)"
