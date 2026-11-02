
$ErrorActionPreference = "Stop"

$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$seedFile = Join-Path $PSScriptRoot "seed.sql"

$hostName = "127.0.0.1"
$port = "5432"
$database = "smartadvisor_demo"
$userName = "postgres"

Write-Host "SmartAdvisor Demo Seed"
Write-Host "----------------------"

if (-not (Test-Path $psql)) {
    throw "PostgreSQL psql.exe was not found."
}

if (-not (Test-Path $seedFile)) {
    throw "seed.sql was not found."
}

if ($hostName -ne "127.0.0.1" -or $port -ne "5432" -or $database -ne "smartadvisor_demo") {
    throw "Safety check failed: Only the local smartadvisor_demo database is allowed."

}

Write-Host "Target: $database on $hostName"
Write-Host "Checking database connection..."

$identity = & $psql `
    -X -W `
    -h $hostName `
    -p $port `
    -U $userName `
    -d $database `
    -Atc "SELECT current_database(), inet_server_addr(), inet_server_port();"

if ($LASTEXITCODE -ne 0) {
    throw "Connection verification failed. No seed SQL executed."
}

$expectedIdentity = "smartadvisor_demo|127.0.0.1|5432"

if (($identity | Select-Object -Last 1).Trim() -ne $expectedIdentity) {
    throw "Database identity mismatch. No seed SQL executed."
}

Write-Host "Local demo database verified."
Write-Host "Running seed.sql..."

& $psql `
    -X `
    -h $hostName `
    -p $port `
    -U $userName `
    -d $database `
    -v ON_ERROR_STOP=1 `
    -f $seedFile

if ($LASTEXITCODE -ne 0) {
    throw "Database seed failed."
}

Write-Host "SmartAdvisor demo seed completed successfully."
