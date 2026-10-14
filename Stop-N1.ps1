$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
[System.IO.File]::WriteAllText((Join-Path $runtime 'stop.request'), 'User requested stop.')
Write-Output 'Stop requested. The runner will stop game input; it will not abandon the run.'
