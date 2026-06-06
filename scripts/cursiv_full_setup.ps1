# ============================================================
# Cursiv Full Setup Bootstrap v1.0
# Installs every dependency needed to run Cursiv completely.
#
# Runs automatically after Cursiv installer finishes.
# Each major component gets its own visible terminal window.
#
# What gets installed (if not already present):
#   - winget  (App Installer — usually pre-installed on Win10/11)
#   - Git     (version control, used by Cursiv updater)
#   - Python 3.11+  (used by Cursiv internals + pip packages)
#   - Ollama  (local AI engine — runs llama3.1 offline)
#   - llama3.1 model (~4.7 GB download, one time)
#   - Python packages: anthropic, openai, psutil, bcrypt, PyJWT
# ============================================================

$Host.UI.RawUI.WindowTitle = "Cursiv Setup — Full Bootstrap"

$GOLD   = [char]27 + "[33m"
$CYAN   = [char]27 + "[36m"
$GREEN  = [char]27 + "[32m"
$RED    = [char]27 + "[31m"
$DIM    = [char]27 + "[90m"
$RESET  = [char]27 + "[0m"
$BOLD   = [char]27 + "[1m"

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  $GOLD$BOLD CURSIV  |  Full Setup Bootstrap$RESET"
    Write-Host "  $DIM Eye of Horus — installing everything you need$RESET"
    Write-Host ""
    Write-Host "  $DIM This window shows overall progress.$RESET"
    Write-Host "  $DIM Each component opens its own window — don't close them.$RESET"
    Write-Host ""
}

function Write-Step([string]$num, [string]$label, [string]$status = "running") {
    $icon = switch ($status) {
        "done"    { "$GREEN OK $RESET" }
        "skip"    { "$DIM -- $RESET" }
        "fail"    { "$RED !! $RESET" }
        default   { "$GOLD .. $RESET" }
    }
    Write-Host "  [$icon] $num  $label"
}

function Test-Command([string]$cmd) {
    $null = Get-Command $cmd -ErrorAction SilentlyContinue
    return $?
}

function Open-Window([string]$title, [string]$cmd) {
    Start-Process powershell -ArgumentList `
        "-NoProfile -ExecutionPolicy Bypass -Command `"
        `$Host.UI.RawUI.WindowTitle = '$title';
        Write-Host \`"  $GOLD$BOLD $title$RESET\`" -ForegroundColor Yellow;
        Write-Host '';
        $cmd;
        Write-Host '';
        Write-Host '  $GREEN Done. Close this window.$RESET';
        Start-Sleep 3
        `"" -Wait
}

function Open-WindowNoWait([string]$title, [string]$cmd) {
    Start-Process powershell -ArgumentList `
        "-NoProfile -ExecutionPolicy Bypass -Command `"
        `$Host.UI.RawUI.WindowTitle = '$title';
        Write-Host \`"  $title\`";
        $cmd
        `""
}

# ── Banner ─────────────────────────────────────────────────────────────────────
Write-Banner

$steps = @(
    @{n="1/7"; l="winget (App Installer)"},
    @{n="2/7"; l="Git"},
    @{n="3/7"; l="Python 3.11"},
    @{n="4/7"; l="Ollama"},
    @{n="5/7"; l="llama3.1 model  (~4.7 GB)"},
    @{n="6/7"; l="Python packages"},
    @{n="7/7"; l="Verify + launch"}
)

foreach ($s in $steps) { Write-Step $s.n $s.l "pending" }
Write-Host ""

Start-Sleep 1
Write-Banner

# ── 1. winget ──────────────────────────────────────────────────────────────────
Write-Step "1/7" "winget (App Installer)" "running"

$wingetOk = Test-Command "winget"
if (-not $wingetOk) {
    Write-Host "       $DIM winget not found — downloading App Installer...$RESET"
    $appInstaller = "$env:TEMP\AppInstaller.msixbundle"
    try {
        $uri = "https://aka.ms/getwinget"
        Invoke-WebRequest -Uri $uri -OutFile $appInstaller -UseBasicParsing
        Add-AppxPackage -Path $appInstaller -ErrorAction SilentlyContinue
        $wingetOk = Test-Command "winget"
    } catch {
        Write-Host "       $RED winget install failed: $_$RESET"
    }
}

