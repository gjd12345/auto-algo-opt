param(
  [string]$Arm = "guided",
  [string]$Batch = "a1",
  [int]$Attempts = 3
)

$ErrorActionPreference = "Continue"
$repo = "C:\Users\24294\Projects\auto-algo-opt"
$py = "C:\Users\24294\Projects\aao-venv311\Scripts\python.exe"
$runs = Join-Path $repo "experiments\cvrp_midterm\runs"

if ($Batch -eq "a1") { $driver = "guided_search.py" } else { $driver = "guided_search_b2.py" }
$dir = Join-Path $runs "${Batch}_$Arm"

Set-Location $repo
New-Item -ItemType Directory -Force -Path (Join-Path $runs "_aborted") | Out-Null
$code = 1

for ($i = 1; $i -le $Attempts; $i++) {
    if (Test-Path $dir) {
        Move-Item $dir (Join-Path $runs "_aborted\${Batch}_${Arm}_attempt$i") -Force
    }
    Write-Host "[attempt $i] $Batch/$Arm start $(Get-Date -Format HH:mm:ss)"
    if ($Batch -eq "a1") {
        & $py "experiments\cvrp_midterm\runs\$driver" --arm $Arm *> (Join-Path $runs "$Batch`_$Arm`_try$i.log")
    }
    else {
        & $py "experiments\cvrp_midterm\runs\$driver" --arm $Arm --tag $Batch *> (Join-Path $runs "$Batch`_$Arm`_try$i.log")
    }
    $code = $LASTEXITCODE
    Write-Host "[attempt $i] exit=$code $(Get-Date -Format HH:mm:ss)"
    if ($code -eq 0) { break }
    Start-Sleep -Seconds 45
}
exit $code
