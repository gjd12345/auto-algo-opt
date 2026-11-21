param(
  [string]$Arm = "guided",
  [int]$Attempts = 3
)

$ErrorActionPreference = "Continue"
$repo = "C:\Users\24294\Projects\auto-algo-opt"
$py = "C:\Users\24294\Projects\aao-venv311\Scripts\python.exe"
$runs = Join-Path $repo "experiments\cvrp_midterm\runs"
$dir = Join-Path $runs "a1_$Arm"

Set-Location $repo
New-Item -ItemType Directory -Force -Path (Join-Path $runs "_aborted") | Out-Null

for ($i = 1; $i -le $Attempts; $i++) {
    if (Test-Path $dir) {
        Move-Item $dir (Join-Path $runs "_aborted\a1_${Arm}_attempt$i") -Force
    }
    Write-Host "[attempt $i] $Arm start $(Get-Date -Format HH:mm:ss)"
    & $py "experiments\cvrp_midterm\runs\guided_search.py" --arm $Arm *> (Join-Path $runs "$Arm`_a$i.log")
    $code = $LASTEXITCODE
    Write-Host "[attempt $i] exit=$code $(Get-Date -Format HH:mm:ss)"
    if ($code -eq 0) { break }
    Start-Sleep -Seconds 45
}
exit $code
