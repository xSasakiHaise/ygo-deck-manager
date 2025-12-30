$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$bundledPythonDir = Join-Path $projectRoot "tools\.python"
$bundledPythonExe = Join-Path $bundledPythonDir "python.exe"
$pythonVersion = "3.12.6"
$pythonArch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "win32" }

function Resolve-SystemPython {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) {
    try {
      $pythonPath = & $pythonCommand.Source -c "import sys; print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $pythonPath) {
        return $pythonPath.Trim()
      }
    } catch {
      # Ignore and fall through to try other resolvers.
    }
  }

  $pyCommand = Get-Command py -ErrorAction SilentlyContinue
  if (-not $pyCommand) {
    return $null
  }

  try {
    $pythonPath = & $pyCommand.Source -3.12 -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -eq 0 -and $pythonPath) {
      return $pythonPath.Trim()
    }
  } catch {
    # Ignore and fall through to return null.
  }

  try {
    $pythonPath = & $pyCommand.Source -3 -c "import sys; print(sys.executable)"
    if ($LASTEXITCODE -eq 0 -and $pythonPath) {
      return $pythonPath.Trim()
    }
  } catch {
    # Ignore and fall through to return null.
  }

  return $null
}

function Install-BundledPython {
  param(
    [switch]$Force
  )

  $hadBundledPython = Test-Path $bundledPythonExe

  if ($Force -and (Test-Path $bundledPythonDir)) {
    Remove-Item $bundledPythonDir -Recurse -Force
  }

  if ((-not $Force) -and (Test-Path $bundledPythonExe)) {
    return $bundledPythonExe
  }

  $installerName = if ($pythonArch -eq "amd64") { "python-$pythonVersion-amd64.exe" } else { "python-$pythonVersion.exe" }
  $installerUrl = "https://www.python.org/ftp/python/$pythonVersion/$installerName"
  $installerPath = Join-Path $projectRoot $installerName

  Write-Host "Python not found. Downloading $installerUrl..."
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath | Out-Null

  Write-Host "Installing bundled Python to $bundledPythonDir..."
  if ($Force -and (Test-Path $bundledPythonDir)) {
    Remove-Item $bundledPythonDir -Recurse -Force
  }
  $installArgs = @(
    "/quiet",
    "InstallAllUsers=0",
    "PrependPath=0",
    "Include_test=0",
    "Include_lib=1",
    "Include_pip=1",
    "Include_vcruntime=1",
    "TargetDir=$bundledPythonDir"
  )
  $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru
  if ($process.ExitCode -eq 1638) {
    Write-Warning "Bundled Python installer reported an existing installation (code 1638). Falling back to system Python."
    if ($hadBundledPython -and (Test-Path $bundledPythonExe)) {
      return $bundledPythonExe
    }
    $systemPython = Resolve-SystemPython
    if ($systemPython) {
      return $systemPython
    }
    throw "Bundled Python installer returned code 1638, but no usable system Python was found. Disable the Microsoft Store Python alias or install Python 3.12+."
  }

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

& $pythonExe -c "import ctypes" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Bundled Python appears unhealthy (ctypes import failed). Reinstalling..."
  if (Test-Path $venvPath) {
    Remove-Item $venvPath -Recurse -Force
  }
  $systemPython = Install-BundledPython -Force
  & $systemPython -m venv $venvPath
  if ($LASTEXITCODE -ne 0) {
    throw "Python virtual environment creation failed after reinstall."
  }
  & $pythonExe -c "import ctypes" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Bundled Python is still unable to import ctypes. Please reinstall Python."
  }
}

& $pythonExe -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) {
  & $pythonExe -m ensurepip --upgrade
  if ($LASTEXITCODE -ne 0) {
    throw "pip bootstrap failed. Ensure Python includes ensurepip."
  }
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $projectRoot "requirements.txt")

$cardsPath = Join-Path $projectRoot "assets\cards.json"
$cardsDePath = Join-Path $projectRoot "assets\cards_de.json"
try {
  & $pythonExe (Join-Path $projectRoot "tools\download_cards_db.py")
} catch {
  if (!(Test-Path $cardsPath)) {
    throw "Card database download failed and assets/cards.json is missing. Aborting."
  }
}
if (!(Test-Path $cardsDePath)) {
  throw "Card database download failed and assets/cards_de.json is missing. Aborting."
}

$pyinstaller = Join-Path $venvPath "Scripts\pyinstaller.exe"
$assetsDir = Join-Path $projectRoot "assets"
$separator = ";"

& $pyinstaller --onefile --noconsole --name "YGODecklistTool" `
  --add-data "$assetsDir\cards.json${separator}assets" `
  --add-data "$assetsDir\cards_de.json${separator}assets" `
  --add-data "$assetsDir\rarity_hierarchy_main.json${separator}assets" `
  --add-data "$assetsDir\rarity_hierarchy_extra_side.json${separator}assets" `
  (Join-Path $projectRoot "src\main.py")
