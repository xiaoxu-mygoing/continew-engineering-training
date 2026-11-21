param([string]$Python = 'py', [string]$Runtime = (Join-Path $PSScriptRoot '../../local-runtime/face'))
$ErrorActionPreference = 'Stop'
$Runtime = [IO.Path]::GetFullPath($Runtime)
New-Item -ItemType Directory -Path "$Runtime/models" -Force | Out-Null
$private = New-Item -ItemType Directory -Path "$Runtime/private" -Force
$acl = Get-Acl -LiteralPath $private.FullName
$acl.SetAccessRuleProtection($true, $false)
$principals = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544')
foreach ($sid in $principals) {
    $identity = [Security.Principal.SecurityIdentifier]::new($sid)
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.SetAccessRule($rule)
}
Set-Acl -LiteralPath $private.FullName -AclObject $acl
if (!(Test-Path "$Runtime/venv/Scripts/python.exe")) {
    & $Python -m venv "$Runtime/venv"
    if ($LASTEXITCODE) { throw 'Unable to create Python environment' }
}
& "$Runtime/venv/Scripts/python.exe" -m pip install --only-binary=:all: -r "$PSScriptRoot/requirements.txt"
if ($LASTEXITCODE) { throw 'Python dependencies failed to install' }
# Older installations used the headless distribution, which owns the same cv2 files.
$oldCv = & "$Runtime/venv/Scripts/python.exe" -c "import importlib.metadata as m; print(any(d.metadata['Name'] == 'opencv-python-headless' for d in m.distributions()))"
if ($oldCv -eq 'True') {
    & "$Runtime/venv/Scripts/python.exe" -m pip uninstall -y opencv-python-headless
    if ($LASTEXITCODE) { throw 'Unable to migrate OpenCV installation' }
    & "$Runtime/venv/Scripts/python.exe" -m pip install --only-binary=:all: --force-reinstall --no-deps opencv-contrib-python==4.10.0.84
    if ($LASTEXITCODE) { throw 'Unable to restore OpenCV installation' }
}
$models = @{
    'face_detection_yunet/face_detection_yunet_2023mar.onnx' = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'
    'face_recognition_sface/face_recognition_sface_2021dec.onnx' = '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'
}
foreach ($key in $models.Keys) {
    $path = Join-Path "$Runtime/models" (Split-Path $key -Leaf)
    if ((Test-Path $path) -and (Get-FileHash $path).Hash -eq $models[$key]) { continue }
    Invoke-WebRequest "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/$key" -OutFile "$path.download"
    if ((Get-FileHash "$path.download").Hash -ne $models[$key]) { throw "Invalid model checksum: $key" }
    Move-Item -LiteralPath "$path.download" -Destination $path -Force
}
$landmarker = Join-Path "$Runtime/models" 'face_landmarker.task'
$landmarkerHash = '64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff'
if (!(Test-Path $landmarker) -or (Get-FileHash $landmarker).Hash -ne $landmarkerHash) {
    Invoke-WebRequest 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task' -OutFile "$landmarker.download"
    if ((Get-FileHash "$landmarker.download").Hash -ne $landmarkerHash) { throw 'Invalid face landmark model checksum' }
    Move-Item -LiteralPath "$landmarker.download" -Destination $landmarker -Force
}
