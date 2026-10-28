$ErrorActionPreference = "Stop"
$py32 = "$env:LOCALAPPDATA\Programs\Python\Python311-32\python.exe"
$iscc = if (Test-Path "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") {
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
} elseif (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") {
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
} elseif (Test-Path "C:\Program Files\Inno Setup 6\ISCC.exe") {
    "C:\Program Files\Inno Setup 6\ISCC.exe"
} else {
    "ISCC.exe"
}

Write-Host "=== Step 1: Building erba_listener.exe (32-bit) ==="
& $py32 -m PyInstaller -y --onefile --console --clean --distpath dist-listener --workpath build-listener --name erba_listener "py-script\erba_listener.py"

if (-not (Test-Path "dist-listener\erba_listener.exe")) {
    throw "Failed to create dist-listener\erba_listener.exe"
}
Write-Host "erba_listener.exe built successfully!"

Write-Host "=== Step 2: Building COCOHOSPITALS-LIS-Analyzer-Connector.exe (32-bit) ==="
Push-Location "desktop-app"
try {
    & $py32 -m PyInstaller -y --onedir --windowed --clean --icon=..\logo.ico --name COCOHOSPITALS-LIS-Analyzer-Connector app.py
} finally {
    Pop-Location
}

if (-not (Test-Path "desktop-app\dist\COCOHOSPITALS-LIS-Analyzer-Connector\COCOHOSPITALS-LIS-Analyzer-Connector.exe")) {
    throw "Failed to create desktop-app\dist\COCOHOSPITALS-LIS-Analyzer-Connector\COCOHOSPITALS-LIS-Analyzer-Connector.exe"
}
Write-Host "Desktop app built successfully!"

Write-Host "=== Step 3: Copying Assets into Dist Folder ==="
$targetDist = "desktop-app\dist\COCOHOSPITALS-LIS-Analyzer-Connector"
Copy-Item -Path "dist-listener\erba_listener.exe" -Destination "$targetDist\" -Force
Copy-Item -Path "desktop-app\erba_connector_config.json" -Destination "$targetDist\" -Force
Copy-Item -Path "desktop-app\source_devices.json" -Destination "$targetDist\" -Force

Write-Host "Assets copied."

Write-Host "=== Step 4: Compiling Universal Inno Setup Installer ==="
& $iscc "COCOHOSPITALS_LIS_Analyzer_Connector.iss"

Write-Host "=== Step 5: Architecture Verification ==="
function Get-ExeMachineType($path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $peOffset = [System.BitConverter]::ToInt32($bytes, 0x3C)
    $machine = [System.BitConverter]::ToUInt16($bytes, $peOffset + 4)
    if ($machine -eq 0x014c) { return "32-bit (x86 / IMAGE_FILE_MACHINE_I386)" }
    if ($machine -eq 0x8664) { return "64-bit (x64 / IMAGE_FILE_MACHINE_AMD64)" }
    return "Unknown (0x{0:x4})" -f $machine
}

$files = @(
    "dist-listener\erba_listener.exe",
    "desktop-app\dist\COCOHOSPITALS-LIS-Analyzer-Connector\COCOHOSPITALS-LIS-Analyzer-Connector.exe",
    "installer-output\COCOHOSPITALS-LIS.exe"
)

foreach ($f in $files) {
    if (Test-Path $f) {
        $arch = Get-ExeMachineType (Resolve-Path $f)
        Write-Host "$f => $arch"
    } else {
        Write-Host "$f => NOT FOUND"
    }
}

Write-Host "=== ALL BUILDS COMPLETED SUCCESSFULLY! ==="
