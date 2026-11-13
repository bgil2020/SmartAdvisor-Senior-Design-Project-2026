param(
    [string]$Image = "smartadvisor-headed-smoke:local",
    [int]$Port = 18000
)

$ErrorActionPreference = "Stop"
$containerName = "smartadvisor-free-smoke-$PID"
$signingBytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($signingBytes)
$signingKey = [Convert]::ToBase64String($signingBytes)
$result = [ordered]@{
    container = $containerName
    memory_limit_mb = 512
    idle_memory_mb = $null
    peak_memory_mb = $null
    oom_killed = $null
    request_duration_ms = $null
    health = "not_run"
}

try {
    docker build --tag $Image .
    docker run --detach --name $containerName --memory 512m --memory-swap 512m --publish "${Port}:8000" `
        --env PORT=8000 --env ACQUISITION_BROWSER_MODE=headed `
        --env SYLLABUS_ACQUISITION_ENABLED=false --env CONVERSATIONAL_PARSER_MODE=deterministic `
        --env SESSION_EVIDENCE_SIGNING_KEY=$signingKey --env RENDER_STARTUP_BROWSER_SMOKE=true $Image | Out-Null

    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2
        } catch {
            $health = $null
        }
    } until ($health -or (Get-Date) -gt $deadline)
    if (-not $health) { throw "Container health did not become ready within 60 seconds." }

    $result.health = "passed"
    $idleBytes = [double](docker stats $containerName --no-stream --format "{{.MemUsage}}" | ForEach-Object {
        if ($_ -match '^([0-9.]+)MiB') { [double]$Matches[1] * 1MB } elseif ($_ -match '^([0-9.]+)GiB') { [double]$Matches[1] * 1GB } else { 0 }
    })
    $result.idle_memory_mb = [math]::Round($idleBytes / 1MB, 1)
    $peakBytes = $idleBytes
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    1..3 | ForEach-Object {
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/conversation" -ContentType "application/json" `
            -Body '{"message":"What topics are covered in COP 4331?","session_context":{"course_code":"COP4331","term_id":"202608","section":"002"}}' | Out-Null
        $bytes = [double](docker stats $containerName --no-stream --format "{{.MemUsage}}" | ForEach-Object {
            if ($_ -match '^([0-9.]+)MiB') { [double]$Matches[1] * 1MB } elseif ($_ -match '^([0-9.]+)GiB') { [double]$Matches[1] * 1GB } else { 0 }
        })
        if ($bytes -gt $peakBytes) { $peakBytes = $bytes }
    }
    $watch.Stop()
    $result.peak_memory_mb = [math]::Round($peakBytes / 1MB, 1)
    $result.request_duration_ms = $watch.ElapsedMilliseconds
} finally {
    $running = docker ps --all --filter "name=^/${containerName}$" --format "{{.Names}}"
    if ($running -eq $containerName) {
        $result.oom_killed = [System.Convert]::ToBoolean((docker inspect $containerName --format "{{.State.OOMKilled}}"))
        docker rm --force $containerName | Out-Null
    }
    $result | ConvertTo-Json
}
