# Деплой «Биржи намерений» на corelia.uz

> **Как развёрнуто на самом деле (8 ноября).** На VM уже стоял Caddy с сертификатом corelia.uz и старый
> «UZEX Data Agent» (`uzex.service`, 127.0.0.1:8000) — его не трогали. Поэтому вместо nginx+certbot используется
> `deploy/Caddyfile` (`/etc/caddy/Caddyfile`, старый сохранён как `Caddyfile.bak-uzex-agent`), а `intent-api`
> слушает **127.0.0.1:8001**. nginx отключён (`systemctl disable nginx`). Обновление кода: `deploy/update.sh`
> как и раньше; конфиг прокси: `sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo caddy validate --config
> /etc/caddy/Caddyfile && sudo systemctl reload caddy`. Код скопирован tar'ом (не git clone): перед `git pull`
> на сервере нужно настроить доступ к репозиторию. Файлы из Windows имеют CRLF — после копирования
> `sed -i 's/$//' deploy/* scripts/*`. Зависимости закреплены в `backend/pyproject.toml`
> (pandas<3, duckdb<2): на свежих версиях сборка базы падала.

Сервер: Azure VM `uzex-agent` (группа `UZEX-RG`, Ubuntu 24.04, Standard_B2als_v2 — 2 vCPU, 4 ГБ ОЗУ),
статический IP `9.205.157.141`, домен `corelia.uz` уже указывает на него, открыты порты 22/80/443.

```
браузер ──https──▶ nginx :443 ──┬── /            статика фронта из /var/www/intent
                                └── /api/…  ──▶ uvicorn 127.0.0.1:8000 (systemd: intent-api, 1 процесс)
```

Файлы этой папки:

| файл | куда на сервере | что делает |
|---|---|---|
| `setup.sh` | запускается один раз | пакеты, часовой пояс Ташкента, swap, клон, venv, `.env`, база, systemd, nginx, сертификат |
| `update.sh` | запускается при каждом выкате | `git pull`, зависимости, перезапуск, проверка `/health`, сам откатывается, если сервис не поднялся |
| `intent-api.service` | `/etc/systemd/system/` | uvicorn под `azureuser`, `ENV=prod`, `Restart=always` |
| `nginx.conf` | `/etc/nginx/sites-available/intent` | статика, `/api/` → uvicorn, лимиты, заголовки безопасности, gzip, страница «сервис перезапускается» |

---

## Перед деплоем спросить

Эти четыре вопроса решает владелец проекта, по ним не угадываем:

1. **SSH-ключ.** Есть ли на ноутбуке ключ, с которым пускает `ssh azureuser@corelia.uz`? Проверка:
   `ssh -o BatchMode=yes azureuser@corelia.uz echo ok`. Если ключа нет — добавить его через портал Azure
   (VM → Reset password → Reset SSH public key) или `az vm user update -g UZEX-RG -n uzex-agent -u azureuser --ssh-key-value ~/.ssh/id_ed25519.pub`.
2. **Как клонировать приватный репозиторий `vexi1es/uzex-intent` на сервер.** Два варианта:
   - *deploy key* (рекомендуется: доступ только на чтение, только к этому репозиторию). На сервере
     `ssh-keygen -t ed25519 -f ~/.ssh/uzex_deploy -N ""`, вывести `cat ~/.ssh/uzex_deploy.pub`, владелец добавляет его
     в GitHub → repo → Settings → Deploy keys (без права записи); затем в `~/.ssh/config` на сервере:
     `Host github.com` / `IdentityFile ~/.ssh/uzex_deploy`. В `setup.sh` — `REPO=git@github.com:vexi1es/uzex-intent.git` (по умолчанию).
   - *его `gh auth login` на сервере* — токен владельца с доступом ко всем его репозиториям остаётся на VM.
     Тогда `REPO=https://github.com/vexi1es/uzex-intent.git`.
