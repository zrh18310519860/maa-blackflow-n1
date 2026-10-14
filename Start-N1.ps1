param([switch]$Run, [switch]$CheckOnly,
      [ValidateSet('wisadel','wang','mechanist')][string]$Start)
$ErrorActionPreference = 'Stop'
if ($Run -and $CheckOnly) { throw 'Choose Run or CheckOnly, not both.' }
$candidates = @($env:MAA_N1_PYTHON)
$found = Get-Command python.exe -ErrorAction SilentlyContinue
if ($found) { $candidates += $found.Source }
$python = $null
foreach ($candidate in $candidates) {
    if (-not $candidate -or -not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $check = & $candidate -c "import sys,struct;print('MAA_N1_OK' if sys.version_info >= (3,10) and struct.calcsize('P')==8 else 'NO')" 2>$null }
    finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE -eq 0 -and $check -eq 'MAA_N1_OK') { $python=$candidate; break }
}
if (-not $python) { throw '64-bit Python 3.10+ was not found. Install Python or set MAA_N1_PYTHON to python.exe.' }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
$mode = if ($Run) { '--run' } else { '--offline-check' }
$runnerArgs = @('-B', (Join-Path $PSScriptRoot 'runner.py'), $mode)
if ($Start) { $runnerArgs += @('--start', $Start) }
& $python @runnerArgs
exit $LASTEXITCODE
