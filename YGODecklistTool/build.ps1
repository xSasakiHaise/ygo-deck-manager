$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$bundledPythonDir = Join-Path $projectRoot ".python"
$bundledPythonExe = Join-Path $bundledPythonDir "python.exe"
$pythonVersion = "3.12.6"
$pythonArch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "win32" }

function Install-BundledPython {
  if (Test-Path $bundledPythonExe) {
    return $bundledPythonExe
  }

  $installerName = "python-$pythonVersion-$pythonArch.exe"
  $installerUrl = "https://www.python.org/ftp/python/$pythonVersion/$installerName"
  $installerPath = Join-Path $projectRoot $installerName

  Write-Host "Python not found. Downloading $installerUrl..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath

  Write-Host "Installing bundled Python to $bundledPythonDir..."
  & $installerPath /quiet InstallAllUsers=0 PrependPath=0 Include_pip=1 TargetDir="$bundledPythonDir"

  Remove-Item $installerPath -Force

  if (!(Test-Path $bundledPythonExe)) {
    throw "Bundled Python installation failed. Ensure you can download and run the installer."
  }

  return $bundledPythonExe
}

if (!(Test-Path $pythonExe)) {
  $systemPython = Install-BundledPython

  & $systemPython -m venv $venvPath
  if (!(Test-Path $pythonExe)) {
    throw "Python virtual environment creation failed. Ensure Python 3 and venv are available."
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
