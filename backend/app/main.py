from __future__ import annotations

import json
import logging
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Optional

from collections import defaultdict
from io import BytesIO
from urllib.parse import quote_plus

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import Workbook
from sqlalchemy import create_engine, delete, func, inspect, insert, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from . import schemas
from .config import get_settings
from .database import configure_engines, get_db, get_engine, get_secondary_engine, session_scope
from .models import AdminAccount, AdminAuditLog, Base, Employee, Setting, TimeEntry
from .security import hash_pin, verify_pin

settings = get_settings()
app = FastAPI(title="HubClock API", version="0.1.0")
api_router = APIRouter()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
SCHEMA_VERSION = 5
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
logger = logging.getLogger(__name__)

DATABASE_TARGETS = {"primary", "secondary"}


def connection_active(setting: Optional[Setting], target: str) -> bool:
    target = (target or "primary").lower()
    if target not in DATABASE_TARGETS:
        return False
    if target == "primary":
        if not setting or setting.primary_db_active is None:
            return True
        return bool(setting.primary_db_active)
    if not setting or setting.secondary_db_active is None:
        return False
    return bool(setting.secondary_db_active)


def connection_defined(setting: Optional[Setting], target: str) -> bool:
    target = (target or "primary").lower()
    if target not in DATABASE_TARGETS:
        return False
    if target == "primary":
        host_source = setting.db_host if setting and setting.db_host else settings.mysql_host
        user_source = setting.db_user if setting and setting.db_user else settings.mysql_user
        host = (host_source or "").strip()
        user = (user_source or "").strip()
        return bool(host and user)
    if not setting:
        return False
    host = (setting.secondary_db_host or "").strip()
    user = (setting.secondary_db_user or "").strip()
    return bool(host and user)


def connection_configured(setting: Optional[Setting], target: str) -> bool:
    return connection_defined(setting, target) and connection_active(setting, target)


def build_connection_url(
    setting: Optional[Setting],
    overrides: Optional[schemas.DBTestRequest] = None,
    target: str = "primary",
    *,
    allow_missing: bool = False,
    require_active: bool = True,
) -> Optional[str]:
    target = (target or "primary").lower()
    if target not in DATABASE_TARGETS:
        raise ValueError(f"Unsupported database target '{target}'")

    def setting_value(attr: str) -> Optional[str]:
        if not setting:
            return None
        if target == "primary":
            return getattr(setting, attr)
        return getattr(setting, f"secondary_{attr}")

    if require_active and not connection_active(setting, target):
        if allow_missing:
            return None
        raise ValueError(f"מסד הנתונים {target} אינו פעיל")

    host_candidate = overrides.db_host if overrides and overrides.db_host is not None else None
    user_candidate = overrides.db_user if overrides and overrides.db_user is not None else None
    port_candidate = overrides.db_port if overrides and overrides.db_port is not None else None
    password_override = overrides.db_password if overrides and overrides.db_password is not None else None

    if target == "primary":
        host = host_candidate or (setting.db_host if setting and setting.db_host else settings.mysql_host)
        port = port_candidate or (setting.db_port if setting and setting.db_port else settings.mysql_port)
        user = user_candidate or (setting.db_user if setting and setting.db_user else settings.mysql_user)
        if password_override is not None:
            password_raw = password_override
        else:
            if setting and setting.db_password is not None:
                password_raw = setting.db_password
            else:
                password_raw = settings.mysql_password
    else:
        host = host_candidate or (setting.secondary_db_host if setting and setting.secondary_db_host else None)
        port = port_candidate or (setting.secondary_db_port if setting and setting.secondary_db_port else settings.mysql_port)
        user = user_candidate or (setting.secondary_db_user if setting and setting.secondary_db_user else settings.mysql_user)
        if password_override is not None:
            password_raw = password_override
        else:
            if setting and setting.secondary_db_password is not None:
                password_raw = setting.secondary_db_password
            elif setting and setting.db_password is not None:
                password_raw = setting.db_password
            else:
                password_raw = settings.mysql_password

    host = (host or "").strip()
    user = (user or "").strip()
    if not host or not user:
        if allow_missing:
            return None
        raise ValueError(f"Missing host or user for {target} database configuration")

    password = quote_plus((password_raw or ""))
    database = settings.mysql_database
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
def determine_primary_label(setting: Optional[Setting]) -> str:
    if setting and setting.primary_database in DATABASE_TARGETS:
        candidate = setting.primary_database
        if connection_configured(setting, candidate):
            return candidate

    for candidate in ("primary", "secondary"):
        if connection_configured(setting, candidate):
            return candidate

    raise ValueError("לא הוגדר בסיס נתונים פעיל לשימוש כראשי")


def resolve_connection_urls(setting: Optional[Setting]) -> tuple[str, Optional[str]]:
    primary_label = determine_primary_label(setting)
    primary_url = build_connection_url(setting, target=primary_label, require_active=True)
    other_label = "secondary" if primary_label == "primary" else "primary"
    secondary_url: Optional[str] = None
    if connection_configured(setting, other_label):
        secondary_url = build_connection_url(setting, target=other_label, allow_missing=True, require_active=True)
    return primary_url, secondary_url


def configure_from_setting(setting: Optional[Setting]) -> None:
    primary_url, secondary_url = resolve_connection_urls(setting)
    configure_engines(primary_url, secondary_url)


def _get_singleton_setting(session: Session) -> Setting:
    setting = session.scalar(select(Setting))
    if not setting:
        raise HTTPException(status_code=400, detail="לא נמצאו נתוני הגדרות")
    return setting


def _validate_admin_pin(
    session: Session,
    admin_id: int,
    pin: str,
    *,
    bypass_lock: bool = False,
) -> tuple[Setting, AdminAccount]:
    admin = session.get(AdminAccount, admin_id)
    if not admin or not admin.active:
        raise HTTPException(status_code=403, detail="פרטי הניהול שגויים")
    if not verify_pin(pin, admin.pin_hash):
        raise HTTPException(status_code=403, detail="קוד ה-PIN שגוי")
    setting = _get_singleton_setting(session)
    if setting.write_lock_active and not bypass_lock:
        raise HTTPException(status_code=423, detail="שינויים חסומים בזמן סנכרון או תחזוקה")
    return setting, admin


def _ensure_writes_allowed(session: Session) -> Setting:
    setting = _get_singleton_setting(session)
    if setting.write_lock_active:
        raise HTTPException(status_code=423, detail="שינויים חסומים בזמן סנכרון או תחזוקה")
    return setting


def _record_admin_audit(session: Session, admin: AdminAccount, action: str, details: Optional[dict] = None) -> None:
    payload = json.dumps(details, ensure_ascii=False) if details else None
    entry = AdminAuditLog(admin_id=admin.id, action=action, details=payload)
    session.add(entry)


def _sync_setting_pin_hash(session: Session) -> None:
    setting = session.scalar(select(Setting))
    if not setting:
        return
    primary_admin = session.scalar(
        select(AdminAccount)
        .where(AdminAccount.active.is_(True))
        .order_by(AdminAccount.created_at.asc())
    )
    if not primary_admin:
        primary_admin = session.scalar(select(AdminAccount).order_by(AdminAccount.created_at.asc()))
    setting.pin_hash = primary_admin.pin_hash if primary_admin else None


def _serialize_audit_entry(entry: AdminAuditLog) -> schemas.AdminAuditLogEntry:
    try:
        details = json.loads(entry.details) if entry.details else None
    except json.JSONDecodeError:
        details = {"raw": entry.details}
    return schemas.AdminAuditLogEntry(
        id=entry.id,
        admin_id=entry.admin_id,
        action=entry.action,
        details=details,
        created_at=entry.created_at,
    )


def _get_engine_for_label(label: str):  # type: ignore[return-type]
    normalized = label.lower()
    if normalized == "primary":
        return get_engine()
    if normalized == "secondary":
        engine = get_secondary_engine()
        if engine is None:
            raise HTTPException(status_code=400, detail="מסד הנתונים המשני אינו מוגדר")
        return engine
    raise HTTPException(status_code=400, detail=f"יעד מסד נתונים לא נתמך: {label}")


def _replicate_incremental(table, source_session: Session, target_session: Session) -> int:
    pk_column = table.__table__.c.id
    max_target = target_session.execute(select(func.max(pk_column))).scalar()
    max_value = max_target if max_target is not None else 0
    rows = (
        source_session.execute(select(table).where(pk_column > max_value).order_by(pk_column)).scalars()
    )
    inserted = 0
    insert_stmt = table.__table__.insert()
    for row in rows:
        data = {column.name: getattr(row, column.name) for column in table.__table__.columns}
        target_session.execute(insert_stmt.values(**data))
        inserted += 1
    return inserted


