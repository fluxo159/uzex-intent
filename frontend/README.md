# intent — фронтенд

React 18 + Vite + TypeScript + Tailwind + react-router + Recharts. Стиль G «терминал-тикет» (эталон `mvp_docs/design_preview_v3.html`), только тёмная тема, RU/UZ.

```bash
npm install
npm run dev        # против бэкенда: /api → http://127.0.0.1:8000 (VITE_BACKEND меняет адрес)
npm run dev:mock   # без бэкенда: ответы из src/api/fixtures (VITE_MOCK=1)
npm test           # Vitest
```

- Маршруты: `/` → `/intent` → `/card` → `/sign` → `/wait` → `/result` → `/why` → `/money`; отдельно `/plant`, `/market`, `/passport/:id`, `/radar`, `/compare`, `/guest`.
- Если бэкенд не отвечает или маршрута нет, конкретный вызов идёт в мок, а в футере загорается плашка «мок-данные».
- Фикстуры мока — настоящие ответы бэкенда на демо-сценарии (сид 2035), чисел «из головы» в них нет.
- Все строки — в `src/i18n/ru.json` и `uz.json`; тест проверяет, что в компонентах нет кириллицы и запрещённых слов.
