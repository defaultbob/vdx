#!/bin/bash
set -e

echo "Updating version and rebuilding VSIX..."
cd vscode-extension
npm version patch

VERSION=$(node -p "require('./package.json').version")
echo "VERSION = '$VERSION'" > ../vdx_project/vdx/version.py

rm -f *.vsix
vsce package
echo "Done! New VSIX created."
