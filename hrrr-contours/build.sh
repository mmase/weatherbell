#!/usr/bin/env bash
# Fetch the latest HRRR 2 m temperature analysis and build everything under web/.
set -euo pipefail
cd "$(dirname "$0")"
pip install -q -r requirements.txt
npm install --silent
mkdir -p data
python3 scripts/fetch_hrrr.py
python3 scripts/build_tiles.py
python3 scripts/build_glyphs.py
node scripts/build_boundaries.mjs
echo "Serve with: npx http-server web -p 8080   (then open http://localhost:8080)"
