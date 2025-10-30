# HubClock

HubClock is a small-footprint time tracking kiosk for neighborhood shops, delis, and other small teams. It includes a FastAPI backend, a React (Vite) frontend, and a MySQL database. Employees clock in/out with a masked ID, while administrators manage staff, pay rates, reports, and settings behind a PIN-protected area.

## Stack Overview

- **Backend**: FastAPI, SQLAlchemy, MySQL
- **Frontend**: React 18 + Vite + TypeScript
- **Auth**: Simple PIN gate for admin-only sections
- **Data**: Employees, time entries, global settings (currency + PIN)

## Getting Started

1. **Install MySQL (local VM)**
   ```bash
   ./scripts/install_mysql.sh
   ```
   On Ubuntu/Debian VMs you can run the full bootstrap instead:
   ```bash
   sudo ./scripts/setup_ubuntu.sh
   ```
   The wizard installs Python/Node, prompts for backend/frontend hosts and ports, and (optionally) provisions MySQL or MariaDB. Create a database and user once MySQL is running:
   ```sql
   CREATE DATABASE hubclock CHARACTER SET utf8mb4;
   CREATE USER 'hubclock'@'localhost' IDENTIFIED BY 'hubclock';
   GRANT ALL PRIVILEGES ON hubclock.* TO 'hubclock'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. **Configure environment**
   The setup scripts copy the `.env` templates (if missing) and prompt for backend host/port and the frontend API base URL/port. To pre-populate or adjust manually:
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   # edit credentials when needed
   ```

3. **Bootstrap dependencies (scripted prompts included)**
   ```bash
   make backend-setup
   make frontend-setup
   ```
   The helper scripts create the virtualenv, install Python packages, fetch Node modules, and offer to build the production bundle and launch the dev servers immediately if you opt in at the end of each run.

4. **Start the services**
   ```bash
   make backend-run
   make frontend-run
   ```
   or launch both with:
   ```bash
   ./scripts/manage_dev_services.sh start
   ```
   Visit http://localhost:5173 (host/port follow your `.env` choices).

5. **Bootstrap the schema**
   - Use **Settings → Database Utilities** to run "Test DB Connection" and "Create/Update Schema".
   - Alternatively, call `POST http://127.0.0.1:8000/api/db/init`.

## Key Features

- **Clock In/Out**: ממשק בעברית מותאם למובייל עם כפתור יחיד שמזהה אוטומטית אם העובד נכנס או יצא, ורשימת משמרות שמתעדכנת בזמן אמת. כל פעולה מצרפת מזהה מכשיר ייחודי כדי לעקוב אחר העמדה שממנה בוצעה הכניסה או היציאה.
- **Employees**: ניהול עובדים מלא כולל עדכון שכר שעתי, מספר עובד לזיהוי במערכת, מספר מזהה חיצוני (עם תמיכה ב-0 מוביל), מצב פעיל/לא פעיל, הזנת משמרות ידניות וייצוא/ייבוא JSON לגיבוי ושחזור.
- **Dashboard**: דוחות סיכום חודשיים או טווח מותאם לצד יומן יומי המציג לכל עובד את התאריכים ושעות העבודה, כולל חישוב שכר משוער במטבע הנבחר וייצוא לאקסל (בחירה האם לכלול רכיבי שכר).
- **Redundant Storage**: כתובות חיבור לשני מסדי נתונים MySQL (ראשי ומשני) עם סימון פעילות, בחירת המסד הראשי לקריאה, וסנכרון אוטומטי של כל הנתונים לכל מסד פעיל.
- **Settings & Adjustments**: בחירת מטבע (ברירת מחדל ‎ILS‎) וצבע נושא, קביעת שם העסק המופיע בכותרות, הגדרת מסדי הנתונים הפעילים (כולל בדיקת חיבור/יצירת סכימה לכל יעד), קוד PIN מנהל, עריכת רשומות משמרת מתוך הדוחות היומיים, וייצוא/ייבוא מלא של ההגדרות—all מהדפדפן.

## File Layout

```
backend/
  app/
    config.py        # MySQL configuration via env vars
    database.py      # Engine + session utilities
    main.py          # FastAPI routes
    models.py        # SQLAlchemy models
    schemas.py       # Pydantic request/response models
    security.py      # PIN hashing helpers
  requirements.txt
  .env.example
frontend/
  src/
    api/             # Axios client
    components/      # Shared UI building blocks
    context/         # Auth + settings providers
    pages/           # Clock, Dashboard, Employees, Settings
  package.json
  vite.config.ts
scripts/
  install_mysql.sh   # Helper instructions for MySQL installation
```

## Tips

