#!/usr/bin/env bash
# The patcher: fetch the latest tree and re-run the installer.
# Re-running IS the designed patch path — the installer backs up
# the previous install, merges with the running system (your
# models, your tuned services), redeploys, and re-validates,
# door included. No uninstall needed to take a fix.
# For a full reset instead: bash install.sh uninstall, then
# bash install.sh.
set -e
cd "$(dirname "$0")"
echo "🔄 Pulling the latest tree..."
git pull -q
echo "🔧 Re-running the installer (merge + backup + redeploy)..."
bash install.sh
