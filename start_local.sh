#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv || true
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env || true
python app.py
