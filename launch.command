#!/bin/bash
# Double-click this file (Finder) to open the Graph Visualizer fully offline.
#
# Why a launcher: the app loads MediaPipe models from local files. Chrome
# blocks file:// pages from reading other local files (CORS, origin "null"),
# so a plain double-click of app.html leaves the hand-tracking model stuck.
# This launches Chrome with --allow-file-access-from-files, which lifts that
# block. A dedicated profile dir keeps the flag effective even if your normal
# Chrome is already open, and remembers the camera permission between runs.

DIR="$(cd "$(dirname "$0")" && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [ ! -x "$CHROME" ]; then
  echo "Google Chrome not found at: $CHROME"
  echo "Install Chrome or edit this path."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

open -na "Google Chrome" --args \
  --allow-file-access-from-files \
  --user-data-dir="$HOME/.nodeviz-chrome-profile" \
  "file://$DIR/app.html"
