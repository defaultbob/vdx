#!/bin/bash
set -e

echo "Updating version and rebuilding VSIX..."
cd vscode-extension
npm version patch
rm -f *.vsix
vsce package
echo "Done! New VSIX created."
