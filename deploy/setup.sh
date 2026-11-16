#!/usr/bin/env bash
set -euo pipefail

APP=${APP:-/opt/uzex-intent}
WEB=${WEB:-/var/www/intent}
DOMAIN=${DOMAIN:-demo.example}
REPO=${REPO:-git@github.com:vexi1es/uzex-intent.git}   # deploy key; либо https после `gh auth login`
BRANCH=${BRANCH:-master}
CERT_EMAIL=${CERT_EMAIL:-}
RUN_USER=${RUN_USER:-azureuser}

say() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }

say "1/10 часовой пояс Ташкента (окна корзин 11:30/16:30 и автозакрытие считаются по часам сервера)"
sudo timedatectl set-timezone Asia/Tashkent

say "2/10 пакеты"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx python3.12-venv python3-pip certbot \
    python3-certbot-nginx git rsync curl

say "3/10 swap 2 ГБ (на B2als_v2 всего 4 ГБ ОЗУ)"
if ! swapon --show | grep -q /swapfile; then
    sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

say "4/10 код в $APP"
sudo mkdir -p "$APP" "$WEB"
sudo chown "$RUN_USER:$RUN_USER" "$APP" "$WEB"
if [[ "$REPO" == git@github.com:* ]] && ! grep -q '^github.com' ~/.ssh/known_hosts 2>/dev/null; then
    mkdir -p ~/.ssh && ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
fi
if [ ! -d "$APP/.git" ]; then
    git clone --branch "$BRANCH" "$REPO" "$APP"
else
    git -C "$APP" pull --ff-only
fi
mkdir -p "$APP/logs" "$APP/data/cache"

say "5/10 Python-окружение"
[ -d "$APP/.venv" ] || python3.12 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
python3.12 - "$APP/backend/pyproject.toml" > /tmp/intent-req.txt <<'PY'
import sys, tomllib
print("\n".join(tomllib.load(open(sys.argv[1], "rb"))["project"]["dependencies"]))
PY
"$APP/.venv/bin/pip" install -q -r /tmp/intent-req.txt

say "6/10 .env (секреты — только здесь, chmod 600)"
if [ ! -f "$APP/.env" ]; then
    gen=$(cd "$APP" && "$APP/.venv/bin/python" scripts/gen_codes.py --n 10)
    {
        echo "# создан setup.sh $(date -Iseconds). Ключи API впишите вручную (nano $APP/.env), затем:"
        echo "#   sudo systemctl restart intent-api"
        echo "ENV=prod"
        echo "DEMO_OFFLINE=0"
        echo "DEMO_CLOCK=live"
        echo "DEMO_SEED=2035"
        echo "WHISPER_MODEL="
        echo "AUTOCLOSE_MIN=10"
        echo "CORS_ORIGINS=https://$DOMAIN"
        echo "GEMINI_API_KEY="
        echo "ANTHROPIC_API_KEY="
        echo "ELEVENLABS_API_KEY="
        echo "$gen" | grep -E '^(JURY_CODES|ADMIN_TOKEN|AUTH_SECRET)='
    } > "$APP/.env"
    chmod 600 "$APP/.env"
    echo "Коды жюри для карточек:"; echo "$gen" | sed -n '/коды для карточек/,$p'
else
    echo ".env уже есть — не трогаю"
fi

say "7/10 база DuckDB из data/raw"
(cd "$APP" && "$APP/.venv/bin/python" scripts/build_db.py)

say "8/10 systemd: intent-api"
sudo cp "$APP/deploy/intent-api.service" /etc/systemd/system/intent-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now intent-api
sudo systemctl restart intent-api

say "9/10 nginx"
if [ ! -f "$WEB/index.html" ]; then
    echo '<!doctype html><meta charset="utf-8"><title>intent</title><p>Фронт ещё не выложен (deploy/README.md, шаг «Фронт»).</p>' > "$WEB/index.html"
fi
sudo cp "$APP/deploy/nginx.conf" /etc/nginx/sites-available/intent
sudo ln -sf /etc/nginx/sites-available/intent /etc/nginx/sites-enabled/intent
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
if [ -n "$CERT_EMAIL" ]; then
    sudo certbot --nginx -d "$DOMAIN" --redirect -m "$CERT_EMAIL" --agree-tos -n
    echo "Сертификат выпущен. Включите HSTS: раскомментируйте строку Strict-Transport-Security в"
    echo "  /etc/nginx/sites-available/intent и выполните sudo nginx -t && sudo systemctl reload nginx"
else
    echo "CERT_EMAIL не задан — HTTPS позже: sudo certbot --nginx -d $DOMAIN --redirect -m <email> --agree-tos"
fi

say "10/10 проверка"
for i in $(seq 1 20); do
    if curl -fsS http://127.0.0.1:8000/health; then echo; break; fi
    sleep 1
done
curl -fsS -o /dev/null -w "через nginx /api/health: %{http_code}\n" -H "Host: $DOMAIN" http://127.0.0.1/api/health
curl -s -o /dev/null -w "/api/docs (ждём 404): %{http_code}\n" -H "Host: $DOMAIN" http://127.0.0.1/api/docs
curl -s -o /dev/null -w "/api/demo/reset без токена (ждём 403): %{http_code}\n" -X POST -H "Host: $DOMAIN" http://127.0.0.1/api/demo/reset
echo "Готово. Логи: journalctl -u intent-api -f ; $APP/logs/access.log ; /var/log/nginx/"
