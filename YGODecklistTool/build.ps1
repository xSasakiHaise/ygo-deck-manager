$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

function Resolve-Python {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) {
    return $pythonCommand.Source
  }

  $pyCommand = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCommand) {
    return "$($pyCommand.Source) -3"
  }

  return $null
}

if (!(Test-Path $pythonExe)) {
  $systemPython = Resolve-Python
  if (!$systemPython) {
    throw "Python was not found. Install Python 3 or enable the 'python'/'py' launcher, then rerun build.ps1."
  }

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
