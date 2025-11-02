## Admin PIN Recovery Runbook

Use this procedure when the HubClock admin PIN is lost and you have shell access to the host or maintenance container. The steps below update (or create) an admin account in the database without exposing the PIN hash in version control.

### Prerequisites
- Access to the deployment host (SSH, console, or maintenance container).
- MySQL client (`mysql`) and OpenSSL available in `PATH`.
- Database credentials supplied via environment variables (`MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`) or an `.env` file in the project root.

### Steps
1. **Navigate to the project**
   ```bash
   cd /path/to/hubclock
   ```
2. **Run the recovery tool**
   ```bash
   bash scripts/reset_admin_pin.sh
   ```
   - The script loads defaults (or `.env` overrides), prompts twice for the new PIN, enforces the standard length (4–12 characters), and then lets you choose which admin to update or create.
3. **Optional flags**
   - Set `ENV_FILE=/path/to/custom.env` before running if the configuration file is not at the project root.
   - Override connection details inline, for example:
     ```bash
     MYSQL_HOST=db.internal MYSQL_PASSWORD=secret bash scripts/reset_admin_pin.sh
     ```
4. **Verify**
   - Call `POST /api/auth/verify-pin` (or use the frontend) with the new PIN to confirm it was updated.
   - Log the recovery event in your operational records.

### Notes
- The script manages entries in the `admin_accounts` table (creating a new admin when needed) and keeps accounts active after a reset.
- If the database connection fails, ensure the expected credentials are present (either exported or in the `.env` file) before retrying.
- Rotate any temporary automation secrets used during recovery and remove them from shell history.