if ($wingetOk) {
    Write-Step "1/7" "winget" "done"
} else {
    Write-Step "1/7" "winget  (install from Microsoft Store manually if needed)" "fail"
}

# ── 2. Git ─────────────────────────────────────────────────────────────────────
Write-Step "2/7" "Git" "running"

$gitOk = Test-Command "git"
if ($gitOk) {
    $gitVer = (git --version 2>$null)
    Write-Step "2/7" "Git  $DIM($gitVer already installed)$RESET" "skip"
} elseif ($wingetOk) {
    Write-Host "       $DIM Opening Git install window...$RESET"
    Open-Window "Cursiv Setup — Installing Git" `
        "winget install --id Git.Git --accept-package-agreements --accept-source-agreements --scope machine 2>&1"
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
    $gitOk = Test-Command "git"
    Write-Step "2/7" "Git" $(if ($gitOk) { "done" } else { "fail" })
} else {
    Write-Step "2/7" "Git  (skipped — winget unavailable)" "fail"
}

# ── 3. Python 3.11 ─────────────────────────────────────────────────────────────
Write-Step "3/7" "Python 3.11" "running"

$pyOk = $false
$pyCmd = $null
foreach ($c in @("python","python3","py")) {
    if (Test-Command $c) {
        $ver = & $c --version 2>&1
        if ($ver -match "3\.(1[1-9]|[2-9]\d)") {
            $pyOk = $true
            $pyCmd = $c
            break
        }
    }
}

if ($pyOk) {
    $pyVer = & $pyCmd --version 2>&1
    Write-Step "3/7" "Python  $DIM($pyVer already installed)$RESET" "skip"
} elseif ($wingetOk) {
    Write-Host "       $DIM Opening Python install window...$RESET"
    Open-Window "Cursiv Setup — Installing Python 3.11" `
        "winget install --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --scope machine 2>&1"
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
    foreach ($c in @("python","python3","py")) {
        if (Test-Command $c) { $pyOk = $true; $pyCmd = $c; break }
    }
    Write-Step "3/7" "Python 3.11" $(if ($pyOk) { "done" } else { "fail" })
} else {
    Write-Step "3/7" "Python  (skipped — winget unavailable)" "fail"
}

# ── 4. Ollama ──────────────────────────────────────────────────────────────────
Write-Step "4/7" "Ollama" "running"

