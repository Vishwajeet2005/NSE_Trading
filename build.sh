#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing frontend dependencies and building..."
cd frontend
npm install
npm run build
cd ..

echo "Installing python dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt
