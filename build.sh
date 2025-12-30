#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🔁 Initializing submodules"
git submodule sync --recursive
git submodule update --init --recursive

echo "📦 Installing dependencies"
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