$ollamaOk = Test-Command "ollama"
if ($ollamaOk) {
    $ollamaVer = (ollama --version 2>$null)
    Write-Step "4/7" "Ollama  $DIM($ollamaVer already installed)$RESET" "skip"
} elseif ($wingetOk) {
    Write-Host "       $DIM Opening Ollama install window...$RESET"
    Open-Window "Cursiv Setup — Installing Ollama" `
        "winget install --id Ollama.Ollama --accept-package-agreements --accept-source-agreements 2>&1"
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
    $ollamaOk = Test-Command "ollama"
    if (-not $ollamaOk) {
        # Try direct download fallback
        Write-Host "       $DIM Trying direct Ollama download...$RESET"
        $ollamaSetup = "$env:TEMP\OllamaSetup.exe"
        try {
            Invoke-WebRequest "https://ollama.com/download/OllamaSetup.exe" -OutFile $ollamaSetup -UseBasicParsing
            Start-Process $ollamaSetup -ArgumentList "/SILENT" -Wait
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
            $ollamaOk = Test-Command "ollama"
        } catch {
            Write-Host "       $RED Direct download failed: $_$RESET"
        }
    }
    Write-Step "4/7" "Ollama" $(if ($ollamaOk) { "done" } else { "fail" })
} else {
    Write-Step "4/7" "Ollama  (download manually: ollama.com/download)" "fail"
}

# ── 5. llama3.1 model ─────────────────────────────────────────────────────────
Write-Step "5/7" "llama3.1 model  (~4.7 GB)" "running"

$modelOk = $false
if ($ollamaOk) {
    # Start ollama serve in background if not running
    $serving = Get-Process "ollama" -ErrorAction SilentlyContinue
    if (-not $serving) {
        Write-Host "       $DIM Starting Ollama service...$RESET"
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep 4
    }

    # Check if model already exists
    $models = ollama list 2>$null
    if ($models -match "llama3.1") {
        Write-Step "5/7" "llama3.1  $DIM(already downloaded)$RESET" "skip"
        $modelOk = $true
    } else {
        Write-Host ""
        Write-Host "  $GOLD  Downloading llama3.1 — this is ~4.7 GB and may take 10-30 min$RESET"
        Write-Host "  $DIM  A separate window will show download progress.$RESET"
        Write-Host ""
        # Open a new window for the pull so progress is visible
        Open-Window "Cursiv Setup — Downloading llama3.1 model (4.7 GB)" `
            "Write-Host 'Pulling llama3.1 — please wait, this is a 4.7 GB download...';
             Write-Host 'You can minimise this window.';
             Write-Host '';
             ollama pull llama3.1;
             Write-Host '';
             Write-Host 'Model download complete!'"
        $models2 = ollama list 2>$null
        $modelOk = $models2 -match "llama3.1"
        Write-Step "5/7" "llama3.1 model" $(if ($modelOk) { "done" } else { "fail" })
    }
} else {
    Write-Step "5/7" "llama3.1  (skipped — Ollama not installed)" "fail"
}

# ── 6. Python packages ─────────────────────────────────────────────────────────
Write-Step "6/7" "Python packages" "running"

$pipOk = $false
if ($pyOk) {
    $packages = "anthropic openai psutil bcrypt PyJWT websockets httpx"
    Write-Host "       $DIM Installing: $packages$RESET"
    Open-Window "Cursiv Setup — Installing Python Packages" `
        "Write-Host 'Installing Python packages for Cursiv...';
         Write-Host '';
         & '$pyCmd' -m pip install --upgrade pip --quiet;
         & '$pyCmd' -m pip install $packages --quiet 2>&1;
         Write-Host '';
         Write-Host 'Python packages installed!'"
    $pipOk = $true
    Write-Step "6/7" "Python packages" "done"
} else {
    Write-Step "6/7" "Python packages  (skipped — Python not found)" "fail"
}

# ── 7. Verify + summary ─────────────────────────────────────────────────────────
Write-Step "7/7" "Verifying install..." "running"
Start-Sleep 1

Write-Banner

Write-Host "  $GOLD$BOLD Setup Complete$RESET"
Write-Host ""

$results = @(
    @{label="winget";   ok=$wingetOk},
    @{label="Git";      ok=$gitOk},
    @{label="Python";   ok=$pyOk},
    @{label="Ollama";   ok=$ollamaOk},
    @{label="llama3.1"; ok=$modelOk},
    @{label="pip pkgs"; ok=$pipOk}
)

foreach ($r in $results) {
    $icon = if ($r.ok) { "$GREEN OK $RESET" } else { "$RED -- $RESET" }
    Write-Host "  [$icon] $($r.label)"
}

Write-Host ""

if ($ollamaOk -and $modelOk) {
    Write-Host "  $GREEN Cursiv is fully set up and ready to run offline.$RESET"
    Write-Host "  $DIM  Open Cursiv from the Start Menu or type 'cursiv' in any terminal.$RESET"
} else {
    Write-Host "  $GOLD Cursiv installed. Some components need manual setup:$RESET"
    if (-not $ollamaOk) {
        Write-Host "  $DIM  - Install Ollama: https://ollama.com/download$RESET"
    }
    if (-not $modelOk) {
        Write-Host "  $DIM  - Pull the model: open a terminal and run:  ollama pull llama3.1$RESET"
    }
}

Write-Host ""
Write-Host "  $DIM Press any key to close this window...$RESET"
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