def _ensure_setting_present(source_session: Session, target_session: Session) -> int:
    existing = target_session.scalar(select(func.count(Setting.id))) or 0
    if existing:
        return 0
    setting = source_session.scalar(select(Setting))
    if not setting:
        return 0
    data = {column.name: getattr(setting, column.name) for column in Setting.__table__.columns}
    target_session.execute(Setting.__table__.insert().values(**data))
    return 1


def _perform_database_sync(source_label: str, target_label: str) -> dict[str, int]:
    normalized_source = source_label.lower()
    normalized_target = target_label.lower()
    if normalized_source == normalized_target:
        raise HTTPException(status_code=400, detail="מקור ויעד הסנכרון חייבים להיות שונים")

    try:
        source_engine = _get_engine_for_label(normalized_source)
        target_engine = _get_engine_for_label(normalized_target)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    SourceSession = sessionmaker(bind=source_engine, autoflush=False, expire_on_commit=False)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, expire_on_commit=False)

    copied: dict[str, int] = {}

    with SourceSession() as source_session, TargetSession() as target_session:
        try:
            copied["settings"] = _ensure_setting_present(source_session, target_session)
            copied["employees"] = _replicate_incremental(Employee, source_session, target_session)
            copied["time_entries"] = _replicate_incremental(TimeEntry, source_session, target_session)
            copied["admin_accounts"] = _replicate_incremental(AdminAccount, source_session, target_session)
            copied["admin_audit_logs"] = _replicate_incremental(AdminAuditLog, source_session, target_session)
            target_session.commit()
        except HTTPException:
            target_session.rollback()
            raise
        except Exception as exc:  # pragma: no cover - defensive
            target_session.rollback()
            raise HTTPException(status_code=500, detail=f"כשל בסנכרון הנתונים: {exc}") from exc

    return copied


def ensure_legacy_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    with engine.begin() as conn:
        if "time_entries" in table_names:
            columns = {col["name"] for col in inspector.get_columns("time_entries")}
            if "manual" in columns and "is_manual" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE time_entries "
                        "CHANGE manual is_manual BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "clock_in_device_id" not in columns:
                conn.execute(text("ALTER TABLE time_entries ADD COLUMN clock_in_device_id VARCHAR(64)"))
            if "clock_out_device_id" not in columns:
                conn.execute(text("ALTER TABLE time_entries ADD COLUMN clock_out_device_id VARCHAR(64)"))
        if "settings" in table_names:
            columns = {col["name"] for col in inspector.get_columns("settings")}
            alterations = {
                "db_host": "ALTER TABLE settings ADD COLUMN db_host VARCHAR(128)",
                "db_port": "ALTER TABLE settings ADD COLUMN db_port INT",
                "db_user": "ALTER TABLE settings ADD COLUMN db_user VARCHAR(64)",
                "db_password": "ALTER TABLE settings ADD COLUMN db_password VARCHAR(128)",
                "brand_name": "ALTER TABLE settings ADD COLUMN brand_name VARCHAR(120)",
                "theme_color": "ALTER TABLE settings ADD COLUMN theme_color VARCHAR(16)",
                "secondary_db_host": "ALTER TABLE settings ADD COLUMN secondary_db_host VARCHAR(128)",
                "secondary_db_port": "ALTER TABLE settings ADD COLUMN secondary_db_port INT",
                "secondary_db_user": "ALTER TABLE settings ADD COLUMN secondary_db_user VARCHAR(64)",
                "secondary_db_password": "ALTER TABLE settings ADD COLUMN secondary_db_password VARCHAR(128)",
                "primary_database": "ALTER TABLE settings ADD COLUMN primary_database VARCHAR(16)",
                "primary_db_active": "ALTER TABLE settings ADD COLUMN primary_db_active BOOLEAN NOT NULL DEFAULT 1",
                "secondary_db_active": "ALTER TABLE settings ADD COLUMN secondary_db_active BOOLEAN NOT NULL DEFAULT 0",
                "show_clock_device_ids": "ALTER TABLE settings ADD COLUMN show_clock_device_ids BOOLEAN NOT NULL DEFAULT 1",
                "write_lock_active": "ALTER TABLE settings ADD COLUMN write_lock_active BOOLEAN NOT NULL DEFAULT 0",
                "schema_version": "ALTER TABLE settings ADD COLUMN schema_version INT NOT NULL DEFAULT 1",
            }
            for column, ddl in alterations.items():
                if column not in columns:
                    conn.execute(text(ddl))
        if "employees" in table_names:
            employee_columns = {col["name"] for col in inspector.get_columns("employees")}
            if "id_number" not in employee_columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN id_number VARCHAR(32)"))
                conn.execute(text("ALTER TABLE employees ADD UNIQUE KEY uq_employees_id_number (id_number)"))
        created_admin_accounts = False
        if "admin_accounts" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE admin_accounts (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(120) NOT NULL UNIQUE,
                        pin_hash VARCHAR(255) NOT NULL,
                        active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            created_admin_accounts = True
        if "admin_audit_logs" not in table_names:
            conn.execute(
                text(
                    """
                    CREATE TABLE admin_audit_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        admin_id INT NOT NULL,
                        action VARCHAR(120) NOT NULL,
                        details TEXT NULL,
                        created_at DATETIME NOT NULL,
                        CONSTRAINT fk_admin_audit_admin
                            FOREIGN KEY (admin_id) REFERENCES admin_accounts(id)
                            ON DELETE CASCADE
                    )
                    """
                )
            )
        if created_admin_accounts or "admin_accounts" in table_names:
            admin_count = conn.execute(text("SELECT COUNT(*) FROM admin_accounts")).scalar() or 0
            if admin_count == 0 and "settings" in table_names:
                row = conn.execute(
                    text("SELECT pin_hash FROM settings WHERE pin_hash IS NOT NULL AND pin_hash <> '' ORDER BY id LIMIT 1")
                ).first()
                if row and row[0]:
                    timestamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        text(
                            """
                            INSERT INTO admin_accounts (name, pin_hash, active, created_at, updated_at)
                            VALUES (:name, :pin_hash, 1, :created_at, :updated_at)
                            """
                        ),
                        {
                            "name": "Primary Admin",
                            "pin_hash": row[0],
                            "created_at": timestamp,
                            "updated_at": timestamp,
                        },
                    )


def populate_setting_defaults(setting: Setting) -> None:
    if not setting.currency:
        setting.currency = "ILS"
    if not setting.db_host:
        setting.db_host = settings.mysql_host
    if not setting.db_port:
        setting.db_port = settings.mysql_port
    if not setting.db_user:
        setting.db_user = settings.mysql_user
    if setting.db_password is None:
        setting.db_password = settings.mysql_password
    if not setting.brand_name:
        setting.brand_name = "העסק שלי"
    if not setting.theme_color:
        setting.theme_color = "#1b3aa6"
    if not setting.primary_database or setting.primary_database not in DATABASE_TARGETS:
        setting.primary_database = "primary"
    if setting.primary_db_active is None:
        setting.primary_db_active = True
    if setting.secondary_db_active is None:
        setting.secondary_db_active = False
    if setting.show_clock_device_ids is None:
        setting.show_clock_device_ids = True
    if setting.write_lock_active is None:
        setting.write_lock_active = False
    if setting.schema_version is None:
        setting.schema_version = SCHEMA_VERSION


def get_active_employee_by_code(db: Session, employee_code: str) -> Employee:
    employee = db.scalar(select(Employee).where(Employee.employee_code == employee_code))
    if not employee or not employee.active:
        raise HTTPException(status_code=404, detail="העובד לא נמצא או אינו פעיל")
    return employee