- PIN protects all routes except the public clock page. Set it in **Settings** before first use.
- Use MySQL’s timezone-aware configuration (`DEFAULT_TIME_ZONE='+00:00'`) to avoid DST surprises.
- Run reports regularly and export data by copying table results if payroll needs archival outside the app.
- The frontend reads `VITE_API_BASE_URL` (or `window.__HUBCLOCK_API_BASE__` at runtime) to know where the backend lives. By default it points to `/api`; set it to a full URL if you proxy requests through a web server.
- Backend REST endpoints are exposed under `/api/...` so the app and API can share a reverse proxy/port without path collisions.
- `VITE_DEV_HOST` / `VITE_DEV_PORT` in `frontend/.env` control the Vite dev server binding used by `scripts/start_frontend.sh`. If you change them, reinstall the dev services (`sudo ./scripts/install_services.sh --dev`) or pass the host/port manually when running `npm run dev` from `frontend/`.
- When running the Vite dev server manually, invoke it from the `frontend/` folder (e.g. `npm run dev -- --host 0.0.0.0 --port 5173`) or use `npm --prefix frontend run dev …` from the repo root.
- Use **Settings → מסדי נתונים** לבדיקת חיבור לכל יעד (`בדיקת חיבור ראשי/משני`) ולהגדרת היעד עבור יצירת סכימה (`מסדי נתונים פעילים`, `ראשי`, `משני`, או `שני המסדים`).
- אם מתקבלת התרעה על גרסת סכימה מיושנת, הריצו את "יצירת/עדכון סכימה" (בטאב ההגדרות) כך שהסכמה תעודכן ויכולות חדשות כמו עריכת משמרות יפעלו.
- במצב פיתוח, השירותים יעלו גם ללא מסד נתונים מקומי — הגדירו חיבור למסד מרוחק דרך מסך ההגדרות ולאחר מכן הפעילו בדיקת חיבור/עדכון סכימה.

## Deployment (Ubuntu)

```bash
sudo ./scripts/setup_ubuntu.sh
sudo ./scripts/install_services.sh --dev
./scripts/manage_dev_services.sh start   # uses systemd when available, otherwise background jobs
```

To remove systemd units later, use:

```bash
sudo ./scripts/install_services.sh --remove-development
sudo ./scripts/install_services.sh --remove-production
```

Services run under the invoking user by default; adjust the systemd unit files in `deploy/` if you prefer a dedicated account. When systemd isn’t available (e.g., minimal containers), the management script falls back to background processes spawned from `scripts/start_backend.sh` / `scripts/start_frontend.sh`. Frontend listens on the `VITE_DEV_HOST:VITE_DEV_PORT` values (defaults 127.0.0.1:5173) and the backend on `UVICORN_HOST:UVICORN_PORT` (defaults 0.0.0.0:8000). Remember to configure MySQL credentials in `backend/.env` and run `curl -X POST http://127.0.0.1:8000/api/db/init` once after provisioning.

To install the development services (backend w/ auto-reload + Vite dev server), run:

```bash
sudo ./scripts/install_services.sh --dev
```

For a production install that serves the compiled frontend from the backend, run:

```bash
sudo ./scripts/install_services.sh --production
```

The production option builds `frontend/dist`, installs `hubclock-backend.service` with multiple uvicorn workers, and disables the Vite dev service.

For quick management of the dev services, use:

```bash
./scripts/manage_dev_services.sh start|stop|restart|status
```

For production control (install/start/stop/status), use:

```bash
sudo ./scripts/setproduction.sh help
```

If systemd refuses to start MySQL/MariaDB (common in root-only containers), launch it directly as root:

```bash
sudo ./scripts/manage_mysql_root.sh start
```

Logs live in `/var/log/mysqld-root.log`; stop/status are available via the same helper.

### Serve Everything on Port 80

Run the Ubuntu setup script with the Nginx option (`Install and configure Nginx reverse proxy on port 80? -> y`). The helper installs Nginx, lets you set the public HTTP port, writes `/etc/nginx/sites-available/hubclock.conf`, and creates a split proxy: `location /api/` forwards API calls to FastAPI, while `location /` proxies everything else (the built frontend). You can optionally switch to the production backend service (which serves the built frontend from `frontend/dist`). After choosing the production option you only need the selected port exposed—Nginx forwards API and static requests to the backend on port 8000.

If your DNS already points to the VM, answer `y` to the "Request Let's Encrypt SSL certificates" prompt to have Certbot obtain and configure HTTPS automatically. The script temporarily binds port 80 for the ACME challenge, then asks which HTTPS port you’d like (default 443) and rewrites the config accordingly. Certificates live under `/etc/letsencrypt/live/<hostname>/`, and Nginx is reloaded with the SSL-ready config.

### Production Update Procedure

1. Pull the latest code: `git pull`.
2. Rebuild frontend assets and reinstall the production service:
   ```bash
   npm --prefix frontend install
   npm --prefix frontend run build
   sudo ./scripts/install_services.sh --production
   ```
3. Apply database migrations via the UI (**Settings → יצירת/עדכון סכימה**) or:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/db/init
   ```
4. Restart the backend service: `sudo systemctl restart hubclock-backend.service`.

### Quick PIN Check

Both `scripts/setup_ubuntu.sh` and the individual setup scripts can now run a quick `curl` against `/auth/verify-pin`. Provide the PIN you expect to use and the helper will confirm connectivity (or surface the API error) right after the services start.

## Docker

Build an all-in-one image (FastAPI backend + compiled frontend) with:

```bash
./scripts/build_docker.sh hubclock:latest
```

Run the container while pointing it to an accessible MySQL instance:

```bash
docker run --rm -p 8000:8000 \
  -e MYSQL_HOST=your-mysql-host \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=hubclock \
  -e MYSQL_PASSWORD=hubclock \
  -e MYSQL_DATABASE=hubclock \
  hubclock:latest
```

The backend serves the compiled frontend from `/`, so visiting `http://localhost:8000` loads the UI directly.
