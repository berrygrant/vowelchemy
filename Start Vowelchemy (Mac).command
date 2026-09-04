#!/bin/sh
# Double-click me to set up and start Vowelchemy — no typing needed.
#
# First run: creates a private Python environment in this folder (.venv-app)
# and installs Vowelchemy into it (a few minutes, needs internet).
# Every run after that: starts instantly.
#
# macOS may warn that this file is "from an unidentified developer" the first
# time: right-click (or Control-click) it and choose Open instead.
#
# (This is a plain POSIX shell script, so on Linux you can run it with
#  `sh "Start Vowelchemy (Mac).command"`.)

set -u
cd "$(dirname "$0")" || exit 1

say_bye() {
    echo ""
    echo "$1"
    echo "Ask a labmate or your supervisor if you get stuck — copy the text above."
    printf "Press Return to close this window. "
    read -r _
    exit 1
}

command -v python3 >/dev/null 2>&1 || say_bye \
    "Python 3 was not found. Install it from https://www.python.org/downloads/ and double-click me again.
(If macOS pops up a dialog offering 'command line developer tools', that also works — install those.)"

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null || say_bye \
    "Your Python 3 is too old (Vowelchemy needs 3.9 or newer).
Install the current version from https://www.python.org/downloads/ and try again."

# Install on the first run, and re-install whenever the requirements change.
# The install is *editable*, so pulling new code takes effect on the next
# launch — otherwise this folder would keep running the version that was
# installed the very first time.
STAMP=".venv-app/.vowelchemy-stamp"
want=$(cksum pyproject.toml 2>/dev/null | cut -d' ' -f1,2 | tr ' ' '-')
have=$(cat "$STAMP" 2>/dev/null || true)

if [ ! -x ".venv-app/bin/vowelchemy" ]; then
    echo "First-time setup: installing Vowelchemy into a private environment."
    echo "This takes a few minutes and needs an internet connection..."
    python3 -m venv .venv-app || say_bye "Could not create the environment (.venv-app)."
    need_install=yes
elif [ "$want" != "$have" ]; then
    echo "Vowelchemy's requirements changed — updating (this may take a minute)..."
    need_install=yes
else
    need_install=no
fi

if [ "$need_install" = "yes" ]; then
    ./.venv-app/bin/python -m pip install --upgrade pip >/dev/null 2>&1
    ./.venv-app/bin/pip install -e . || say_bye \
        "Installing Vowelchemy failed. Check your internet connection and try again.
(To retry setup from scratch, delete the .venv-app folder first.)"
    printf '%s' "$want" > "$STAMP"
    echo "Setup complete."
fi

echo ""
./.venv-app/bin/vowelchemy doctor 2>/dev/null | sed -n '1,3p'
echo ""
echo "Starting Vowelchemy — your browser will open by itself in a moment."
echo "Keep this window open while you work; press Ctrl+C (or close the window) to stop."
echo ""
exec ./.venv-app/bin/vowelchemy app
