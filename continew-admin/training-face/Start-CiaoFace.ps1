param([string]$Runtime = (Join-Path $PSScriptRoot '../../local-runtime/face-ciao'), [string]$Python = 'py', [switch]$Install)
$ErrorActionPreference = 'Stop'
$Runtime = [IO.Path]::GetFullPath($Runtime)
New-Item -ItemType Directory -Force "$Runtime/private" | Out-Null
$private = Get-Item "$Runtime/private"
$acl = Get-Acl -LiteralPath $private.FullName
$principals = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544')
$rules = @($acl.Access)
$expectedRules = @($rules | Where-Object {
    $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -in $principals -and
    $_.AccessControlType -eq 'Allow' -and $_.FileSystemRights -eq 'FullControl' -and
    $_.InheritanceFlags -eq 'ContainerInherit,ObjectInherit' -and $_.PropagationFlags -eq 'None'
})
if (!$acl.AreAccessRulesProtected -or $rules.Count -ne 3 -or $expectedRules.Count -ne 3) {
    # Change only the DACL; never copy audit/owner sections requiring extra privileges.
    $restricted = [Security.AccessControl.DirectorySecurity]::new()
    $restricted.SetAccessRuleProtection($true, $false)
    foreach ($sid in $principals) {
        $restricted.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    [IO.FileSystemAclExtensions]::SetAccessControl($private, $restricted)
}
if (!(Test-Path "$Runtime/venv/Scripts/python.exe")) {
    & $Python -m venv "$Runtime/venv"
    if ($LASTEXITCODE) { throw 'Cannot create face environment' }
    $Install = $true
}
if ($Install) {
    & "$Runtime/venv/Scripts/python.exe" -m pip install wheel 'Cython<3' numpy==1.26.4
    if ($LASTEXITCODE) { throw 'Cannot install native build dependencies' }
    & "$Runtime/venv/Scripts/python.exe" -m pip install --no-build-isolation -r "$PSScriptRoot/ciao_requirements.txt"
    if ($LASTEXITCODE) { throw 'Cannot install InsightFace dependencies; Windows C++ build tools may be required' }
}
$keyPath = "$Runtime/private/service-key.txt"
if (!(Test-Path $keyPath)) { ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')) | Set-Content $keyPath -Encoding ascii }
$env:FACE_SERVICE_API_KEY = (Get-Content $keyPath -Raw).Trim()
$env:TRAINING_FACE_HOME = $Runtime
$env:TRAINING_FACE_SERVICE_URL = 'http://127.0.0.1:18100'
if (!(Get-NetTCPConnection -LocalPort 18100 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process "$Runtime/venv/Scripts/python.exe" -ArgumentList '-m','uvicorn','ciao_server:app','--host','127.0.0.1','--port','18100','--no-access-log' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$Runtime/service.log" -RedirectStandardError "$Runtime/service-errors.log" | Out-Null
}
