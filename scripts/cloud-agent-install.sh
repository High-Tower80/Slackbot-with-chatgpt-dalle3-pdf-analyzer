#!/usr/bin/env bash
set -euo pipefail

# Bootstrap a project venv. Ubuntu's python3 package does not include
# ensurepip unless python3.12-venv is installed, so `python3 -m venv`
# otherwise leaves a broken .venv without pip.

if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12-venv
fi

if [[ ! -x .venv/bin/pip ]]; then
  rm -rf .venv
  python3 -m venv .venv
fi

.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