def resolve_date_range(
    month: Optional[str], start: Optional[dt.date], end: Optional[dt.date]
) -> tuple[dt.date, dt.date]:
    if month and (start or end):
        raise HTTPException(status_code=400, detail="בחרו חודש או טווח מותאם אישית, לא את שניהם")
    if month:
        try:
            range_start = dt.date.fromisoformat(f"{month}-01")
        except ValueError:
            raise HTTPException(status_code=400, detail="פורמט החודש אינו תקין. יש להשתמש ב-YYYY-MM")
        next_month = (range_start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        range_end = next_month - dt.timedelta(days=1)
    else:
        if not start or not end:
            today = dt.date.today()
            range_start = today.replace(day=1)
            range_end = today
        else:
            range_start = start
            range_end = end
    if range_end < range_start:
        raise HTTPException(status_code=400, detail="תאריך הסיום חייב להיות מאוחר מתאריך ההתחלה")
    return range_start, range_end


@app.on_event("startup")
def ensure_engine():
    try:
        get_engine()
    except (RuntimeError, OperationalError) as exc:
        logger.warning("Database engine unavailable on startup: %s", exc)


def _load_setting() -> Optional[Setting]:
    try:
        with session_scope() as session:
            return session.scalar(select(Setting))
    except (OperationalError, RuntimeError, ProgrammingError):
        return None


def _normalize_overrides(payload: Optional[schemas.DBTestRequest]) -> Optional[schemas.DBTestRequest]:
    if not payload:
        return None
    filtered = payload.model_dump(exclude_none=True)
    if not filtered:
        return None
    return schemas.DBTestRequest(**filtered)


def _override_from_update(payload: schemas.SettingsUpdate) -> Optional[schemas.DBTestRequest]:
    if all(
        value is None
        for value in (
            payload.db_host,
            payload.db_port,
            payload.db_user,
            payload.db_password,
        )
    ):
        return None
    return schemas.DBTestRequest(
        db_host=payload.db_host,
        db_port=payload.db_port,
        db_user=payload.db_user,
        db_password=payload.db_password,
        target="primary",
    )


def _override_from_import(payload: schemas.SettingsImport) -> Optional[schemas.DBTestRequest]:
    if all(
        value is None
        for value in (
            payload.db_host,
            payload.db_port,
            payload.db_user,
            payload.db_password,
        )
    ):
        return None
    return schemas.DBTestRequest(
        db_host=payload.db_host,
        db_port=payload.db_port,
        db_user=payload.db_user,
        db_password=payload.db_password,
        target="primary",
    )


def _ensure_primary_connection(override: Optional[schemas.DBTestRequest]) -> None:
    try:
        ensure_legacy_schema(get_engine())
        return
    except (RuntimeError, OperationalError):
        if not override:
            raise HTTPException(
                status_code=400,
                detail="לא הוגדר חיבור למסד הנתונים. הזינו פרטי חיבור ושמרו שוב.",
            )
        try:
            url = build_connection_url(None, override, target=override.target, require_active=False)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        configure_engines(url)
        try:
            ensure_legacy_schema(get_engine())
        except OperationalError as exc:
            detail = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
            raise HTTPException(status_code=400, detail=detail)


def _check_schema(engine) -> list[str]:
    inspector = inspect(engine)
    missing_tables = []
    required_tables = {"employees", "time_entries", "settings"}
    existing = set(inspector.get_table_names())
    for table in sorted(required_tables - existing):
        missing_tables.append(table)
    return missing_tables


def _run_connection_test(overrides: Optional[schemas.DBTestRequest]) -> schemas.DBTestResponse:
    setting = _load_setting()
    target = overrides.target if overrides else "primary"
    try:
        url = build_connection_url(setting, overrides, target=target, require_active=False)
    except ValueError as exc:
        return schemas.DBTestResponse(ok=False, message=str(exc))
    temp_engine = create_engine(url, pool_pre_ping=True)
    schema_missing: list[str] = []
    schema_version: Optional[int] = None
    schema_ok: Optional[bool] = None
    try:
        with temp_engine.connect() as connection:
            connection.execute(select(1))
            schema_missing = _check_schema(connection)
            try:
                result = connection.execute(text("SELECT schema_version FROM settings ORDER BY id LIMIT 1"))
                row = result.first()
                if row is not None:
                    value = row[0]
                    schema_version = int(value) if value is not None else 0
                if schema_version is None:
                    schema_version = 0
                schema_ok = schema_version >= SCHEMA_VERSION if schema_version else False
            except SQLAlchemyError:
                schema_version = 0
                schema_ok = False
    except OperationalError as exc:
        return schemas.DBTestResponse(
            ok=False,
            message=f"{target}: {str(exc.orig) if exc.orig else str(exc)}",
            schema_version=None,
            schema_ok=None,
        )
    finally:
        temp_engine.dispose()

    if schema_missing:
        version_fragment = (
            f" (גרסת סכימה {schema_version} - נדרש עדכון)"
            if schema_version is not None
            else ""
        )
        return schemas.DBTestResponse(
            ok=False,
            message=f"{target.capitalize()} connection succeeded but missing tables: {', '.join(schema_missing)}{version_fragment}",
            schema_version=schema_version,
            schema_ok=False if schema_version is not None else None,
        )

    version_fragment = ""
    if schema_version is not None:
        version_fragment = (
            f" (גרסת סכימה {schema_version} - {'עדכנית' if schema_ok else 'נדרש עדכון'})"
        )

    return schemas.DBTestResponse(
        ok=True,
        message=f"{target.capitalize()} connection and schema verified{version_fragment}",
        schema_version=schema_version,
        schema_ok=schema_ok,
    )


@api_router.get("/db/test", response_model=schemas.DBTestResponse)
def test_database_connection_get(
    db_host: Optional[str] = None,
    db_port: Optional[int] = None,
    db_user: Optional[str] = None,
    db_password: Optional[str] = None,
    target: str = "primary",
):
    overrides = _normalize_overrides(
        schemas.DBTestRequest(
            db_host=db_host,
            db_port=db_port,
            db_user=db_user,
            db_password=db_password,
            target=target,
        )
    )
    return _run_connection_test(overrides)


@api_router.post("/db/test", response_model=schemas.DBTestResponse)
def test_database_connection_post(payload: schemas.DBTestRequest):
    overrides = _normalize_overrides(payload)
    return _run_connection_test(overrides)


@api_router.post("/db/init", response_model=schemas.DBTestResponse)
def create_database_schema(target: str = "active"):
    valid_targets = {"primary", "secondary", "both", "active"}
    if target not in valid_targets:
        raise HTTPException(status_code=400, detail="יעד לא מוכר לחיבור לבסיס הנתונים")

    try:
        current_setting = _load_setting()
    except OperationalError:
        current_setting = None

    active_label = determine_primary_label(current_setting)
    if target == "active":
        target_labels = [active_label]
    elif target == "both":
        target_labels = ["primary", "secondary"]
    else:
        target_labels = [target]

    messages: list[str] = []
    success = True

    for label in target_labels:
        if label not in DATABASE_TARGETS:
            continue
        if target == "active" and not connection_active(current_setting, label):
            messages.append(f"{label}: מסומן כלא פעיל — דילוג")
            continue
        try:
            url = build_connection_url(
                current_setting,
                target=label,
                allow_missing=True,
                require_active=(target == "active"),
            )
        except ValueError as exc:
            messages.append(f"{label}: {exc}")
            success = False
            continue

        if not url:
            messages.append(f"{label}: לא הוגדרו פרטי חיבור — דילוג")
            continue

        temp_engine = create_engine(url, pool_pre_ping=True)
        try:
            ensure_legacy_schema(temp_engine)
            Base.metadata.create_all(temp_engine)

            TempSession = sessionmaker(bind=temp_engine, autoflush=False, expire_on_commit=False)
            with TempSession() as temp_session:
                existing = temp_session.scalar(select(Setting))
                if not existing:
                    new_setting = Setting(
                        currency=current_setting.currency if current_setting else "ILS",
                        db_host=current_setting.db_host if current_setting and current_setting.db_host else settings.mysql_host,
                        db_port=current_setting.db_port if current_setting and current_setting.db_port else settings.mysql_port,
                        db_user=current_setting.db_user if current_setting and current_setting.db_user else settings.mysql_user,
                        db_password=(
                            current_setting.db_password
                            if current_setting and current_setting.db_password is not None
                            else settings.mysql_password
                        ),
                        brand_name=current_setting.brand_name if current_setting and current_setting.brand_name else "העסק שלי",
                        theme_color=current_setting.theme_color if current_setting and current_setting.theme_color else "#1b3aa6",
                        secondary_db_host=current_setting.secondary_db_host if current_setting else None,
                        secondary_db_port=current_setting.secondary_db_port if current_setting else None,
                        secondary_db_user=current_setting.secondary_db_user if current_setting else None,
                        secondary_db_password=current_setting.secondary_db_password if current_setting else None,
                        primary_database=current_setting.primary_database if current_setting and current_setting.primary_database in DATABASE_TARGETS else determine_primary_label(current_setting),
                        primary_db_active=current_setting.primary_db_active if current_setting else True,
                        secondary_db_active=current_setting.secondary_db_active if current_setting else False,
                        show_clock_device_ids=current_setting.show_clock_device_ids if current_setting else True,
                        schema_version=SCHEMA_VERSION,
                    )
                    populate_setting_defaults(new_setting)
                    temp_session.add(new_setting)
                    temp_session.commit()
                else:
                    populate_setting_defaults(existing)
                    if existing.schema_version < SCHEMA_VERSION:
                        existing.schema_version = SCHEMA_VERSION
                    temp_session.flush()
                    temp_session.commit()
        except OperationalError as exc:
            success = False
            messages.append(f"{label}: {str(exc.orig) if exc.orig else str(exc)}")
        else:
            messages.append(f"{label}: הסכימה עודכנה")
        finally:
            temp_engine.dispose()

    refreshed_setting = _load_setting()
    if refreshed_setting:
        try:
            configure_from_setting(refreshed_setting)
        except ValueError as exc:
            success = False
            messages.append(str(exc))

    joined_message = " | ".join(messages) if messages else "No databases processed"
    return schemas.DBTestResponse(ok=success, message=joined_message)


@api_router.post("/db/sync", response_model=schemas.DatabaseSyncResponse)
def synchronize_databases(payload: schemas.DatabaseSyncRequest):
    if payload.source.lower() == payload.target.lower():
        raise HTTPException(status_code=400, detail="מקור ויעד הסנכרון חייבים להיות שונים")

    with session_scope() as session:
        setting = session.scalar(select(Setting))
        if not setting:
            raise HTTPException(status_code=400, detail="לא נמצאו נתוני הגדרות")

        setting, admin = _validate_admin_pin(
            session,
            payload.requestor_admin_id,
            payload.requestor_pin,
            bypass_lock=True,
        )

        populate_setting_defaults(setting)
        try:
            configure_from_setting(setting)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        original_lock_state = bool(setting.write_lock_active)
        auto_locked = False
        if not original_lock_state:
            setting.write_lock_active = True
            session.flush()
            auto_locked = True

        try:
            copied = _perform_database_sync(payload.source, payload.target)
        finally:
            if auto_locked:
                if payload.auto_unlock:
                    setting.write_lock_active = False
                session.flush()

        _sync_setting_pin_hash(session)
        admins = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()
        session.flush()

        _record_admin_audit(
            session,
            admin,
            "database.sync",
            {
                "source": payload.source,
                "target": payload.target,
                "copied": copied,
            },
        )

        total_copied = sum(copied.values())
        message = (
            f"הועתקו {total_copied} רשומות מ-{payload.source} אל {payload.target}"
            if total_copied
            else "לא נמצאו נתונים חדשים לסנכרון"
        )

        return schemas.DatabaseSyncResponse(ok=True, message=message, copied=copied)


@api_router.get("/employees", response_model=list[schemas.EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    employees = db.scalars(select(Employee).order_by(Employee.full_name)).all()
    return employees


@api_router.post("/employees", response_model=schemas.EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = Employee(
        full_name=payload.full_name,
        employee_code=payload.employee_code,
        id_number=payload.id_number,
        hourly_rate=Decimal(payload.hourly_rate),
        active=payload.active,
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig).lower() if getattr(exc, "orig", None) else ""
        if "employee_code" in message:
            detail = "קוד העובד כבר בשימוש"
        elif "id_number" in message:
            detail = "מספר הזיהוי כבר בשימוש"
        else:
            detail = "שגיאה בעת שמירת העובד"
        raise HTTPException(status_code=400, detail=detail)
    return employee


@api_router.get("/employees/export")
def export_employees(db: Session = Depends(get_db)):
    employees = db.scalars(select(Employee).order_by(Employee.full_name)).all()
    employee_payload = [
        {
            "full_name": employee.full_name,
            "employee_code": employee.employee_code,
            "id_number": employee.id_number,
            "hourly_rate": float(employee.hourly_rate or 0),
            "active": employee.active,
        }
        for employee in employees
    ]

    code_by_id = {employee.id: employee.employee_code for employee in employees}
    entries = db.scalars(select(TimeEntry)).all()
    entry_payload = []
    for entry in entries:
        employee_code = code_by_id.get(entry.employee_id)
        if not employee_code:
            continue
        entry_payload.append(
            {
                "employee_code": employee_code,
                "clock_in": entry.clock_in.isoformat(),
                "clock_out": entry.clock_out.isoformat() if entry.clock_out else None,
                "manual": entry.is_manual,
                "clock_in_device_id": entry.clock_in_device_id,
                "clock_out_device_id": entry.clock_out_device_id,
            }
        )

    return {"employees": employee_payload, "time_entries": entry_payload}


@api_router.post("/employees/import")
def import_employees(payload: schemas.EmployeesImportPayload, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    if payload.replace_existing:
        db.execute(delete(TimeEntry))
        db.execute(delete(Employee))
        db.flush()

    existing_employees = db.scalars(select(Employee)).all()
    code_to_employee: dict[str, Employee] = {emp.employee_code: emp for emp in existing_employees}
    id_to_employee: dict[str, Employee] = {
        emp.id_number: emp for emp in existing_employees if emp.id_number
    }

    for incoming in payload.employees:
        employee = code_to_employee.get(incoming.employee_code)
        if not employee and incoming.id_number:
            employee = id_to_employee.get(incoming.id_number)
        if not employee:
            employee = Employee(
                full_name=incoming.full_name,
                employee_code=incoming.employee_code,
                id_number=incoming.id_number,
                hourly_rate=incoming.hourly_rate,
                active=incoming.active,
            )
            db.add(employee)
            code_to_employee[incoming.employee_code] = employee
            if incoming.id_number:
                id_to_employee[incoming.id_number] = employee
        else:
            employee.full_name = incoming.full_name
            employee.hourly_rate = incoming.hourly_rate
            employee.active = incoming.active
            if incoming.id_number is not None:
                employee.id_number = incoming.id_number

    db.flush()

    # refresh mapping with IDs
    refreshed = list(db.scalars(select(Employee)).all())
    code_to_employee = {emp.employee_code: emp for emp in refreshed}
    id_to_employee = {emp.id_number: emp for emp in refreshed if emp.id_number}

    for entry in payload.time_entries:
        employee = code_to_employee.get(entry.employee_code)
        if not employee:
            continue
        clock_in = entry.clock_in.replace(tzinfo=None)
        clock_out = entry.clock_out.replace(tzinfo=None) if entry.clock_out else None
        new_entry = TimeEntry(
            employee_id=employee.id,
            clock_in=clock_in,
            clock_out=clock_out,
            is_manual=entry.manual if entry.manual is not None else False,
            clock_in_device_id=entry.clock_in_device_id,
            clock_out_device_id=entry.clock_out_device_id,
        )
        db.add(new_entry)

    db.flush()
    return {"employees": len(code_to_employee), "time_entries": len(payload.time_entries)}


@api_router.put("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(employee_id: int, payload: schemas.EmployeeUpdate, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")

    if payload.full_name is not None:
        employee.full_name = payload.full_name
    if payload.employee_code is not None:
        employee.employee_code = payload.employee_code
    updated_fields = getattr(payload, "model_fields_set", getattr(payload, "__fields_set__", set()))
    if "id_number" in updated_fields:
        employee.id_number = payload.id_number
    if payload.hourly_rate is not None:
        employee.hourly_rate = Decimal(payload.hourly_rate)
    if payload.active is not None:
        employee.active = payload.active

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        message = str(exc.orig).lower() if getattr(exc, "orig", None) else ""
        if "employee_code" in message:
            detail = "קוד העובד כבר בשימוש"
        elif "id_number" in message:
            detail = "מספר הזיהוי כבר בשימוש"
        else:
            detail = "שגיאה בעת עדכון העובד"
        raise HTTPException(status_code=400, detail=detail)

    return employee


@api_router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")
    db.delete(employee)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/employees/{employee_id}/entries", response_model=schemas.ManualEntryOut, status_code=status.HTTP_201_CREATED)
def add_manual_entry(employee_id: int, payload: schemas.ManualEntryCreate, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")
    clock_in = payload.clock_in.replace(tzinfo=None) if payload.clock_in.tzinfo else payload.clock_in
    clock_out = payload.clock_out.replace(tzinfo=None) if payload.clock_out.tzinfo else payload.clock_out
    entry = TimeEntry(employee=employee, clock_in=clock_in, clock_out=clock_out, is_manual=True)
    db.add(entry)
    db.flush()
    return entry
    

@api_router.put("/time-entries/{entry_id}", response_model=schemas.ManualEntryOut)
def update_time_entry(entry_id: int, payload: schemas.TimeEntryUpdate, db: Session = Depends(get_db)):
    if not payload.pin:
        raise HTTPException(status_code=400, detail="יש להזין קוד PIN")
    if not payload.admin_id:
        raise HTTPException(status_code=400, detail="יש להזין מזהה מנהל")
    setting, admin = _validate_admin_pin(db, payload.admin_id, payload.pin)
    if setting.schema_version < SCHEMA_VERSION:
        raise HTTPException(status_code=409, detail="גרסת הסכימה בבסיס הנתונים ישנה. אנא הריצו יצירת/עדכון סכימה במסך ההגדרות לפני עריכת משמרות.")

    entry = db.get(TimeEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="רשומת המשמרת לא נמצאה")

    new_clock_in = entry.clock_in
    new_clock_out = entry.clock_out

    if payload.clock_in is not None:
        new_clock_in = payload.clock_in.replace(tzinfo=None) if payload.clock_in.tzinfo else payload.clock_in
    if payload.clock_out is not None:
        new_clock_out = payload.clock_out.replace(tzinfo=None) if payload.clock_out.tzinfo else payload.clock_out

    if new_clock_out and new_clock_in and new_clock_out <= new_clock_in:
        raise HTTPException(status_code=400, detail="זמן היציאה חייב להיות מאוחר מזמן הכניסה")

    entry.clock_in = new_clock_in
    entry.clock_out = new_clock_out
    entry.is_manual = True
    db.flush()

    _record_admin_audit(
        db,
        admin,
        "time_entries.update",
        {"entry_id": entry.id, "employee_id": entry.employee_id},
    )

    return schemas.ManualEntryOut(
        id=entry.id,
        employee_id=entry.employee_id,
        clock_in=entry.clock_in,
        clock_out=entry.clock_out,
        manual=entry.is_manual,
    )


@api_router.delete("/time-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_entry(
    entry_id: int,
    payload: schemas.TimeEntryDelete = Body(...),
    db: Session = Depends(get_db),
):
    if not payload.pin:
        raise HTTPException(status_code=400, detail="יש להזין קוד PIN")
    if not payload.admin_id:
        raise HTTPException(status_code=400, detail="יש להזין מזהה מנהל")
    setting, admin = _validate_admin_pin(db, payload.admin_id, payload.pin)
    if setting.schema_version < SCHEMA_VERSION:
        raise HTTPException(status_code=409, detail="גרסת הסכימה בבסיס הנתונים ישנה. אנא הריצו יצירת/עדכון סכימה במסך ההגדרות לפני מחיקת משמרות.")

    entry = db.get(TimeEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="רשומת המשמרת לא נמצאה")

    db.delete(entry)
    _record_admin_audit(
        db,
        admin,
        "time_entries.delete",
        {"entry_id": entry_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.post("/clock/in", response_model=schemas.ClockResponse)
def clock_in(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = get_active_employee_by_code(db, payload.employee_code)
    open_entry = db.scalar(
        select(TimeEntry).where(TimeEntry.employee_id == employee.id, TimeEntry.clock_out.is_(None))
    )
    if open_entry:
        return schemas.ClockResponse(
            status="already_in",
            message=f"{employee.full_name} כבר במשמרת פעילה",
            entry_id=open_entry.id,
            device_id=open_entry.clock_in_device_id,
            device_match=(payload.device_id == open_entry.clock_in_device_id if payload.device_id and open_entry.clock_in_device_id else None),
        )
    now = dt.datetime.now()
    entry = TimeEntry(
        employee=employee,
        clock_in=now,
        is_manual=False,
        clock_in_device_id=payload.device_id,
    )
    db.add(entry)
    db.flush()
    return schemas.ClockResponse(
        status="clocked_in",
        message="הכניסה נרשמה בהצלחה",
        entry_id=entry.id,
        device_id=payload.device_id,
        device_match=True,
    )


@api_router.post("/clock/out", response_model=schemas.ClockResponse)
def clock_out(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
    _ensure_writes_allowed(db)
    employee = get_active_employee_by_code(db, payload.employee_code)
    open_entry = db.scalar(
        select(TimeEntry)
        .where(TimeEntry.employee_id == employee.id, TimeEntry.clock_out.is_(None))
        .order_by(TimeEntry.clock_in.desc())
    )
    if not open_entry:
        return schemas.ClockResponse(
            status="not_in",
            message=f"{employee.full_name} אינו במשמרת פעילה",
        )
    open_entry.clock_out = dt.datetime.now()
    open_entry.clock_out_device_id = payload.device_id
    device_match: Optional[bool] = None
    if payload.device_id and open_entry.clock_in_device_id:
        device_match = payload.device_id == open_entry.clock_in_device_id
    db.flush()
    return schemas.ClockResponse(
        status="clocked_out",
        message="היציאה נרשמה בהצלחה",
        entry_id=open_entry.id,
        device_id=payload.device_id,
        device_match=device_match,
    )


@api_router.post("/clock/status", response_model=schemas.ClockStatus)
def clock_status(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
    employee = get_active_employee_by_code(db, payload.employee_code)
    open_entry = db.scalar(
        select(TimeEntry).where(TimeEntry.employee_id == employee.id, TimeEntry.clock_out.is_(None))
    )
    return schemas.ClockStatus(is_clocked_in=open_entry is not None)


@api_router.get("/clock/active", response_model=list[schemas.ActiveShift])
def list_active_shifts(db: Session = Depends(get_db)):
    now = dt.datetime.now()
    setting = db.scalar(select(Setting))
    show_devices = True
    if setting is not None and setting.show_clock_device_ids is not None:
        show_devices = setting.show_clock_device_ids
    entries = db.execute(
        select(TimeEntry, Employee)
        .join(Employee)
        .where(TimeEntry.clock_out.is_(None))
        .order_by(TimeEntry.clock_in.asc())
    ).all()
    response: list[schemas.ActiveShift] = []
    for entry, employee in entries:
        elapsed = now - entry.clock_in
        minutes = max(int(elapsed.total_seconds() // 60), 0)
        response.append(
            schemas.ActiveShift(
                employee_id=employee.id,
                full_name=employee.full_name,
                clock_in=entry.clock_in,
                elapsed_minutes=minutes,
                clock_in_device_id=entry.clock_in_device_id if show_devices else None,
            )
        )
    return response


def _collect_summary_report(
    db: Session,
    month: Optional[str],
    start: Optional[dt.date],
    end: Optional[dt.date],
    employee_id: Optional[int],
) -> tuple[dt.date, dt.date, list[schemas.ReportResponseRow]]:
    range_start, range_end = resolve_date_range(month, start, end)

    range_start_dt = dt.datetime.combine(range_start, dt.time.min)
    range_end_dt = dt.datetime.combine(range_end, dt.time.max)

    stmt = (
        select(
            Employee.id.label("employee_id"),
            Employee.full_name,
            Employee.id_number,
            Employee.hourly_rate,
            func.sum(
                func.timestampdiff(
                    text("SECOND"),
                    func.greatest(TimeEntry.clock_in, range_start_dt),
                    func.least(TimeEntry.clock_out, range_end_dt),
                )
            ).label("total_seconds"),
        )
        .join(TimeEntry, TimeEntry.employee_id == Employee.id)
        .where(TimeEntry.clock_in <= range_end_dt)
        .where(TimeEntry.clock_out.isnot(None))
        .where(TimeEntry.clock_out >= range_start_dt)
        .group_by(Employee.id)
    )
    if employee_id:
        stmt = stmt.where(Employee.id == employee_id)

    rows = db.execute(stmt).all()
    response_rows: list[schemas.ReportResponseRow] = []
    for row in rows:
        seconds = int(row.total_seconds or 0)
        hours = round(seconds / 3600, 2)
        rate = Decimal(row.hourly_rate or 0)
        total_pay = float(rate * Decimal(hours))
        response_rows.append(
            schemas.ReportResponseRow(
                employee_id=row.employee_id,
                full_name=row.full_name,
                id_number=row.id_number,
                total_seconds=seconds,
                total_hours=hours,
                hourly_rate=rate,
                total_pay=total_pay,
            )
        )
    return range_start, range_end, response_rows


@api_router.get("/reports", response_model=schemas.ReportResponse)
def generate_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    range_start, range_end, rows = _collect_summary_report(db, month, start, end, employee_id)
    return schemas.ReportResponse(rows=rows, range_start=range_start, range_end=range_end)


def _collect_daily_report(
    db: Session,
    month: Optional[str],
    start: Optional[dt.date],
    end: Optional[dt.date],
    employee_id: Optional[int],
) -> tuple[dt.date, dt.date, list[schemas.DailyEmployeeReport]]:
    range_start, range_end = resolve_date_range(month, start, end)
    range_start_dt = dt.datetime.combine(range_start, dt.time.min)
    range_end_dt = dt.datetime.combine(range_end, dt.time.max)

    stmt = (
        select(TimeEntry, Employee)
        .join(Employee)
        .where(TimeEntry.clock_out.isnot(None))
        .where(TimeEntry.clock_in <= range_end_dt)
        .where(TimeEntry.clock_out >= range_start_dt)
        .order_by(Employee.full_name, TimeEntry.clock_in)
    )
    if employee_id:
        stmt = stmt.where(Employee.id == employee_id)

    rows = db.execute(stmt).all()

    grouped: dict[int, list[schemas.DailyShiftRow]] = defaultdict(list)
    employee_meta: dict[int, tuple[str, Decimal, Optional[str]]] = {}

    for entry, employee in rows:
        if not entry.clock_out:
            continue
        employee_meta[employee.id] = (employee.full_name, Decimal(employee.hourly_rate or 0), employee.id_number)
        duration = entry.clock_out - entry.clock_in
        minutes = max(int(duration.total_seconds() // 60), 0)
        hours = Decimal(minutes) / Decimal(60)
        rate = Decimal(employee.hourly_rate or 0)
        estimated_pay = float(rate * hours)
        grouped[employee.id].append(
            schemas.DailyShiftRow(
                entry_id=entry.id,
                shift_date=entry.clock_in.date(),
                clock_in=entry.clock_in,
                clock_out=entry.clock_out,
                duration_minutes=minutes,
                hourly_rate=rate,
                estimated_pay=estimated_pay,
                clock_in_device_id=entry.clock_in_device_id,
                clock_out_device_id=entry.clock_out_device_id,
            )
        )

    employees_response: list[schemas.DailyEmployeeReport] = []
    for emp_id, shifts in grouped.items():
        full_name, _, id_number = employee_meta.get(emp_id, ("", Decimal(0), None))
        employees_response.append(
            schemas.DailyEmployeeReport(
                employee_id=emp_id,
                full_name=full_name,
                id_number=id_number,
                shifts=shifts,
            )
        )

    employees_response.sort(key=lambda item: item.full_name)

    return range_start, range_end, employees_response


@api_router.get("/reports/daily", response_model=schemas.DailyReportResponse)
def generate_daily_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    include_device_ids: bool = True,
    db: Session = Depends(get_db),
):
    setting = db.scalar(select(Setting))
    effective_include_devices = include_device_ids
    if setting is not None and not setting.show_clock_device_ids:
        effective_include_devices = False
    range_start, range_end, employees_response = _collect_daily_report(
        db, month, start, end, employee_id
    )
    if not effective_include_devices:
        masked_employees: list[schemas.DailyEmployeeReport] = []
        for employee in employees_response:
            masked_shifts = [
                schemas.DailyShiftRow(
                    entry_id=shift.entry_id,
                    shift_date=shift.shift_date,
                    clock_in=shift.clock_in,
                    clock_out=shift.clock_out,
                    duration_minutes=shift.duration_minutes,
                    hourly_rate=shift.hourly_rate,
                    estimated_pay=shift.estimated_pay,
                    clock_in_device_id=None,
                    clock_out_device_id=None,
                )
                for shift in employee.shifts
            ]
            masked_employees.append(
                schemas.DailyEmployeeReport(
                    employee_id=employee.employee_id,
                    full_name=employee.full_name,
                    id_number=employee.id_number,
                    shifts=masked_shifts,
                )
            )
        employees_response = masked_employees
    return schemas.DailyReportResponse(
        range_start=range_start,
        range_end=range_end,
        employees=employees_response,
    )


@api_router.get("/reports/daily/export")
def export_daily_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    include_payments: bool = False,
    include_device_ids: bool = True,
    db: Session = Depends(get_db),
):
    setting = db.scalar(select(Setting))
    effective_include_devices = include_device_ids
    if setting is not None and not setting.show_clock_device_ids:
        effective_include_devices = False
    range_start, range_end, employees_response = _collect_daily_report(
        db, month, start, end, employee_id
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Report"
    headers = [
        "Employee ID",
        "Employee",
        "Start Date",
        "Start Time",
        "End Date",
        "End Time",
        "Total Hours (HH:MM)",
    ]
    if effective_include_devices:
        headers.extend(["Clock-in Device", "Clock-out Device"])
    if include_payments:
        headers.append("Estimated Pay")
    ws.append(headers)

    for employee in employees_response:
        for shift in employee.shifts:
            total_hours = format_minutes_hhmm(shift.duration_minutes)
            start_date = shift.clock_in.date().isoformat()
            end_date = shift.clock_out.date().isoformat()
            row = [
                employee.id_number or "",
                employee.full_name,
                start_date,
                shift.clock_in.strftime("%H:%M"),
                end_date,
                shift.clock_out.strftime("%H:%M"),
                total_hours,
            ]
            if effective_include_devices:
                row.extend([shift.clock_in_device_id or "", shift.clock_out_device_id or ""])
            if include_payments:
                row.append(shift.estimated_pay)
            ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = (
        f"daily-report-{range_start.isoformat()}-{range_end.isoformat()}.xlsx"
    )

    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    }

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@api_router.get("/reports/export")
def export_summary_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    include_payments: bool = True,
    include_device_ids: bool = True,
    db: Session = Depends(get_db),
):
    range_start, range_end, rows = _collect_summary_report(db, month, start, end, employee_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary Report"

    headers = ["Employee ID", "Employee", "Total Hours (HH:MM)"]
    if include_payments:
        headers.extend(["Hourly Rate", "Estimated Pay"])
    ws.append(headers)

    for row in rows:
        formatted_duration = format_seconds_hhmm(int(row.total_seconds or 0))
        line = [row.id_number or "", row.full_name, formatted_duration]
        if include_payments:
            line.extend([float(row.hourly_rate or 0), row.total_pay])
        ws.append(line)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"summary-report-{range_start.isoformat()}-{range_end.isoformat()}.xlsx"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\""
    }

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@api_router.get("/admins", response_model=list[schemas.AdminSummary])
def list_admins():
    with session_scope() as session:
        admins = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()
        return admins


@api_router.post("/admins", response_model=schemas.AdminSummary, status_code=status.HTTP_201_CREATED)
def create_admin(payload: schemas.AdminCreateRequest):
    with session_scope() as session:
        total_admins = session.scalar(select(func.count(AdminAccount.id))) or 0
        requestor: Optional[AdminAccount] = None
        if total_admins > 0:
            if not payload.requestor_admin_id or not payload.requestor_pin:
                raise HTTPException(status_code=403, detail="יש להזין מזהה מנהל וקוד PIN פעיל")
            _, requestor = _validate_admin_pin(session, payload.requestor_admin_id, payload.requestor_pin)
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="שם המנהל נדרש")
        lower_name = name.lower()
        existing = session.scalar(select(AdminAccount).where(func.lower(AdminAccount.name) == lower_name))
        if existing:
            raise HTTPException(status_code=400, detail="שם המנהל כבר בשימוש")
        admin = AdminAccount(name=name, pin_hash=hash_pin(payload.pin), active=True)
        session.add(admin)
        session.flush()
        _sync_setting_pin_hash(session)
        if requestor:
            _record_admin_audit(session, requestor, "admins.create", {"admin_id": admin.id})
        return admin


@api_router.put("/admins/{admin_id}", response_model=schemas.AdminSummary)
def update_admin(admin_id: int, payload: schemas.AdminUpdateRequest):
    with session_scope() as session:
        _, requestor = _validate_admin_pin(session, payload.requestor_admin_id, payload.requestor_pin)
        admin = session.get(AdminAccount, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="מנהל לא נמצא")

        changed: dict[str, object] = {}

        if payload.name is not None:
            new_name = payload.name.strip()
            if not new_name:
                raise HTTPException(status_code=400, detail="שם המנהל לא יכול להיות ריק")
            duplicate = session.scalar(
                select(AdminAccount)
                .where(func.lower(AdminAccount.name) == new_name.lower())
                .where(AdminAccount.id != admin_id)
            )
            if duplicate:
                raise HTTPException(status_code=400, detail="שם המנהל כבר בשימוש")
            admin.name = new_name
            changed["name"] = new_name

        if payload.new_pin:
            admin.pin_hash = hash_pin(payload.new_pin)
            changed["pin"] = True

        if payload.active is not None:
            admin.active = payload.active
            changed["active"] = payload.active

        session.flush()
        _sync_setting_pin_hash(session)
        _record_admin_audit(
            session,
            requestor,
            "admins.update",
            {"admin_id": admin.id, **changed} if changed else {"admin_id": admin.id},
        )
        return admin


@api_router.get("/admins/{admin_id}/audit", response_model=list[schemas.AdminAuditLogEntry])
def list_admin_audit(admin_id: int, limit: int = 50):
    limit = max(1, min(limit, 500))
    with session_scope() as session:
        admin = session.get(AdminAccount, admin_id)
        if not admin:
            raise HTTPException(status_code=404, detail="מנהל לא נמצא")
        entries = (
            session.execute(
                select(AdminAuditLog)
                .where(AdminAuditLog.admin_id == admin_id)
                .order_by(AdminAuditLog.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [_serialize_audit_entry(entry) for entry in entries]


@api_router.get("/settings", response_model=schemas.SettingsOut)
def get_settings_endpoint(db: Session = Depends(get_db)):
    schema_ok = False
    setting: Optional[Setting] = None
    admins: list[AdminAccount] = []
    try:
        engine = get_engine()
        ensure_legacy_schema(engine)
        with session_scope() as session:
            setting = session.scalar(select(Setting))
            if not setting:
                setting = Setting(
                    currency="ILS",
                    db_host=settings.mysql_host,
                    db_port=settings.mysql_port,
                    db_user=settings.mysql_user,
                    db_password=settings.mysql_password,
                    secondary_db_host=None,
                    secondary_db_port=None,
                    secondary_db_user=None,
                    secondary_db_password=None,
                    primary_database="primary",
                    primary_db_active=True,
                    secondary_db_active=False,
                    show_clock_device_ids=True,
                    schema_version=SCHEMA_VERSION,
                    brand_name="העסק שלי",
                    theme_color="#1b3aa6",
                )
                session.add(setting)
                session.flush()
            admins = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()
            _sync_setting_pin_hash(session)
        populate_setting_defaults(setting)
        schema_ok = setting.schema_version == SCHEMA_VERSION
    except (RuntimeError, OperationalError):
        setting = Setting(
            currency="ILS",
            db_host=None,
            db_port=None,
            db_user=None,
            db_password=None,
            secondary_db_host=None,
            secondary_db_port=None,
            secondary_db_user=None,
            secondary_db_password=None,
            primary_database="primary",
            primary_db_active=False,
            secondary_db_active=False,
            show_clock_device_ids=True,
            schema_version=0,
            brand_name="העסק שלי",
            theme_color="#1b3aa6",
        )
        schema_ok = False
        admins = []

    return schemas.SettingsOut(
        currency=setting.currency,
        pin_set=any(admin.active for admin in admins),
        write_lock_active=bool(setting.write_lock_active),
        db_host=setting.db_host,
        db_port=setting.db_port,
        db_user=setting.db_user,
        db_password=setting.db_password,
        secondary_db_host=setting.secondary_db_host,
        secondary_db_port=setting.secondary_db_port,
        secondary_db_user=setting.secondary_db_user,
        secondary_db_password=setting.secondary_db_password,
        primary_db_active=bool(setting.primary_db_active),
        secondary_db_active=bool(setting.secondary_db_active),
        primary_database=setting.primary_database or "primary",
        schema_version=setting.schema_version,
        schema_ok=schema_ok,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
        show_clock_device_ids=bool(setting.show_clock_device_ids),
        admins=admins,
    )


@api_router.put("/settings", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsUpdate):
    override = _override_from_update(payload)
    _ensure_primary_connection(override)

    def normalize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    if not payload.current_pin:
        raise HTTPException(status_code=400, detail="יש להזין PIN נוכחי לצורך עדכון")

    with session_scope() as session:
        setting = session.scalar(select(Setting))
        if not setting:
            setting = Setting(currency="ILS")
            session.add(setting)
            session.flush()

        previous_primary_label = setting.primary_database or "primary"
        original_lock_state = bool(setting.write_lock_active)

        setting, admin = _validate_admin_pin(session, payload.admin_id, payload.current_pin, bypass_lock=True)

        changed_fields: set[str] = set()

        if payload.currency and payload.currency != setting.currency:
            setting.currency = payload.currency
            changed_fields.add("currency")

        if payload.db_host is not None:
            setting.db_host = normalize(payload.db_host)
            changed_fields.add("db_host")
        if payload.db_port is not None:
            setting.db_port = payload.db_port
            changed_fields.add("db_port")
        if payload.db_user is not None:
            setting.db_user = normalize(payload.db_user)
            changed_fields.add("db_user")
        if payload.db_password is not None:
            setting.db_password = payload.db_password
            changed_fields.add("db_password")
        if payload.secondary_db_host is not None:
            setting.secondary_db_host = normalize(payload.secondary_db_host)
            changed_fields.add("secondary_db_host")
        if payload.secondary_db_port is not None:
            setting.secondary_db_port = payload.secondary_db_port
            changed_fields.add("secondary_db_port")
        if payload.secondary_db_user is not None:
            setting.secondary_db_user = normalize(payload.secondary_db_user)
            changed_fields.add("secondary_db_user")
        if payload.secondary_db_password is not None:
            setting.secondary_db_password = payload.secondary_db_password
            changed_fields.add("secondary_db_password")
        if payload.primary_db_active is not None:
            setting.primary_db_active = payload.primary_db_active
            changed_fields.add("primary_db_active")
        if payload.secondary_db_active is not None:
            setting.secondary_db_active = payload.secondary_db_active
            changed_fields.add("secondary_db_active")

        if not connection_active(setting, "primary") and not connection_active(setting, "secondary"):
            raise HTTPException(status_code=400, detail="יש להפעיל לפחות מסד נתונים אחד")

        if payload.primary_database is not None:
            if payload.primary_database not in DATABASE_TARGETS:
                raise HTTPException(status_code=400, detail="בחירה לא תקינה של מסד נתונים ראשי")
            setting.primary_database = payload.primary_database
            changed_fields.add("primary_database")

        new_primary_label = setting.primary_database or "primary"

        if payload.brand_name is not None:
            setting.brand_name = payload.brand_name
            changed_fields.add("brand_name")
        if payload.theme_color is not None:
            setting.theme_color = payload.theme_color
            changed_fields.add("theme_color")
        if payload.show_clock_device_ids is not None:
            setting.show_clock_device_ids = payload.show_clock_device_ids
            changed_fields.add("show_clock_device_ids")
        if payload.write_lock_active is not None:
            setting.write_lock_active = payload.write_lock_active
            changed_fields.add("write_lock_active")

        if payload.write_lock_active is not None:
            setting.write_lock_active = payload.write_lock_active
            changed_fields.add("write_lock_active")

        if payload.new_pin:
            admin.pin_hash = hash_pin(payload.new_pin)
            changed_fields.add("admin_pin")

        if setting.primary_database == "secondary" and not connection_configured(setting, "secondary"):
            raise HTTPException(status_code=400, detail="לא הוגדרו פרטי חיבור למסד הנתונים המשני")

        populate_setting_defaults(setting)
        try:
            configure_from_setting(setting)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        final_lock_state = bool(setting.write_lock_active)
        sync_summary: Optional[dict[str, int]] = None
        if new_primary_label != previous_primary_label:
            temp_lock_applied = False
            if not final_lock_state:
                setting.write_lock_active = True
                session.flush()
                temp_lock_applied = True
            try:
                sync_summary = _perform_database_sync(previous_primary_label, new_primary_label)
            finally:
                if temp_lock_applied:
                    setting.write_lock_active = final_lock_state
                    session.flush()
            changed_fields.add("database_sync")

        _sync_setting_pin_hash(session)
        admins = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()

        audit_details: dict[str, object] = {}
        if changed_fields:
            audit_details["fields"] = sorted(changed_fields)
        if sync_summary:
            audit_details["sync"] = sync_summary
        _record_admin_audit(
            session,
            admin,
            "settings.update",
            audit_details or None,
        )

        schema_ok = setting.schema_version == SCHEMA_VERSION
        session.flush()

        return schemas.SettingsOut(
            currency=setting.currency,
            pin_set=any(candidate.active for candidate in admins),
            write_lock_active=bool(setting.write_lock_active),
            db_host=setting.db_host,
            db_port=setting.db_port,
            db_user=setting.db_user,
            db_password=setting.db_password,
            secondary_db_host=setting.secondary_db_host,
            secondary_db_port=setting.secondary_db_port,
            secondary_db_user=setting.secondary_db_user,
            secondary_db_password=setting.secondary_db_password,
            primary_db_active=bool(setting.primary_db_active),
            secondary_db_active=bool(setting.secondary_db_active),
            primary_database=setting.primary_database or "primary",
            schema_version=setting.schema_version,
            schema_ok=schema_ok,
            brand_name=setting.brand_name,
            theme_color=setting.theme_color,
            show_clock_device_ids=bool(setting.show_clock_device_ids),
            admins=admins,
        )


@api_router.get("/settings/export", response_model=schemas.SettingsExport)
def export_settings(db: Session = Depends(get_db)):
    try:
        ensure_legacy_schema(get_engine())
    except (RuntimeError, OperationalError):
        raise HTTPException(status_code=400, detail="לא הוגדר חיבור למסד הנתונים לצורך ייצוא.")
    with session_scope() as session:
        setting = session.scalar(select(Setting))
        if not setting:
            raise HTTPException(status_code=400, detail="אין נתוני הגדרות לשמירה במסד הנתונים.")
        populate_setting_defaults(setting)
        admin_records = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()
    active_admin = next((candidate for candidate in admin_records if candidate.active), admin_records[0] if admin_records else None)
    pin_hash = active_admin.pin_hash if active_admin else None
    admin_exports = [
        schemas.AdminExportDefinition(name=admin.name, pin_hash=admin.pin_hash, active=admin.active)
        for admin in admin_records
    ]
    return schemas.SettingsExport(
        currency=setting.currency,
        db_host=setting.db_host,
        db_port=setting.db_port,
        db_user=setting.db_user,
        db_password=setting.db_password,
        secondary_db_host=setting.secondary_db_host,
        secondary_db_port=setting.secondary_db_port,
        secondary_db_user=setting.secondary_db_user,
        secondary_db_password=setting.secondary_db_password,
        primary_database=setting.primary_database,
        primary_db_active=bool(setting.primary_db_active),
        secondary_db_active=bool(setting.secondary_db_active),
        schema_version=setting.schema_version,
        pin_hash=pin_hash,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
        show_clock_device_ids=bool(setting.show_clock_device_ids),
        write_lock_active=bool(setting.write_lock_active),
        admins=admin_exports,
    )


@api_router.post("/settings/import", response_model=schemas.SettingsOut)
def import_settings(payload: schemas.SettingsImport):
    override = _override_from_import(payload)
    _ensure_primary_connection(override)

    with session_scope() as session:
        setting = session.scalar(select(Setting))
        if not setting:
            setting = Setting(currency="ILS")
            session.add(setting)
            session.flush()

        existing_admins = session.scalars(select(AdminAccount).order_by(AdminAccount.id)).all()
        requestor_admin: Optional[AdminAccount] = None
        if existing_admins:
            if not payload.requestor_admin_id or not payload.requestor_pin:
                raise HTTPException(status_code=403, detail="נדרשת הזדהות מנהל לצורך יבוא הגדרות")
            _, requestor_admin = _validate_admin_pin(session, payload.requestor_admin_id, payload.requestor_pin)

        changed_fields: set[str] = set()

        if payload.currency is not None:
            setting.currency = payload.currency
            changed_fields.add("currency")
        if payload.db_host is not None:
            setting.db_host = payload.db_host.strip() if payload.db_host else None
            changed_fields.add("db_host")
        if payload.db_port is not None:
            setting.db_port = payload.db_port
            changed_fields.add("db_port")
        if payload.db_user is not None:
            setting.db_user = payload.db_user.strip() if payload.db_user else None
            changed_fields.add("db_user")
        if payload.db_password is not None:
            setting.db_password = payload.db_password
            changed_fields.add("db_password")
        if payload.secondary_db_host is not None:
            setting.secondary_db_host = payload.secondary_db_host.strip() if payload.secondary_db_host else None
            changed_fields.add("secondary_db_host")
        if payload.secondary_db_port is not None:
            setting.secondary_db_port = payload.secondary_db_port
            changed_fields.add("secondary_db_port")
        if payload.secondary_db_user is not None:
            setting.secondary_db_user = payload.secondary_db_user.strip() if payload.secondary_db_user else None
            changed_fields.add("secondary_db_user")
        if payload.secondary_db_password is not None:
            setting.secondary_db_password = payload.secondary_db_password
            changed_fields.add("secondary_db_password")
        if payload.primary_db_active is not None:
            setting.primary_db_active = payload.primary_db_active
            changed_fields.add("primary_db_active")
        if payload.secondary_db_active is not None:
            setting.secondary_db_active = payload.secondary_db_active
            changed_fields.add("secondary_db_active")
        if not connection_active(setting, "primary") and not connection_active(setting, "secondary"):
            setting.primary_db_active = True
            setting.secondary_db_active = False

        if payload.primary_database is not None and payload.primary_database in DATABASE_TARGETS:
            setting.primary_database = payload.primary_database
            changed_fields.add("primary_database")
        if payload.schema_version is not None:
            setting.schema_version = payload.schema_version
            changed_fields.add("schema_version")
        if payload.brand_name is not None:
            setting.brand_name = payload.brand_name
            changed_fields.add("brand_name")
        if payload.theme_color is not None:
            setting.theme_color = payload.theme_color
            changed_fields.add("theme_color")
        if payload.show_clock_device_ids is not None:
            setting.show_clock_device_ids = payload.show_clock_device_ids
            changed_fields.add("show_clock_device_ids")

        admin_definitions_applied = False
        if payload.admins:
            admin_definitions_applied = True
            existing_by_name = {admin.name: admin for admin in existing_admins}
            for definition in payload.admins:
                hashed = definition.pin_hash or (hash_pin(definition.pin) if definition.pin else None)
                if not hashed:
                    raise HTTPException(status_code=400, detail=f"Admin '{definition.name}' חייב לכלול PIN או pin_hash")
                admin_obj = existing_by_name.get(definition.name)
                if admin_obj:
                    admin_obj.pin_hash = hashed
                    if definition.active is not None:
                        admin_obj.active = bool(definition.active)
                else:
                    admin_obj = AdminAccount(
                        name=definition.name,
                        pin_hash=hashed,
                        active=bool(definition.active) if definition.active is not None else True,
                    )
                    session.add(admin_obj)
                    session.flush()
                    existing_admins.append(admin_obj)
                    existing_by_name[definition.name] = admin_obj
        elif payload.pin or payload.pin_hash:
            admin_definitions_applied = True
            hashed_pin = payload.pin_hash or hash_pin(payload.pin)
            primary_admin = session.scalar(select(AdminAccount).where(AdminAccount.name == "Primary Admin"))
            if not primary_admin:
                primary_admin = AdminAccount(name="Primary Admin", pin_hash=hashed_pin, active=True)
                session.add(primary_admin)
                session.flush()
                existing_admins.append(primary_admin)
            else:
                primary_admin.pin_hash = hashed_pin
                if not primary_admin.active:
                    primary_admin.active = True

        if admin_definitions_applied:
            changed_fields.add("admins")

        existing_admins = session.scalars(select(AdminAccount).order_by(AdminAccount.name)).all()

        if setting.primary_database == "secondary" and not connection_configured(setting, "secondary"):
            setting.primary_database = "primary"

        populate_setting_defaults(setting)
        try:
            configure_from_setting(setting)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        _sync_setting_pin_hash(session)

        if requestor_admin:
            _record_admin_audit(
                session,
                requestor_admin,
                "settings.import",
                {"fields": sorted(changed_fields)} if changed_fields else None,
            )

        schema_ok = setting.schema_version == SCHEMA_VERSION
        session.flush()

        return schemas.SettingsOut(
            currency=setting.currency,
            pin_set=any(candidate.active for candidate in existing_admins),
            write_lock_active=bool(setting.write_lock_active),
            db_host=setting.db_host,
            db_port=setting.db_port,
            db_user=setting.db_user,
            db_password=setting.db_password,
            secondary_db_host=setting.secondary_db_host,
            secondary_db_port=setting.secondary_db_port,
            secondary_db_user=setting.secondary_db_user,
            secondary_db_password=setting.secondary_db_password,
            primary_db_active=bool(setting.primary_db_active),
            secondary_db_active=bool(setting.secondary_db_active),
            primary_database=setting.primary_database or "primary",
            schema_version=setting.schema_version,
            schema_ok=schema_ok,
            brand_name=setting.brand_name,
            theme_color=setting.theme_color,
            show_clock_device_ids=bool(setting.show_clock_device_ids),
            admins=existing_admins,
        )


@api_router.post("/auth/verify-pin", response_model=schemas.PinVerifyResponse)
def verify_pin_endpoint(payload: schemas.PinVerifyRequest):
    with session_scope() as session:
        admin = session.get(AdminAccount, payload.admin_id)
        if not admin or not admin.active:
            raise HTTPException(status_code=403, detail="פרטי הניהול שגויים")
        if not verify_pin(payload.pin, admin.pin_hash):
            raise HTTPException(status_code=403, detail="קוד PIN שגוי")
        _record_admin_audit(session, admin, "auth.verify", None)
    return schemas.PinVerifyResponse(ok=True)


app.include_router(api_router, prefix="/api")

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
def format_minutes_hhmm(total_minutes: int) -> str:
    hours, minutes = divmod(max(total_minutes, 0), 60)
    return f"{hours:02d}:{minutes:02d}"


def format_seconds_hhmm(total_seconds: int) -> str:
    total_minutes = int(round(max(total_seconds, 0) / 60))
    return format_minutes_hhmm(total_minutes)
