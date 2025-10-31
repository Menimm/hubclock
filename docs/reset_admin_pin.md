## Admin PIN Recovery Runbook

Use this procedure when the HubClock admin PIN is lost and you have shell access to the host or maintenance container. The steps below update the PIN directly in the database without exposing the PIN hash in version control.

### Prerequisites
- Access to the deployment host (SSH, console, or maintenance container).
- Environment variables or `.env` file configured with the production database credentials so the backend modules can connect.
- Python 3.11 with the project virtual environment and dependencies installed.

### Steps
1. **Activate the environment**
   ```bash
   cd /path/to/hubclock
   source .venv/bin/activate
   ```
2. **Run the recovery tool**
   ```bash
   python scripts/reset_admin_pin.py
   ```
   - You will be prompted twice for the new PIN (characters are hidden).
   - The script enforces the standard PIN length (4–12 characters).
3. **Optional flags**
   - `--pin <value>`: supply the new PIN non-interactively (use only in secured automation).
   - `--echo`: show typed characters during prompts (handy for temporary automation; avoid on shared terminals).
   - `--no-confirm`: skip the confirmation prompt when `--pin` is provided.
4. **Verify**
   - Call `POST /api/auth/verify-pin` (or use the frontend) with the new PIN to confirm it was updated.
   - Log the recovery event in your operational records.

### Notes
- The script updates the single `settings` row and commits the change in one transaction.
- If the database connection fails, ensure the expected credentials are present in the environment before retrying.
- Rotate any temporary automation secrets used during recovery and remove them from shell history.
