$ErrorActionPreference = 'Stop'
foreach ($start in @('wisadel','wang','mechanist')) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'Start-N1.ps1') -CheckOnly -Start $start
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
