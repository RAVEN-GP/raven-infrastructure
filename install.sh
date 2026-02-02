#!/bin/bash

echo "🦅 Installing RAVEN Infrastructure..."

# 1. Install dependencies
echo "-> Installing Python dependencies..."
# pip3 install -r requirements.txt

# 2. Link CLI
echo "-> Linking 'raven' CLI to /usr/local/bin..."
chmod +x cli/raven.py
# sudo ln -nfs $(pwd)/cli/raven.py /usr/local/bin/raven

echo "✅ Installation Complete!"
echo "Try running: ./cli/raven.py status"