3. **Ключи API для `.env` сервера**: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`. Их вписывает
   владелец сам, прямо на сервере (`nano /opt/uzex-intent/.env`), в репозиторий и чаты не кладём. Без ключей всё
   работает офлайн-разбором, голос недоступен.
4. **Cloudflare.** Переводить ли домен на Cloudflare Free (прокси, защита от DDoS, кэш статики). Это смена NS
   у регистратора — только с его согласия; инструкция ниже, раздел «Cloudflare».

И ещё: **e-mail для Let's Encrypt** (`CERT_EMAIL`) — на него приходят напоминания об истечении сертификата;
запуск `certbot ... --agree-tos` означает согласие владельца с условиями Let's Encrypt.

---

## Первый выкат

С ноутбука (PowerShell или Git Bash; нужен `az` с входом в подписку):

```bash
az vm start -g UZEX-RG -n uzex-agent
```

```bash
ssh azureuser@corelia.uz
```

С ноутбука положить скрипт на сервер (из корня репозитория):

```bash
scp deploy/setup.sh azureuser@corelia.uz:~/
```

На сервере (после того как решён вопрос 2 и, если выбран deploy key, ключ добавлен в GitHub):

```bash
REPO=git@github.com:vexi1es/uzex-intent.git CERT_EMAIL=<email владельца> bash ~/setup.sh
```

Скрипт печатает 10 кодов жюри (для карточек) и создаёт `/opt/uzex-intent/.env` с правами 600:
`ENV=prod`, `DEMO_OFFLINE=0`, `DEMO_CLOCK=live`, `WHISPER_MODEL=` (пусто — GPU на сервере нет, голос только через
ElevenLabs и только для жюри), `AUTOCLOSE_MIN=10`, сгенерированные `JURY_CODES`, `ADMIN_TOKEN`, `AUTH_SECRET`.
Затем владелец вписывает ключи API и перезапускает:

```bash
nano /opt/uzex-intent/.env
```

```bash
sudo systemctl restart intent-api && curl -s http://127.0.0.1:8000/health
```

`/health` должен ответить `"protected": true`. Коды и секрет ведущего потом посмотреть: `grep -E 'JURY|ADMIN' /opt/uzex-intent/.env`.
Напечатать карточки можно и на ноутбуке: `python scripts/gen_codes.py --html cards.html` создаст новые коды —
тогда их же надо вписать в `.env` сервера.

### Фронт

Собирается на ноутбуке (на VM 4 ГБ — `npm run build` там лучше не запускать), выкладывается архивом через ssh
(работает и в PowerShell, и в Git Bash, rsync не нужен):

```bash
cd frontend && npm ci && npm run build
```

```bash
tar -C frontend/dist -czf - . | ssh azureuser@corelia.uz "rm -rf /var/www/intent/* && tar -C /var/www/intent -xzf -"
```

Фронт в проде ходит на `/api` (как прокси Vite в dev), отдельный адрес не нужен. Цель по размеру — ≤ 350 КБ gzip:
`du -sh frontend/dist/assets` и `gzip -c frontend/dist/assets/*.js | wc -c`.

### HTTPS

Если `CERT_EMAIL` был задан, `setup.sh` уже выпустил сертификат и включил редирект http → https.
Иначе вручную: `sudo certbot --nginx -d corelia.uz --redirect -m <email> --agree-tos`.
После выпуска включить HSTS: в `/etc/nginx/sites-available/intent` раскомментировать строку
`Strict-Transport-Security`, затем `sudo nginx -t && sudo systemctl reload nginx`. Продление certbot делает сам (таймер systemd).

### Проверка после выката

```bash
curl -s https://corelia.uz/api/health
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://corelia.uz/api/docs
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://corelia.uz/api/demo/reset
```

Ждём: `{"ok":true,…,"protected":true}`, `404`, `403`. В браузере: сайт открывается, `Ещё → Код доступа` пускает по коду,
у гостя нет микрофона и кнопки «Закрыть корзину».

---

## Повторный выкат

Бэкенд (на сервере):

```bash
bash /opt/uzex-intent/deploy/update.sh
```

Фронт — с ноутбука, теми же двумя командами из раздела «Фронт». Если сервис после `update.sh` не ответил на `/health`
за 20 с, скрипт сам возвращает прежний коммит и перезапускает (коммит записан в `/opt/uzex-intent/logs/last_good_commit`).

## Откат вручную

```bash
bash /opt/uzex-intent/deploy/update.sh $(cat /opt/uzex-intent/logs/last_good_commit)
```

Любой другой коммит: `bash /opt/uzex-intent/deploy/update.sh <sha>`. Вернуться на ветку: `bash /opt/uzex-intent/deploy/update.sh`
(без аргумента — `master`). Фронт откатывается выкладкой прежней сборки.

## Логи

| что | где |
|---|---|
| приложение (старт, ошибки, автозакрытие) | `journalctl -u intent-api -f` |
| 4xx/5xx и срабатывания лимитов: IP, уровень, путь | `/opt/uzex-intent/logs/access.log` (ротация 10 МБ × 5) |
| прогоны клиринга (вход и выход движка) | `/opt/uzex-intent/logs/clearing/*.json` |
| nginx (без query string — в ссылках бывают коды) | `/var/log/nginx/intent.access.log`, `intent.error.log` |

Состояние лимитов и автозакрытия — ведущему: `curl -s -H "X-Admin-Token: <ADMIN_TOKEN>" http://127.0.0.1:8000/auth/limits`.

## Управление в день демо

- **Ведущий**: `https://corelia.uz/more?admin=<ADMIN_TOKEN>` — фронт кладёт секрет в sessionStorage и шлёт заголовком
  `X-Admin-Token`; доступны сброс демо, шаги сценария, «Закрыть корзину сейчас». `?admin=1` ничего не даёт.
- **Жюри**: код с карточки в `Ещё → Код доступа` или ссылка `https://corelia.uz/?k=<КОД>`; cookie на 24 ч.
  Лимиты на код: LLM 30/ч (и 300/день на всех), голос 20/ч. Отозвать код — убрать из `JURY_CODES` и
  `sudo systemctl restart intent-api`.
- **Корзина** закрывается сама каждые 10 минут (11:40, 11:50, …), если в ней есть новые поручения.
  Чаще/реже — `AUTOCLOSE_MIN` в `.env`, выключить — `AUTOCLOSE_MIN=0`.
- **Перезапуск сбрасывает книгу** к сценарию 2035: поручения живут в памяти процесса. Поэтому воркер один
  (два воркера — две разные книги, см. `docs/LOADTEST.md`).
- **QR для зала на питче**: все гости за одним Wi-Fi — один IP. Подписей с одного IP — не больше 20 в час
  (`RL_SIGN_IP_HOUR`); если зал будет подписывать массово, поднять до 200 и перезапустить.

## Защита — что включено

- Уровни `guest` / `jury` / `admin`; cookie `intent_access` (код жюри, 24 ч) и `intent_pid` (участник, 7 дней) —
  httpOnly, SameSite=Lax, Secure, подпись HMAC-SHA256 ключом `AUTH_SECRET`.
- Гость: только офлайн-разбор (`source: "offline"`), 10 разборов в минуту, 5 поручений в час; голос — 403.
- `/demo/reset`, `/demo/step/*`, `POST /clearing/run/*` — только с `X-Admin-Token`, иначе 403 и строка в логе.
- `/mandate/mine` и `/mandate/{id}` — только свои поручения (участник из cookie, не из query).
- Лимиты в приложении: 120 GET и 30 POST в минуту на клиента (IP + cookie), потолок на IP 2400/300 в минуту
  (на площадке все за одним NAT); 10 неверных кодов или секретов за 10 минут с IP → 429.
- Тело запроса ≤ 64 КБ (аудио ≤ 2 МБ, только жюри), фраза ≤ 500 символов, неизвестные ключи и числа вне
  `qty_t` 1…10 000, `max_price_t` 10 000…100 000 000 → 422.
- `/docs`, `/redoc`, `/openapi.json` выключены; CORS только `https://corelia.uz`.
- nginx: `limit_req` 40 r/s + burst 80 на IP, `limit_conn` 40, таймауты 10 с, CSP, `X-Frame-Options DENY`,
  `nosniff`, `Referrer-Policy`, HSTS после сертификата. В документе 11 было 20 r/s, burst 40, 20 соединений:
  порог поднят, потому что зал сидит за одним адресом. Поменять можно в двух строках в начале `nginx.conf`.

## Что не хранить на сервере

Только код, `data/raw` (CSV сделок) и `data/demo`. Видео, транскрипты, записи голоса, исследовательские материалы
на VM не копировать. Кэш STT/LLM (`data/cache/`) можно удалить в любой момент: `rm -rf /opt/uzex-intent/data/cache/*`.

## Cloudflare (только с согласия владельца)

1. Зарегистрироваться на cloudflare.com (Free), добавить сайт `corelia.uz`; Cloudflare сам импортирует DNS-записи —
   проверить, что `A corelia.uz → 9.205.157.141` есть и «проксирован» (оранжевое облако).
2. У регистратора домена заменить NS на два, которые выдаст Cloudflare (применяется от минут до суток).
3. SSL/TLS → режим **Full (strict)** (сертификат Let's Encrypt на сервере остаётся).
4. Чтобы приложение видело настоящие IP посетителей, а не адреса Cloudflare, в `nginx.conf` перед `server {` добавить
   `real_ip_header CF-Connecting-IP;` и строки `set_real_ip_from <диапазон>;` для всех диапазонов из
   https://www.cloudflare.com/ips/ ; затем `sudo nginx -t && sudo systemctl reload nginx`.
5. Включить «Under Attack mode» можно одной кнопкой, если начнётся поток запросов.
Откат: вернуть прежние NS у регистратора.

## Стоимость и остановка

Standard_B2als_v2 стоит порядка $0,04 в час (≈ $27–30 в месяц при круглосуточной работе; точная цена зависит от региона —
смотреть в портале Azure → VM → Cost). Статический IP — около $3,6 в месяц, диск — несколько долларов в месяц, они
оплачиваются и у остановленной VM. После демо:

```bash
az vm deallocate -g UZEX-RG -n uzex-agent
```

`deallocate` (а не просто `stop` изнутри ОС) прекращает оплату вычислений; статический IP при этом сохраняется.

## Если что-то не так

| симптом | что смотреть |
|---|---|
| сайт отдаёт 503 «Сервис перезапускается» | `systemctl status intent-api`, `journalctl -u intent-api -n 50` |
| `intent-api` не стартует: «Failed to set up mount namespacing» | нет папки из `ReadWritePaths`: `mkdir -p /opt/uzex-intent/logs /opt/uzex-intent/data/cache` |
| у всех гостей 429 | `tail /opt/uzex-intent/logs/access.log` — какой лимит; поднять `RL_*` в `.env`, перезапустить |
| время окон корзины не то | `timedatectl` — должен быть `Asia/Tashkent` |
| `nginx -t` ругается после certbot | certbot дописал блоки 443 в `/etc/nginx/sites-available/intent`; новый `deploy/nginx.conf` переносить вручную |
