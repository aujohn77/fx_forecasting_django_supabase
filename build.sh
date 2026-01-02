#!/usr/bin/env bash
set -euo pipefail

echo "==> Initializing submodules"
git submodule sync --recursive
git submodule update --init --recursive

echo "==> Locating dop_apps inside external_apps (submodule)"
DOP_PARENT="$(find "$(pwd)/external_apps" -maxdepth 4 -type d -name dop_apps -print -quit | xargs -r dirname || true)"

if [ -z "${DOP_PARENT}" ]; then
  echo "ERROR: dop_apps folder not found under external_apps after submodule update."
  echo "Check your submodule path and contents."
  exit 1
fi

echo "==> Adding to PYTHONPATH: ${DOP_PARENT}"
export PYTHONPATH="${PYTHONPATH:-}:${DOP_PARENT}"

echo "==> Installing dependencies"
pip install -r requirements.txt

echo "==> Django collectstatic + migrate"
python manage.py collectstatic --noinput
python manage.py migrate
