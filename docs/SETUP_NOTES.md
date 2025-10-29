# Setup Notes (HubClock)

## Services
- Backend (dev): `./scripts/start_backend.sh` (reload, honours `backend/.env`)
- Backend (service/production): `./scripts/run_backend_service.sh [--production]`
- Frontend dev server: `./scripts/start_frontend.sh`
- Combined stack manager: `./scripts/manage_dev_services.sh start|stop|restart|status` (uses systemd when units exist; otherwise spawns background processes and logs under `.run/`)
- Manual MySQL helper for root-only hosts: `sudo ./scripts/manage_mysql_root.sh start|stop|status`
- Provisioning script: `sudo ./scripts/setup_ubuntu.sh`
- `scripts/setup_backend.sh` / `scripts/setup_frontend.sh` can optionally launch their respective dev servers (backgrounded with logs in `.run/`) once configuration completes.
- `scripts/setup_ubuntu.sh` can start both services and immediately probe `/auth/verify-pin` via `curl` to confirm connectivity.
- Production/dev units can be removed with `sudo ./scripts/install_services.sh --remove-production` or `--remove-development`.
- Install systemd units:
  - Development (backend + Vite dev server): `sudo ./scripts/install_services.sh --dev`
  - Production (backend serving built frontend): `sudo ./scripts/install_services.sh --production`
- Docker image builder: `./scripts/build_docker.sh [tag]`
- `scripts/setup_backend.sh` creates/updates `backend/.env` and prompts for `UVICORN_HOST` / `UVICORN_PORT`.
- `scripts/setup_frontend.sh` creates/updates `frontend/.env` and prompts for `VITE_API_BASE_URL`, `VITE_DEV_HOST`, and `VITE_DEV_PORT`.
- `scripts/setup_ubuntu.sh` runs the same prompts after dependency installation so remote deployments match the local flow.

## Database
- Local MySQL via Homebrew (`brew install mysql`).
- `brew services start mysql` launches the daemon.
- Initial DB/user: `hubclock` / `hubclock`.
- Ensure schema with `curl -X POST http://127.0.0.1:8000/db/init`.
- Containers without full systemd permissions can launch MySQL directly as root with `sudo ./scripts/manage_mysql_root.sh start` (logs in `/var/log/mysqld-root.log`).
- Setup helpers detect the server's IPv4 addresses and suggest them as defaults for `UVICORN_HOST`, `VITE_DEV_HOST`, and `VITE_API_BASE_URL` to simplify remote access.
- Choose the Nginx option in `scripts/setup_ubuntu.sh` to install a reverse proxy (you can set the public port during the prompt); the script creates `/etc/nginx/sites-available/hubclock.conf` and can switch to the production backend service so the entire app is reachable via `http://<host>:<port>/`. If DNS is already in place, opt into the Certbot step to request Let's Encrypt certificates and serve HTTPS immediately.

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
- כתובת ה-API בצד הלקוח ניתנת להגדרה דרך המשתנה `VITE_API_BASE_URL` בזמן בנייה או על ידי הצבת `window.__HUBCLOCK_API_BASE__` לפני טעינת האפליקציה. ברירת המחדל מצביעה על `http://127.0.0.1:8000`; ניתן לשנות ל-`/api` אם פרוקסי חיצוני מנתב לבקאנד. `VITE_DEV_HOST` / `VITE_DEV_PORT` שולטים על כתובת שרת הפיתוח של Vite.
- בלשונית ההגדרות ניתן להפעיל/להשבית כל אחד משני מסדי הנתונים, לבחור מי הראשי, להריץ בדיקת חיבור (`/db/test` עם `target=primary|secondary`) ולייצר סכימה לפי יעד (`/db/init?target=active|primary|secondary|both`).
- בדוח היומי ניתן לערוך או למחוק משמרות (כולל הזנת PIN לוידוא), מה שמפעיל את מסלולי `PUT /time-entries/{id}` ו-`DELETE /time-entries/{id}`.
- במצב פיתוח ניתן להשיק את הממשק ללא מסד נתונים מקומי; הגדירו חיבור למסד נתונים בתיבת ההגדרות ורק לאחר מכן הפעילו עדכון סכימה.
- שינוי ה-host/פורט של שרת הפיתוח נעשה דרך `VITE_DEV_HOST` / `VITE_DEV_PORT` ב-`frontend/.env`. לאחר שינוי, הריצו שוב `sudo ./scripts/install_services.sh --dev` או הקפידו להריץ `npm run dev` מתוך תיקיית `frontend/` עם הפרמטרים `--host` / `--port` המתאימים.

## Docker
- `./scripts/build_docker.sh hubclock:latest` — בונה דימוי הכולל את ה-API וה-frontend המהודק.
- `docker run --rm -p 8000:8000 -e MYSQL_HOST=... hubclock:latest` — מפעיל את השירות. ספקו פרטי MySQL דרך משתני סביבה או בקובץ `.env` חיצוני.

## Notes for Codex Agents
- Key files: `backend/app/main.py`, `frontend/src/pages/ClockPage.tsx`, `frontend/src/pages/SettingsPage.tsx`.
- Refer to `docs/CHANGELOG.md` for the latest modifications history.
