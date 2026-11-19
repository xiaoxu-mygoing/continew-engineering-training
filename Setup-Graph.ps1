param([string]$Runtime = (Join-Path $PSScriptRoot 'local-runtime'))
$ErrorActionPreference = 'Stop'
$folder = Join-Path $Runtime 'neo4j'
$install = Join-Path $folder 'neo4j-community-5.26.0'
New-Item -ItemType Directory -Force $folder | Out-Null
if (!(Test-Path "$install/bin/neo4j.bat")) {
    $zip = Join-Path $folder 'neo4j.zip'
    Invoke-WebRequest 'https://dist.neo4j.org/neo4j-community-5.26.0-windows.zip' -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne 'EA9C98111B72310DAB8AE00B7AE4D43DF59A1EA82A490579B886BFFB3E30DE8F') {
        throw 'Neo4j archive checksum mismatch.'
    }
    Expand-Archive $zip $folder -Force
}
$settings = Join-Path $folder 'credentials.json'
if (!(Test-Path $settings)) {
    @{password = [guid]::NewGuid().ToString('N')} | ConvertTo-Json | Set-Content $settings
}
$env:NEO4J_PASSWORD = (Get-Content $settings -Raw | ConvertFrom-Json).password
$env:NEO4J_USER = 'neo4j'
$env:NEO4J_HTTP_URL = 'http://127.0.0.1:7474'
if (!(Test-Path "$folder/initialized")) {
    & "$install/bin/neo4j-admin.bat" dbms set-initial-password $env:NEO4J_PASSWORD
    if ($LASTEXITCODE) { throw 'Neo4j initial password setup failed.' }
    @('server.memory.heap.initial_size=256m','server.memory.heap.max_size=512m',
      'server.memory.pagecache.size=256m','server.default_listen_address=127.0.0.1') |
        Add-Content "$install/conf/neo4j.conf"
    Set-Content "$folder/initialized" ready
}
if (!(Get-NetTCPConnection -LocalPort 7474 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -ArgumentList '-NoProfile','-Command',("& '" + $install + "/bin/neo4j.bat' console") -WindowStyle Hidden -RedirectStandardOutput "$folder/start.log" -RedirectStandardError "$folder/start-errors.log"
}
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("neo4j:" + $env:NEO4J_PASSWORD))
$limit = (Get-Date).AddMinutes(2)
do {
    try {
        $result = Invoke-RestMethod "$env:NEO4J_HTTP_URL/db/neo4j/tx/commit" -Method Post -Headers @{Authorization="Basic $auth"} -ContentType application/json -Body '{"statements":[{"statement":"CREATE CONSTRAINT training_entity_key IF NOT EXISTS FOR (n:TrainingEntity) REQUIRE (n.documentId,n.version,n.id) IS UNIQUE"}]}'
        $ready = $result.errors.Count -eq 0
    } catch { $ready = $false }
    if (!$ready) { Start-Sleep -Seconds 2 }
} until ($ready -or (Get-Date) -gt $limit)
if (!$ready) { throw 'Neo4j did not become ready. Check local-runtime/neo4j logs.' }
