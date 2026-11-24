param([switch]$Native,[switch]$Build,[switch]$Face,[switch]$Rag,[switch]$Graph,[string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$rt = Join-Path $PSScriptRoot 'local-runtime'
$api = Join-Path $PSScriptRoot 'continew-admin'
$ui = Join-Path $PSScriptRoot 'continew-admin-ui'
$jar = Join-Path $api 'continew-server/target/continew-admin.jar'
function CheckExit($step) { if ($LASTEXITCODE) { throw "$step failed ($LASTEXITCODE)" } }
function Listening($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
foreach ($cmd in 'java','node','pnpm.cmd') { Get-Command $cmd -ErrorAction Stop | Out-Null }
if ($Face -or $Rag -or $Graph) { Get-Command $Python -ErrorAction Stop | Out-Null }
New-Item -Path $rt -ItemType Directory -Force | Out-Null
if (!$Native) {
    Get-Command docker -ErrorAction Stop | Out-Null
    $config = Join-Path $rt 'compose.env'
    if (!(Test-Path $config)) {
        @("DB_PWD=$([guid]::NewGuid().ToString('N'))","REDIS_PWD=$([guid]::NewGuid().ToString('N'))") | Set-Content $config -Encoding ascii
    }
    $settings = Get-Content $config -Raw | ConvertFrom-StringData
    $env:DB_PWD=$settings.DB_PWD
    $env:REDIS_PWD=$settings.REDIS_PWD
    $env:DB_USER='training'
    $env:DB_PORT='13306'
    $env:REDIS_PORT='16379'
    docker compose -p continew-training --env-file $config up -d --wait
    CheckExit 'MySQL and Redis'
} elseif (!$env:DB_USER -or !$env:DB_PWD -or !$env:REDIS_PWD) {
    throw 'Native mode requires DB_USER, DB_PWD and REDIS_PWD. See README.'
}
if ($Face) { & "$api/training-face/Start-CiaoFace.ps1" -Runtime "$rt/face-ciao" -Python $Python -Install }
$env:TRAINING_RAG_HOME="$rt/rag"
$env:TRAINING_RAG_PYTHON="$rt/rag/venv/Scripts/python.exe"
if ($Rag -or $Graph) {
    if (!(Test-Path $env:TRAINING_RAG_PYTHON)) { & $Python -m venv "$rt/rag/venv"; CheckExit 'Python venv' }
    & $env:TRAINING_RAG_PYTHON -m pip install -r "$api/training-rag/requirements.txt"; CheckExit 'RAG packages'
    foreach ($model in 'nomic-embed-text','qwen2.5:3b') { ollama pull $model; CheckExit 'Ollama model' }
}
if ($Graph -or (Test-Path "$rt/neo4j/credentials.json")) {
    & "$PSScriptRoot/Setup-Graph.ps1"
    $env:TRAINING_GRAPH_HOME="$rt/graph"
    $env:TRAINING_GRAPH_PYTHON=$env:TRAINING_RAG_PYTHON
    $env:TRAINING_GRAPH_WORKER="$api/training-graph/worker.py"
}
if ($Build -or !(Test-Path $jar)) {
    Push-Location $api
    try { & .\mvnw.cmd -DskipTests '-Dmaven.jar.forceCreation=true' -P fat-jar package; CheckExit 'Maven build' } finally { Pop-Location }
}
if ($Build -or !(Test-Path "$ui/node_modules/vite/bin/vite.js")) {
    Push-Location $ui
    try { pnpm.cmd install --frozen-lockfile; CheckExit 'Frontend dependencies' } finally { Pop-Location }
}
$env:SERVER_ADDRESS='127.0.0.1'
$env:CONTINEWSTARTER_REFRESHTOKEN_COOKIEALLOWEDORIGINS='http://localhost:5173,http://127.0.0.1:5173'
$env:TRAINING_FACE_HOME="$rt/face"
$env:TRAINING_FACE_WORKER="$api/training-face/worker.py"
if (Test-Path "$rt/face-ciao/venv/Scripts/python.exe") {
    & "$api/training-face/Start-CiaoFace.ps1" -Runtime "$rt/face-ciao"
}
$env:TRAINING_RAG_WORKER="$api/training-rag/worker.py"
if (!(Listening 8000)) {
    $backend = Start-Process java -ArgumentList '-Xmx1024m','-Dp6spy.config.filter=true','-Dp6spy.config.exclude=training_document','-jar',('"'+$jar+'"') -WorkingDirectory $rt -WindowStyle Hidden -PassThru -RedirectStandardOutput "$rt/backend.log" -RedirectStandardError "$rt/backend-errors.log"
}
if (!(Listening 5173)) {
    $env:BROWSER='none'
    $frontend = Start-Process node -ArgumentList 'node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort' -WorkingDirectory $ui -WindowStyle Hidden -PassThru -RedirectStandardOutput "$rt/frontend.log" -RedirectStandardError "$rt/frontend-errors.log"
}
$limit=(Get-Date).AddMinutes(4)
do {
    if (($backend -and $backend.HasExited) -or ($frontend -and $frontend.HasExited)) { throw "Startup failed. Logs: $rt" }
    try { $ready=(Invoke-RestMethod 'http://127.0.0.1:5173/dev-api/captcha/image' -TimeoutSec 3).success } catch { $ready=$false }
    if (!$ready) { Start-Sleep -Seconds 2 }
} until ($ready -or (Get-Date) -gt $limit)
if (!$ready) { throw "Login service unavailable. Logs: $rt" }
Write-Host 'Ready: http://localhost:5173/'
