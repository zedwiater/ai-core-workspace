#!/usr/bin/env bash
# One-command install: fetch the tree (or refresh it), then hand
# over to the installer, which does the rest — crawl, pairing,
# merge, deploy — and narrates as it goes.
# Tracks the repository's DEFAULT branch: the app home is the
# front door, never a side branch.
set -e
DIR="${AI_CORE_DIR:-$HOME/ai-core-workspace}"
if [ -d "$DIR/.git" ]; then
    git -C "$DIR" pull -q
else
    git clone -q https://github.com/zedwiater/ai-core-workspace.git "$DIR"
fi
cd "$DIR" && bash install.sh
