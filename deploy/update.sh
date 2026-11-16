#!/usr/bin/env bash
set -euo pipefail

APP=${APP:-/opt/uzex-intent}
BRANCH=${BRANCH:-master}
TARGET=${1:-}

say() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }

healthy() {
    for _ in $(seq 1 20); do
        if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then return 0; fi
        sleep 1
    done
    return 1
}

cd "$APP"
PREV=$(git rev-parse HEAD)
echo "$PREV" > "$APP/logs/last_good_commit"
say "сейчас: $(git log -1 --format='%h %s')"

git fetch --quiet origin
if [ -n "$TARGET" ]; then
    git checkout --quiet "$TARGET"
else
    git checkout --quiet "$BRANCH"
    git pull --ff-only --quiet origin "$BRANCH"
fi
say "новый: $(git log -1 --format='%h %s')"

python3.12 - "$APP/backend/pyproject.toml" > /tmp/intent-req.txt <<'PY'
import sys, tomllib
print("\n".join(tomllib.load(open(sys.argv[1], "rb"))["project"]["dependencies"]))
PY
"$APP/.venv/bin/pip" install -q -r /tmp/intent-req.txt

if ! git diff --quiet "$PREV" HEAD -- data/raw scripts/build_db.py; then
    say "data/raw изменились — пересобираю базу"
    "$APP/.venv/bin/python" scripts/build_db.py
fi
if ! git diff --quiet "$PREV" HEAD -- deploy/intent-api.service; then
    sudo cp deploy/intent-api.service /etc/systemd/system/intent-api.service && sudo systemctl daemon-reload
fi
if ! git diff --quiet "$PREV" HEAD -- deploy/nginx.conf; then
    echo "deploy/nginx.conf изменился. После certbot файл на сервере содержит блоки 443 — сравните вручную:"
    echo "  diff deploy/nginx.conf /etc/nginx/sites-available/intent"
fi

say "перезапуск"
sudo systemctl restart intent-api
if healthy; then
    curl -fsS http://127.0.0.1:8000/health; echo
    say "готово"
else
    say "НЕ ПОДНЯЛСЯ — откат на $PREV"
    sudo journalctl -u intent-api -n 40 --no-pager || true
    git checkout --quiet "$PREV"
    "$APP/.venv/bin/pip" install -q -r /tmp/intent-req.txt || true
    sudo systemctl restart intent-api
    healthy && echo "откат выполнен, сервис жив" || echo "и после отката не жив — смотрите journalctl -u intent-api"
    exit 1
fi
