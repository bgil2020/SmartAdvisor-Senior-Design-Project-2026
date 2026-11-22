param(
    [string]$Image = "smartadvisor-headed-smoke:local",
    [int]$Port = 18000,
    [string]$SourceFingerprint = "unrecorded",
    [string]$ExpectedImageId = "",
    [switch]$SkipBuild,
    [int]$StartupDeadlineSeconds = 60,
    [int]$RuntimeDeadlineSeconds = 90
)

$ErrorActionPreference = "Stop"
$containerName = "smartadvisor-free-smoke-$PID"
$signingBytes = New-Object byte[] 48
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($signingBytes)
} finally {
    $random.Dispose()
}
$signingKey = [Convert]::ToBase64String($signingBytes)
$result = [ordered]@{
    container = $containerName
    memory_limit_mb = 512
    applied_memory_limit_mb = $null
    applied_memory_swap_mb = $null
    restart_policy = $null
    restart_count = $null
    idle_memory_mb = $null
    peak_memory_mb = $null
    oom_killed = $null
    startup_browser_peak_mb = $null
    startup_browser_status = "unknown"
    xvfb_running = $null
    chromium_processes_after_smoke = $null
    routes = [ordered]@{}
    acquisition_disabled = $null
    provider_disabled = $null
    container_removed = $false
    container_exit_code = $null
    container_state_before_cleanup = "unknown"
    image_id = $null
    source_fingerprint = $SourceFingerprint
    startup_deadline_seconds = $StartupDeadlineSeconds
    runtime_deadline_seconds = $RuntimeDeadlineSeconds
    cgroup_peak_memory_mb = $null
    cgroup_memory_limit_mb = $null
    cgroup_swap_limit_mb = $null
    memory_headroom_mb = $null
    app_running = $null
    static_assets_checked = 0
    health = "not_run"
}

function Get-ContainerMemoryBytes {
    $usage = docker stats $containerName --no-stream --format "{{.MemUsage}}"
    if ($usage -match '^([0-9.]+)KiB') { return [double]$Matches[1] * 1KB }
    if ($usage -match '^([0-9.]+)MiB') { return [double]$Matches[1] * 1MB }
    if ($usage -match '^([0-9.]+)GiB') { return [double]$Matches[1] * 1GB }
    throw "Could not parse container memory usage: $usage"
}

function Assert-RuntimeDeadline {
    if ((Get-Date) -gt $runtimeDeadline) {
        throw "Runtime verification exceeded the $RuntimeDeadlineSeconds second deadline."
    }
}

