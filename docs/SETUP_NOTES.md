# Setup Notes (HubClock)

## Services
- Backend: `PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- Frontend: `npm_config_cache=.cache/npm npm run dev -- --host 127.0.0.1 --port 5173`
- Provisioning script: `sudo ./scripts/setup_ubuntu.sh`
- Install systemd units:
  - Development (backend + Vite dev server): `sudo ./scripts/install_services.sh --dev`
  - Production (backend only, serves built frontend): `sudo ./scripts/install_services.sh --production`
- Docker image builder: `./scripts/build_docker.sh [tag]`
- `scripts/setup_backend.sh` creates/updates `backend/.env` and interactively captures `UVICORN_HOST` and `UVICORN_PORT`.
- `scripts/setup_frontend.sh` creates/updates `frontend/.env` and prompts for `VITE_API_BASE_URL` and `VITE_DEV_PORT`.
- `scripts/setup_ubuntu.sh` performs the same prompts after installing dependencies, so remote deployments follow the same configuration flow.

## Database
- Local MySQL via Homebrew (`brew install mysql`).
- `brew services start mysql` launches the daemon.
- Initial DB/user: `hubclock` / `hubclock`.
- Ensure schema with `curl -X POST http://127.0.0.1:8000/db/init`.

## Default Settings
- Currency: `ILS`
- Theme color: `#1b3aa6`
- Brand name: `העסק שלי`
- PIN must be set via Settings UI or `PUT /settings` before accessing admin screens.
- Settings API: `GET/PUT /settings`, `POST /settings/import`, `GET /settings/export`.

## Frontend Access
- Clock-in page at `/` uses masked input and auto-detects state via `/clock/status`.
- Daily vs summary reports accessible under `/dashboard`; לחצן הייצוא שולח בקשת GET ל-`/reports/daily/export` או `/reports/export` בהתאם לסוג הדוח, עם פרמטר `include_payments` לבחירת הוספת רכיבי שכר.
- נתוני עובדים/משמרות ניתנים לייצוא ב-`GET /employees/export` ולהחזרה ב-`POST /employees/import` (עם דגל `replace_existing`).
- כתובת ה-API בצד הלקוח ניתנת להגדרה דרך המשתנה `VITE_API_BASE_URL` בזמן בנייה או על ידי הצבת `window.__HUBCLOCK_API_BASE__` לפני טעינת האפליקציה. ברירת המחדל מצביעה על `http://127.0.0.1:8000`; ניתן לשנות ל-`/api` אם פרוקסי חיצוני מנתב לבקאנד. `VITE_DEV_PORT` שולט על פורט שרת הפיתוח של Vite.
- בלשונית ההגדרות ניתן להפעיל/להשבית כל אחד משני מסדי הנתונים, לבחור מי הראשי, להריץ בדיקת חיבור (`/db/test` עם `target=primary|secondary`) ולייצר סכימה לפי יעד (`/db/init?target=active|primary|secondary|both`).
- בדוח היומי ניתן לערוך או למחוק משמרות (כולל הזנת PIN לוידוא), מה שמפעיל את מסלולי `PUT /time-entries/{id}` ו-`DELETE /time-entries/{id}`.

## Docker
- `./scripts/build_docker.sh hubclock:latest` — בונה דימוי הכולל את ה-API וה-frontend המהודק.
- `docker run --rm -p 8000:8000 -e MYSQL_HOST=... hubclock:latest` — מפעיל את השירות. ספקו פרטי MySQL דרך משתני סביבה או בקובץ `.env` חיצוני.

## Notes for Codex Agents
- Key files: `backend/app/main.py`, `frontend/src/pages/ClockPage.tsx`, `frontend/src/pages/SettingsPage.tsx`.
- Refer to `docs/CHANGELOG.md` for the latest modifications history.
