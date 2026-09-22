# Sets up WorldQuant BRAIN access on a Windows machine, then runs Phase 0.
#
# Run from the repository root:
#     powershell -ExecutionPolicy Bypass -File 2.0\scripts\setup_worldquant_brain.ps1
#
# The password is read with Read-Host -AsSecureString, so it is never echoed to the
# screen and never lands in PSReadLine history -- unlike typing it into a command.
# It is written to %USERPROFILE%\.worldquant_brain.json, outside the repository, and
# that filename is gitignored so it cannot be committed by accident.

$ErrorActionPreference = "Stop"

function Say($text, $colour = "Gray") { Write-Host $text -ForegroundColor $colour }

Say "WorldQuant BRAIN setup" "Cyan"
Say ""

# --- 1. confirm we are in the repository -------------------------------------------
$script = Join-Path (Get-Location) "2.0\scripts\run_worldquant_brain_decile_ladder_v1.py"
if (-not (Test-Path $script)) {
    Say "Not in the repository root." "Red"
    Say "Open PowerShell inside your atlas-allocation folder and run this again."
    Say "(File Explorer -> open the folder -> click the address bar -> type powershell -> Enter)"
    exit 1
}
Say "[ok] repository found" "Green"

# --- 2. python and requests --------------------------------------------------------
try { $null = & python --version 2>&1 } catch {
    Say "Python is not on PATH. Install it from python.org, tick 'Add to PATH', reopen PowerShell." "Red"
    exit 1
}
Say "[ok] python: $(& python --version 2>&1)" "Green"

& python -c "import requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say "installing requests..."
    & python -m pip install --quiet requests
    if ($LASTEXITCODE -ne 0) { Say "pip install requests failed." "Red"; exit 1 }
}
Say "[ok] requests available" "Green"

# --- 3. credentials ----------------------------------------------------------------
$path = Join-Path $HOME ".worldquant_brain.json"
if (Test-Path $path) {
    $answer = Read-Host "Credentials already exist at $path. Overwrite? (y/N)"
    if ($answer -ne "y") { Say "keeping the existing file" }
}

if (-not (Test-Path $path) -or $answer -eq "y") {
    Say ""
    Say "If you have pasted this password anywhere public, change it on the platform first." "Yellow"
    $email  = Read-Host "BRAIN email"
    $secure = Read-Host "BRAIN password (hidden)" -AsSecureString

    $bstr  = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    # ConvertTo-Json handles quotes, backslashes and non-ASCII in the password correctly.
    [ordered]@{ email = $email; password = $plain } |
        ConvertTo-Json -Compress | Set-Content -Path $path -Encoding UTF8
    $plain = $null
    [GC]::Collect()

    try {
        & icacls $path /inheritance:r /grant:r "$env:USERNAME:(R,W)" | Out-Null
        Say "[ok] credentials written and locked to your account" "Green"
    } catch {
        Say "[ok] credentials written (could not tighten file permissions)" "Yellow"
    }
}

# --- 4. Phase 0 ---------------------------------------------------------------------
Say ""
Say "Running Phase 0 -- downloading the field dictionaries..." "Cyan"
Say ""
& python $script --phase0
if ($LASTEXITCODE -ne 0) {
    Say ""
    Say "Phase 0 failed. Paste the error above back into the conversation." "Red"
    exit $LASTEXITCODE
}

Say ""
Say "Done. Copy everything under the PASTE EVERYTHING BELOW THIS LINE marker" "Green"
Say "and paste it back into the conversation." "Green"
