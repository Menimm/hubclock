# Codex Context (Updated: 2025-10-29)

This document captures the current state of the HubClock project so future Codex sessions can resume seamlessly. Keep it up-to-date whenever major architectural or configuration decisions change.

## Product Overview & Core Requirements
- Purpose: local kiosk time-clock for a small business (initially a deli with ~5 employees) running on a VM with locally managed MySQL.
- Clock-in/out: employees enter their code (masked) on a Hebrew, mobile-friendly interface with a single toggle button and live-updating list of active shifts.
- Employees module: admin manages full name, employee code, external ID (`id_number`, numeric string with leading zeros), hourly rate, active flag; can add manual shifts; supports JSON import/export of employees and time entries.
- Dashboard: monthly/custom summaries and detailed daily reports per employee with shift editing/deletion (PIN re-auth), Excel exports (daily + summary) with optional wage columns; daily exports include individual shift rows.
- Device tracking: each kiosk saves a persistent device UUID in localStorage; backend stores `clock_in_device_id` / `clock_out_device_id` on `time_entries`. Daily reports and Excel exports show the device IDs, and clocking-out responses flag when the device differs from the one used at check-in.
- Settings: configure business name, currency (default ILS), theme color, admin PIN, DB connection parameters (primary/secondary MySQL), theme + name applied globally; includes DB test/init, settings import/export.
- UX/Security: admin routes PIN-gated; PIN input hidden; verification endpoint works even before DB setup. Reports and active shift lists show employee IDs.

## Deployment & Services
- Backend: FastAPI (`hubclock-backend.service`) runs under systemd; production assets served via Uvicorn.
- Frontend: React/Vite; production build lives in `frontend/dist`. `scripts/setup_frontend.sh` and `scripts/setup_ubuntu.sh` can trigger `npm run build` interactively.
- Reverse proxy: Nginx site (`/etc/nginx/sites-available/hubclock.conf`) listens on a configurable port. Proxy layout:
  - `location /api/` → `http://127.0.0.1:<uvicorn-port>/api/`
  - `location /` → `http://127.0.0.1:<uvicorn-port>/`
- System orchestration: `scripts/setproduction.sh` manages install/start/stop/status for backend/nginx/mysql. Component-specific operations supported (e.g., `sudo ./scripts/setproduction.sh start backend nginx`).

## API & Frontend Contract
- All REST endpoints are namespaced under `/api/...`.
- Axios client strips leading `/` to prevent double slashes and defaults `VITE_API_BASE_URL` to `/api`.
- When running behind a proxy, ensure `VITE_API_BASE_URL` (and `window.__HUBCLOCK_API_BASE__`, if used) points to the `/api` base (e.g., `/api` or `https://host/api`).

## Database & Schema
- Primary + optional secondary MySQL connections supported. Settings UI lets the admin toggle active DBs and choose the primary.
- Schema version: **3**. `settings` table tracks `schema_version`. Run `/api/db/init` whenever backend upgrades the schema.
- Employees now include `id_number` (numeric string, preserves leading zeros). Included in exports/reports/daily dashboards/Excel files.

## Key Scripts
- `scripts/setup_backend.sh` – sets up Python env and `.env`.
- `scripts/setup_frontend.sh` – installs node modules, updates `frontend/.env`, optionally builds production bundle, can start dev server.
- `scripts/setup_ubuntu.sh` – full setup: installs deps, prompts for env vars, offers DB/user creation, optional Nginx + Certbot + production service install, optional frontend build.
- `scripts/install_services.sh` – installs/removes systemd units (dev or prod).
- `scripts/setproduction.sh` – wrapper for install/start/stop/status by component.

## Outstanding Notes / Gotchas
- After changing frontend code, rebuild `frontend/dist` (either via `npm --prefix frontend run build` or `setproduction.sh install backend`).
- If requests hit `/clock/...` instead of `/api/clock/...`, verify the deployed bundle has the correct `VITE_API_BASE_URL` and rebuild if necessary.
- Certbot integration assumes port 80 is temporarily available for HTTP-01 validation.
- Hebrew localisation is pervasive; keep new UI labels/messages in Hebrew to maintain consistency.
- Clock-in/out must remain a masked, single-button flow; employee codes are distinct from `id_number` (government ID), so do not swap their roles.
- New device identifiers are stored per entry; keep `/clock` requests sending the `device_id` so analytics remain accurate.

## Last Session Summary (2025-10-29)
- API prefixed with `/api`.
- Frontend/Excel/dashboards updated to show employee ID numbers.
- Setup scripts now offer optional production builds.
- Confirmed Nginx proxy split and axios interceptor fix.

Future changes: update this file with new schema versions, additional services, or config conventions so the next session can read `docs/CODEX_CONTEXT.md` and continue smoothly.
