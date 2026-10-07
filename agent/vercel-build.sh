#!/usr/bin/env bash
# Runs on every Vercel deploy: refresh events with the weekly agent, then publish.
# Uses the YOU_COM_API environment variable set in the Vercel project. Never fails the deploy:
# if anything goes wrong, the last committed public/data/events.json is published as-is.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
echo "== TechEvents agent: refreshing events =="
if [ "${SKIP_AGENT:-}" = "1" ]; then
  echo "SKIP_AGENT=1, publishing existing data"
elif command -v python3 >/dev/null 2>&1; then
  if ! python3 -m pip install --quiet --disable-pip-version-check --target "$HERE/.pydeps" -r requirements.txt 2>/dev/null; then
    python3 -m ensurepip >/dev/null 2>&1
    python3 -m pip install --quiet --target "$HERE/.pydeps" -r requirements.txt 2>/dev/null || echo "!! could not install requests"
  fi
  if PYTHONPATH="$HERE/.pydeps" timeout 2400 python3 run.py; then
    echo "== agent finished =="
    cat ../public/data/agent-report.json 2>/dev/null || true
  else
    echo "!! agent failed — publishing last saved events"
  fi
else
  echo "!! python3 not available in this build image — publishing last saved events"
fi
exit 0
