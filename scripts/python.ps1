function Resolve-BatteryPython {
    param([string]$ProjectRoot)
    $pythonCandidates = @(
        (Join-Path $projectRoot ".venv\Scripts\python.exe"),
        ((Get-Command python -ErrorAction SilentlyContinue).Source),
        (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
    $pythonExe = $null
    foreach ($candidate in $pythonCandidates) {
        & $candidate -c "import pypdf" 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonExe = $candidate; break }
    }

    return $pythonExe
}
