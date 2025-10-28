# HubClock Deli

HubClock is a small-footprint time tracking kiosk for a five-employee deli. It includes a FastAPI backend, a React (Vite) frontend, and a MySQL database. Employees clock in/out with a masked ID, while administrators manage staff, pay rates, reports, and settings behind a PIN-protected area.

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
   The script prints instructions for macOS (Homebrew) and Ubuntu (APT). Create a database and user once MySQL is running:
   ```sql
   CREATE DATABASE hubclock CHARACTER SET utf8mb4;
   CREATE USER 'hubclock'@'localhost' IDENTIFIED BY 'hubclock';
   GRANT ALL PRIVILEGES ON hubclock.* TO 'hubclock'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. **Configure environment**
   ```bash
   cp backend/.env.example backend/.env
   # edit credentials when needed
   ```

3. **Bootstrap dependencies (scripted)**
   ```bash
   make backend-setup
   make frontend-setup
   ```
   The helper scripts create the virtualenv, install Python packages, and fetch Node modules.

4. **Start the services**
   ```bash
   make backend-run
   make frontend-run
   ```
   Visit http://localhost:5173.

5. **Bootstrap the schema**
   - Use **Settings → Database Utilities** to run "Test DB Connection" and "Create/Update Schema".
   - Alternatively, call `POST http://127.0.0.1:8000/db/init`.

## Key Features

- **Clock In/Out**: ממשק בעברית מותאם למובייל עם כפתור יחיד שמזהה אוטומטית אם העובד נכנס או יצא, ורשימת משמרות שמתעדכנת בזמן אמת.
- **Employees**: ניהול עובדים מלא כולל עדכון שכר שעתי, מצב פעיל/לא פעיל, הזנת משמרות ידניות וייצוא/ייבוא JSON לגיבוי ושחזור.
- **Dashboard**: דוחות סיכום חודשיים או טווח מותאם לצד יומן יומי המציג לכל עובד את התאריכים ושעות העבודה, כולל חישוב שכר משוער במטבע הנבחר וייצוא לאקסל (בחירה האם לכלול רכיבי שכר).
- **Settings**: בחירת מטבע (ברירת מחדל ‎ILS‎) וצבע נושא, קביעת שם העסק המופיע בכותרות, ניהול פרטי חיבור למסד נתונים, קוד PIN מנהל, בדיקות קשר למסד, וייצוא/ייבוא מלא של ההגדרות—all מהדפדפן.

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

## Deployment (Ubuntu)

```bash
sudo ./scripts/setup_ubuntu.sh
sudo ./scripts/install_services.sh
sudo systemctl start hubclock-backend.service
sudo systemctl start hubclock-frontend.service
```

Services run under the invoking user by default; adjust the systemd unit files in `deploy/` if you prefer a dedicated account. Frontend listens on port 5173, backend on 8000. Remember to configure MySQL credentials in `backend/.env` and run `curl -X POST http://127.0.0.1:8000/db/init` once after provisioning.
