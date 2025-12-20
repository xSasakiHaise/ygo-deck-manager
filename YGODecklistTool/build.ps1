$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$bundledPythonDir = Join-Path $projectRoot "tools\.python"
$bundledPythonExe = Join-Path $bundledPythonDir "python.exe"
$pythonVersion = "3.12.6"
$pythonArch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "win32" }

function Install-BundledPython {
  if (Test-Path $bundledPythonExe) {
    return $bundledPythonExe
  }

  $installerName = if ($pythonArch -eq "amd64") { "python-$pythonVersion-amd64.exe" } else { "python-$pythonVersion.exe" }
  $installerUrl = "https://www.python.org/ftp/python/$pythonVersion/$installerName"
  $installerPath = Join-Path $projectRoot $installerName

  Write-Host "Python not found. Downloading $installerUrl..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath | Out-Null

  Write-Host "Installing bundled Python to $bundledPythonDir..."
  if (Test-Path $bundledPythonDir) {
    Remove-Item $bundledPythonDir -Recurse -Force
  }
  $installArgs = @(
    "/quiet",
    "InstallAllUsers=0",
    "PrependPath=0",
    "Include_test=0",
    "TargetDir=$bundledPythonDir"
  )
  $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
  if ($process.ExitCode -ne 0) {
    throw "Bundled Python installer exited with code $($process.ExitCode)."
  }

  try {
    Remove-Item $installerPath -Force
  } catch {
    Write-Warning "Unable to remove installer at $installerPath. You may delete it manually."
  }

  if (!(Test-Path $bundledPythonExe)) {
    throw "Bundled Python installation failed. Ensure you can download and run the installer."
  }

  return $bundledPythonExe
}

if (!(Test-Path $pythonExe)) {
  $systemPython = Install-BundledPython

  & $systemPython -m venv $venvPath
  $venvCreated = ($LASTEXITCODE -eq 0) -and (Test-Path $pythonExe)

  if (-not $venvCreated) {
    Write-Host "Standard venv module unavailable. Installing virtualenv..."
    & $systemPython -m pip install --upgrade pip virtualenv
    & $systemPython -m virtualenv $venvPath
    $venvCreated = ($LASTEXITCODE -eq 0) -and (Test-Path $pythonExe)
  }

  if (-not $venvCreated) {
    throw "Python virtual environment creation failed. Ensure Python 3, venv, or virtualenv are available."
  }
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $projectRoot "requirements.txt")

$cardsPath = Join-Path $projectRoot "assets\cards.json"
try {
  & $pythonExe (Join-Path $projectRoot "tools\download_cards_db.py")
} catch {
  if (!(Test-Path $cardsPath)) {
    throw "Card database download failed and assets/cards.json is missing. Aborting."
  }
}

$pyinstaller = Join-Path $venvPath "Scripts\pyinstaller.exe"
$assetsDir = Join-Path $projectRoot "assets"
$separator = ";"

& $pyinstaller --onefile --noconsole --name "YGODecklistTool" `
  --add-data "$assetsDir\cards.json${separator}assets" `
  --add-data "$assetsDir\rarity_hierarchy_main.json${separator}assets" `
  --add-data "$assetsDir\rarity_hierarchy_extra_side.json${separator}assets" `
  (Join-Path $projectRoot "src\main.py")
