# Run from PowerShell: .\start.ps1 --model base
$ErrorActionPreference = 'Stop'
$CaptionLauncher = Join-Path $PSScriptRoot 'deploy.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 $CaptionLauncher run @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $CaptionLauncher run @args
} else {
    throw 'Install 64-bit Python 3.12, then open a new PowerShell window and retry.'
}
exit $LASTEXITCODE
