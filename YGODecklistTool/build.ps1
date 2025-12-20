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

  $archiveName = "python-$pythonVersion-embed-$pythonArch.zip"
  $archiveUrl = "https://www.python.org/ftp/python/$pythonVersion/$archiveName"
  $archivePath = Join-Path $projectRoot $archiveName

  Write-Host "Python not found. Downloading $archiveUrl..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath

  Write-Host "Extracting bundled Python to $bundledPythonDir..."
  if (Test-Path $bundledPythonDir) {
    Remove-Item $bundledPythonDir -Recurse -Force
  }
  New-Item -ItemType Directory -Path $bundledPythonDir | Out-Null
  Expand-Archive -Path $archivePath -DestinationPath $bundledPythonDir

  try {
    Remove-Item $archivePath -Force
  } catch {
    Write-Warning "Unable to remove archive at $archivePath. You may delete it manually."
  }

  $pthFile = Join-Path $bundledPythonDir "python$($pythonVersion.Split('.')[0])$($pythonVersion.Split('.')[1])._pth"
  if (Test-Path $pthFile) {
    $pthContent = Get-Content $pthFile
    if ($pthContent -notcontains "Lib\site-packages") {
      $pthContent = @("Lib\site-packages") + $pthContent
    }
    $pthContent = $pthContent | ForEach-Object { $_ -replace "^#import site$", "import site" }
    Set-Content -Path $pthFile -Value $pthContent
  }

  $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
  $getPipPath = Join-Path $projectRoot "get-pip.py"
  Write-Host "Bootstrapping pip..."
  Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath
  & $bundledPythonExe $getPipPath --no-warn-script-location
  Remove-Item $getPipPath -Force

  if (!(Test-Path $bundledPythonExe)) {
    throw "Bundled Python installation failed. Ensure you can download and extract the archive."
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
