# Setup Notes (HubClock)

## Services
- Backend: `PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- Frontend: `npm_config_cache=.cache/npm npm run dev -- --host 127.0.0.1 --port 5173`
- Provisioning script: `sudo ./scripts/setup_ubuntu.sh`
- Install systemd units: `sudo ./scripts/install_services.sh`

## Database
- Local MySQL via Homebrew (`brew install mysql`).
- `brew services start mysql` launches the daemon.
- Initial DB/user: `hubclock` / `hubclock`.
- Ensure schema with `curl -X POST http://127.0.0.1:8000/db/init`.

## Default Settings
- Currency: `ILS`
- Theme color: `#1b3aa6`
- Brand name: `דלי`
- PIN must be set via Settings UI or `PUT /settings` before accessing admin screens.
- Settings API: `GET/PUT /settings`, `POST /settings/import`, `GET /settings/export`.

## Frontend Access
- Clock-in page at `/` uses masked input and auto-detects state via `/clock/status`.
- Daily vs summary reports accessible under `/dashboard`; לחצן הייצוא שולח בקשת GET ל-`/reports/daily/export` או `/reports/export` בהתאם לסוג הדוח, עם פרמטר `include_payments` לבחירת הוספת רכיבי שכר.
- נתוני עובדים/משמרות ניתנים לייצוא ב-`GET /employees/export` ולהחזרה ב-`POST /employees/import` (עם דגל `replace_existing`).

## Notes for Codex Agents
- Key files: `backend/app/main.py`, `frontend/src/pages/ClockPage.tsx`, `frontend/src/pages/SettingsPage.tsx`.
- Refer to `docs/CHANGELOG.md` for the latest modifications history.
