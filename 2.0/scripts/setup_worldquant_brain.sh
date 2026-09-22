#!/usr/bin/env bash
# Sets up WorldQuant BRAIN access on macOS or Linux, then runs Phase 0.
#
# Run from the repository root:
#     bash 2.0/scripts/setup_worldquant_brain.sh
#
# The companion .ps1 is Windows-only and cannot run here; this machine is Darwin and has
# no pwsh, which is what blocked the 2026-09-22 session at task 1.
#
# The password is read with `read -s`, so it is never echoed to the terminal and never
# reaches shell history -- unlike passing it as an argument. It is written to
# ~/.worldquant_brain.json, outside the repository, and that filename is gitignored
# (.gitignore:6) so it cannot be committed by accident. The file is chmod 600.
#
# The password is never printed, logged, or passed on a command line: it goes to python's
# stdin, and python writes the JSON with json.dumps so quotes, backslashes and non-ASCII
# are encoded correctly.

set -euo pipefail

say() { printf '%s\n' "$*"; }

say "WorldQuant BRAIN setup"
say ""

# --- 1. confirm we are in the repository --------------------------------------------
SCRIPT="2.0/scripts/run_worldquant_brain_decile_ladder_v1.py"
if [ ! -f "$SCRIPT" ]; then
    say "Not in the repository root (cannot see $SCRIPT)."
    say "cd into your atlas-allocation folder and run this again."
    exit 1
fi
say "[ok] repository found"

# --- 2. python and requests ----------------------------------------------------------
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    say "python3 is not on PATH. Install it, then run this again."
    exit 1
fi
say "[ok] python: $("$PY" --version 2>&1)"

# A venv keeps this off the system python, which on macOS is externally managed and will
# refuse a bare `pip install`.
VENV="${WQ_VENV:-$HOME/.worldquant_brain_venv}"
if [ ! -x "$VENV/bin/python" ]; then
    say "creating venv at $VENV ..."
    "$PY" -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c "import requests" >/dev/null 2>&1; then
    say "installing requests ..."
    "$VENV/bin/pip" install --quiet requests
fi
say "[ok] requests available in $VENV"

# --- 3. credentials ------------------------------------------------------------------
CREDS="$HOME/.worldquant_brain.json"
WRITE=yes
if [ -f "$CREDS" ]; then
    printf 'Credentials already exist at %s. Overwrite? (y/N) ' "$CREDS"
    read -r ANSWER
    [ "$ANSWER" = "y" ] || { WRITE=no; say "keeping the existing file"; }
fi

if [ "$WRITE" = yes ]; then
    say ""
    say "If you have pasted this password anywhere public, change it on the platform first."
    printf 'BRAIN email: '
    read -r EMAIL
    printf 'BRAIN password (hidden): '
    read -rs PASSWORD
    printf '\n'

    umask 077
    # Password travels on stdin, never argv (argv is visible to `ps`).
    printf '%s' "$PASSWORD" | "$VENV/bin/python" -c '
import json, os, sys
password = sys.stdin.read()
path = os.path.expanduser("~/.worldquant_brain.json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump({"email": sys.argv[1], "password": password}, handle)
' "$EMAIL"
    unset PASSWORD
    chmod 600 "$CREDS"
    say "[ok] credentials written to $CREDS (mode 600, gitignored)"
fi

# --- 4. Phase 0 -----------------------------------------------------------------------
say ""
say "Running Phase 0 -- downloading the field dictionaries ..."
say ""
if ! "$VENV/bin/python" "$SCRIPT" --phase0; then
    say ""
    say "Phase 0 failed. Paste the error above back into the conversation."
    exit 1
fi

say ""
say "Done. Copy everything under the PASTE EVERYTHING BELOW THIS LINE marker"
say "and paste it back into the conversation."
