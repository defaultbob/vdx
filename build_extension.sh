#!/bin/bash
set -e

echo "Updating version and rebuilding VSIX..."
cd "$(dirname "$0")/vscode-extension"
npm version patch

VERSION=$(node -p "require('./package.json').version")
echo "VERSION = '$VERSION'" > ../vdx_project/vdx/version.py

rm -f *.vsix
npx @vscode/vsce package --no-dependencies
echo "Done! New VSIX created."