try {
    if (-not $SkipBuild) {
        docker build --build-arg "SMARTADVISOR_SOURCE_FINGERPRINT=$SourceFingerprint" --tag $Image .
    }
    $imageMetadata = docker image inspect $Image | ConvertFrom-Json
    $result.image_id = $imageMetadata[0].Id
    $imageFingerprint = $imageMetadata[0].Config.Labels.'org.opencontainers.image.source-fingerprint'
    if ($ExpectedImageId -and $result.image_id -ne $ExpectedImageId) {
        throw "Image ID changed after preflight inspection."
    }
    if ($imageFingerprint -ne $SourceFingerprint) {
        throw "Image source fingerprint does not match the approved tree."
    }

    docker run --detach --name $containerName --restart no --memory 512m --memory-swap 512m --publish "${Port}:8000" `
        --env PORT=8000 --env ACQUISITION_BROWSER_MODE=headed `
        --env SYLLABUS_ACQUISITION_ENABLED=false --env CATALOG_ACQUISITION_ENABLED=false `
        --env ACQUISITION_TEST_SYLLABUS_BUDGET=0 --env ACQUISITION_TEST_CATALOG_BUDGET=0 `
        --env CONVERSATIONAL_PARSER_MODE=deterministic --env RAG_GENERATION_MODE=fallback `
        --env GEMINI_API_KEY= `
        --env SESSION_EVIDENCE_SIGNING_KEY=$signingKey --env RENDER_STARTUP_BROWSER_SMOKE=true $Image | Out-Null
    $runtimeDeadline = (Get-Date).AddSeconds($RuntimeDeadlineSeconds)

    $limits = (docker inspect $containerName --format "{{.HostConfig.Memory}}|{{.HostConfig.MemorySwap}}|{{.HostConfig.RestartPolicy.Name}}") -split '\|'
    $result.applied_memory_limit_mb = [math]::Round(([double]$limits[0]) / 1MB, 0)
    $result.applied_memory_swap_mb = [math]::Round(([double]$limits[1]) / 1MB, 0)
    $result.restart_policy = $limits[2]
    if ($result.applied_memory_limit_mb -ne 512 -or $result.applied_memory_swap_mb -ne 512) {
        throw "Docker did not apply the requested 512 MiB memory and swap limits."
    }
    if ($result.restart_policy -ne "no") { throw "Unexpected restart policy: $($result.restart_policy)" }

    $configuredEnv = docker inspect $containerName --format "{{json .Config.Env}}"
    $result.acquisition_disabled = (
        $configuredEnv -match 'SYLLABUS_ACQUISITION_ENABLED=false' -and
        $configuredEnv -match 'CATALOG_ACQUISITION_ENABLED=false' -and
        $configuredEnv -match 'ACQUISITION_TEST_SYLLABUS_BUDGET=0' -and
        $configuredEnv -match 'ACQUISITION_TEST_CATALOG_BUDGET=0'
    )
    $result.provider_disabled = (
        $configuredEnv -match 'CONVERSATIONAL_PARSER_MODE=deterministic' -and
        $configuredEnv -match 'RAG_GENERATION_MODE=fallback' -and
        $configuredEnv -match 'GEMINI_API_KEY='
    )
    if (-not $result.acquisition_disabled -or -not $result.provider_disabled) {
        throw "Container safety configuration was not applied."
    }

    $deadline = (Get-Date).AddSeconds($StartupDeadlineSeconds)
    $peakBytes = 0
    do {
        Assert-RuntimeDeadline
        Start-Sleep -Milliseconds 500
        $state = docker inspect $containerName --format "{{.State.Status}}"
        if ($state -eq "exited" -or $state -eq "dead") {
            $result.container_exit_code = [int](docker inspect $containerName --format "{{.State.ExitCode}}")
            throw "Container exited before health was ready (exit $($result.container_exit_code))."
        }
        try {
            $bytes = Get-ContainerMemoryBytes
            if ($bytes -gt $peakBytes) { $peakBytes = $bytes }
        } catch {
            # The process can be between startup stages while the container remains alive.
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/" -TimeoutSec 2
        } catch {
            $health = $null
        }
    } until ($health -or (Get-Date) -gt $deadline)
    if (-not $health) { throw "Container health did not become ready within $StartupDeadlineSeconds seconds." }

    $result.health = "passed"
    $result.routes["/"] = "passed"
    $idleBytes = Get-ContainerMemoryBytes
    $result.idle_memory_mb = [math]::Round($idleBytes / 1MB, 1)
    if ($idleBytes -gt $peakBytes) { $peakBytes = $idleBytes }

    $spaResponses = @{}
    foreach ($route in @("/forms", "/chatbot")) {
        Assert-RuntimeDeadline
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port$route" -TimeoutSec 5
        $spaResponses[$route] = $response
        $isSpa = $response.StatusCode -eq 200 -and $response.Content -match '<div id="root"></div>'
        $result.routes[$route] = if ($isSpa) { "passed" } else { "failed" }
        if (-not $isSpa) { throw "SPA direct route failed: $route" }
        $bytes = Get-ContainerMemoryBytes
        if ($bytes -gt $peakBytes) { $peakBytes = $bytes }
    }

    $assetPaths = @(
        [regex]::Matches($spaResponses["/forms"].Content, '(?:src|href)="([^"]+\.(?:js|css))"') |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )
    if ($assetPaths.Count -lt 2) { throw "Built SPA did not expose both script and stylesheet assets." }
    foreach ($assetPath in $assetPaths) {
        Assert-RuntimeDeadline
        $asset = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port$assetPath" -TimeoutSec 5
        if ($asset.StatusCode -ne 200 -or $asset.RawContentLength -le 0) {
            throw "Static asset failed: $assetPath"
        }
        $result.static_assets_checked += 1
    }
    $result.routes["static_assets"] = "passed"

    try {
        $unknown = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/unknown-release-probe" -TimeoutSec 5
        $unknownStatus = [int]$unknown.StatusCode
        $unknownType = [string]$unknown.Headers["Content-Type"]
    } catch {
        $unknownStatus = [int]$_.Exception.Response.StatusCode
        if ($_.Exception.Response.Content -and $_.Exception.Response.Content.Headers.ContentType) {
            $unknownType = [string]$_.Exception.Response.Content.Headers.ContentType
        } else {
            $unknownType = [string]$_.Exception.Response.Headers["Content-Type"]
        }
    }
    $unknownIsApiError = $unknownStatus -eq 404 -and $unknownType -match 'application/json'
    $result.routes["unknown_api_404"] = if ($unknownIsApiError) { "passed" } else { "failed" }
    if (-not $unknownIsApiError) { throw "Unknown API route did not remain a JSON 404." }

    $catalog = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/courses?term=202608" -TimeoutSec 5
    $result.routes["/courses?term=202608"] = if ($catalog.count -gt 0) { "passed" } else { "failed" }
    if ($catalog.count -le 0) { throw "Offline catalog GET returned no records." }

    $processList = docker exec $containerName ps -eo comm,args
    $result.xvfb_running = [bool]($processList -match '(?m)^Xvfb\s')
    $result.app_running = [bool]($processList -match '(?i)uvicorn')
    $result.chromium_processes_after_smoke = @($processList | Select-String -Pattern '(chrome|chromium)' -CaseSensitive:$false).Count
    if (-not $result.xvfb_running -or -not $result.app_running -or $result.chromium_processes_after_smoke -ne 0) {
        throw "Unexpected Xvfb or Chromium process state after startup smoke."
    }

    $startupRecord = docker logs $containerName 2>&1 | Select-String -Pattern '"peak_family_rss_mb"' | Select-Object -Last 1
    if ($startupRecord) {
        $startup = $startupRecord.ToString() | ConvertFrom-Json
        $result.startup_browser_status = $startup.status
        $result.startup_browser_peak_mb = $startup.peak_family_rss_mb
    }
    if ($result.startup_browser_status -ne "passed") { throw "Offline headed-browser startup smoke did not pass." }

    $result.peak_memory_mb = [math]::Round($peakBytes / 1MB, 1)

    $cgroupPeak = docker exec $containerName cat /sys/fs/cgroup/memory.peak
    $cgroupLimit = docker exec $containerName cat /sys/fs/cgroup/memory.max
    $cgroupSwap = docker exec $containerName cat /sys/fs/cgroup/memory.swap.max
    if ($cgroupPeak -match '^\d+$') { $result.cgroup_peak_memory_mb = [math]::Round(([double]$cgroupPeak) / 1MB, 1) }
    if ($cgroupLimit -match '^\d+$') { $result.cgroup_memory_limit_mb = [math]::Round(([double]$cgroupLimit) / 1MB, 0) }
    if ($cgroupSwap -match '^\d+$') { $result.cgroup_swap_limit_mb = [math]::Round(([double]$cgroupSwap) / 1MB, 0) }
    $authoritativePeak = if ($null -ne $result.cgroup_peak_memory_mb) { $result.cgroup_peak_memory_mb } else { $result.peak_memory_mb }
    $result.memory_headroom_mb = [math]::Round(512 - $authoritativePeak, 1)
    Assert-RuntimeDeadline
} finally {
    $running = docker ps --all --filter "name=^/${containerName}$" --format "{{.Names}}"
    if ($running -eq $containerName) {
        $result.oom_killed = [System.Convert]::ToBoolean((docker inspect $containerName --format "{{.State.OOMKilled}}"))
        $result.container_state_before_cleanup = docker inspect $containerName --format "{{.State.Status}}"
        if ($result.container_state_before_cleanup -eq "running") {
            docker stop --time 10 $containerName | Out-Null
            $result.container_state_before_cleanup = "running_then_stopped"
        }
        if ((docker inspect $containerName --format "{{.State.Status}}") -eq "exited") {
            $result.container_exit_code = [int](docker inspect $containerName --format "{{.State.ExitCode}}")
        }
        $result.restart_count = [int](docker inspect $containerName --format "{{.RestartCount}}")
        docker rm --force $containerName | Out-Null
        $result.container_removed = -not [bool](docker ps --all --filter "name=^/${containerName}$" --format "{{.Names}}")
    }
    $result | ConvertTo-Json
}
