# Changelog

## 2025-10-29

### Added
- אפשרות למסד נתונים משני (כולל סימון פעילות, בחירת מסד ראשי, ורפליקציה אוטומטית של שינויי כתיבה לכל המסדים הפעילים).
- הרחבות UI להגדרות: טפסים נפרדים למסד א' וב', בדיקות חיבור לפי יעד, בחירת מסד ראשי ב-radio, והרצת יצירת סכימה עם פרמטר `target`.
- Dockerfile וסקריפט `scripts/build_docker.sh` להרכבת דימוי אחוד; ה-API משרת את ה-frontend המקורמל מתוך `frontend/dist`.
- עריכת ומחיקת משמרות מתוך הדוח היומי (כולל אימות PIN) באמצעות מסלולי `PUT /time-entries/{id}` ו-`DELETE /time-entries/{id}`.
- מעקב אחר גרסת סכימת בסיס הנתונים (`schema_version`) והתרעה ממשקית כאשר יש לעדכן את הסכימה להפעלת יכולות חדשות.

### Changed
- מסלולי `/db/test` ו-`/db/init` תומכים בפרמטר `target` (primary/secondary/both/active) ומחזירים הודעות מפורטות לפי היעד.
- פורמט הייצוא/ייבוא של ההגדרות כולל את דגלי הפעילות, פרטי החיבור המשני, והבחירה במסד הראשי.

## 2025-10-28

### Added
- Hebrew-localized frontend with responsive clock-in UX, single action button, and live shift list.
- FastAPI enhancements: manual entry fixes, daily shift report, dynamic settings with DB connection management and export/import.
- Settings support for business name, theme color, and configurable currency (default ILS).
- Frontend color theming tied to settings; password visibility toggle and improved status banners.
- Employee management allows updating name, code, and hourly rate with inline editing.
- Color picker in Settings controls accent theme; backend stores `theme_color` for consistent styling.
- Documentation: `docs/SETUP_NOTES.md` summarises environment setup for future runs.
- Excel export endpoints (`GET /reports/daily/export` and `/reports/export`) עם אפשרות לכלול חישובי שכר.
- ייבוא/ייצוא נתוני עובדים ומשמרות (`GET /employees/export`, `POST /employees/import`) לתמיכה בשחזור מסד הנתונים.
- סקריפטי ההתקנה שואלים באופן אינטראקטיבי על כתובת/פורט של הבקאנד וכתובת ה-API בפרונטאנד ומעדכנים את קבצי ה-`.env`.

### Fixed
- Clock-in error state now clears after successful entry, preventing persistent "employee not found" alerts.
- Legacy schema migrations adjust `manual` column and add new settings fields automatically.
- Shift duration calculation now uses local timestamps, preventing immediate "02:00" duration after clock-in.

### Notes
- After pulling the latest changes, run `curl -X POST http://127.0.0.1:8000/db/init` once to add new columns.
- Theme color is stored as hex and surfaces across header/badges/buttons via CSS variable.
