# Authenticode-sign the Windows executable so SmartScreen shows a publisher
# instead of "Unknown publisher" (an EV certificate, or one with reputation,
# removes the "Windows protected your PC" screen; an OV certificate earns that
# reputation over time).
#
# Usage:  packaging/desktop/sign_windows.ps1 dist/Vowelchemy.exe
# Environment (from repository secrets):
#     WINDOWS_CERTIFICATE           base64 of the code-signing .pfx
#     WINDOWS_CERTIFICATE_PASSWORD  its password
param([Parameter(Mandatory = $true)][string]$Exe)
$ErrorActionPreference = "Stop"

if (-not $env:WINDOWS_CERTIFICATE) { throw "set WINDOWS_CERTIFICATE (base64 .pfx)" }
if (-not $env:WINDOWS_CERTIFICATE_PASSWORD) { throw "set WINDOWS_CERTIFICATE_PASSWORD" }

$work = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $work | Out-Null
$pfx = Join-Path $work "cert.pfx"
[System.IO.File]::WriteAllBytes($pfx, [System.Convert]::FromBase64String($env:WINDOWS_CERTIFICATE))

# signtool ships with the Windows SDK on the GitHub runners; pick the newest x64 one.
$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signtool) { throw "signtool.exe not found (Windows SDK missing)" }

try {
  & $signtool.FullName sign /f $pfx /p $env:WINDOWS_CERTIFICATE_PASSWORD `
    /tr http://timestamp.digicert.com /td sha256 /fd sha256 /d "Vowelchemy" $Exe
  if ($LASTEXITCODE -ne 0) { throw "signtool failed ($LASTEXITCODE)" }
  & $signtool.FullName verify /pa /v $Exe
  if ($LASTEXITCODE -ne 0) { throw "signature verification failed ($LASTEXITCODE)" }
} finally {
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
Write-Output "Signed: $Exe"
