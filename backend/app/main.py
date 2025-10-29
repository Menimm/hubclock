from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Optional

from collections import defaultdict
from io import BytesIO
from urllib.parse import quote_plus

from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from . import schemas
from .config import get_settings
from .database import configure_engines, get_db, get_engine, session_scope
from .models import Base, Employee, Setting, TimeEntry
from .security import hash_pin, verify_pin

settings = get_settings()
app = FastAPI(title="HubClock API", version="0.1.0")
SCHEMA_VERSION = 2
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

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


def _validate_admin_pin(session: Session, pin: str) -> Setting:
    setting = session.scalar(select(Setting))
    if not setting or not setting.pin_hash:
        raise HTTPException(status_code=400, detail="לא הוגדר קוד PIN לניהול")
    if not verify_pin(pin, setting.pin_hash):
        raise HTTPException(status_code=403, detail="קוד ה-PIN שגוי")
    return setting


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
                "schema_version": "ALTER TABLE settings ADD COLUMN schema_version INT NOT NULL DEFAULT 1",
            }
            for column, ddl in alterations.items():
                if column not in columns:
                    conn.execute(text(ddl))


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
    get_engine()


def _load_setting() -> Optional[Setting]:
    try:
        with session_scope() as session:
            return session.scalar(select(Setting))
    except OperationalError:
        return None


def _normalize_overrides(payload: Optional[schemas.DBTestRequest]) -> Optional[schemas.DBTestRequest]:
    if not payload:
        return None
    filtered = payload.model_dump(exclude_none=True)
    if not filtered:
        return None
    return schemas.DBTestRequest(**filtered)


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


@app.get("/db/test", response_model=schemas.DBTestResponse)
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


@app.post("/db/test", response_model=schemas.DBTestResponse)
def test_database_connection_post(payload: schemas.DBTestRequest):
    overrides = _normalize_overrides(payload)
    return _run_connection_test(overrides)


@app.post("/db/init", response_model=schemas.DBTestResponse)
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


@app.get("/employees", response_model=list[schemas.EmployeeOut])
def list_employees(db: Session = Depends(get_db)):
    employees = db.scalars(select(Employee).order_by(Employee.full_name)).all()
    return employees


@app.post("/employees", response_model=schemas.EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(payload: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    employee = Employee(
        full_name=payload.full_name,
        employee_code=payload.employee_code,
        hourly_rate=Decimal(payload.hourly_rate),
        active=payload.active,
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="קוד העובד כבר בשימוש")
    return employee


@app.get("/employees/export")
def export_employees(db: Session = Depends(get_db)):
    employees = db.scalars(select(Employee).order_by(Employee.full_name)).all()
    employee_payload = [
        {
            "full_name": employee.full_name,
            "employee_code": employee.employee_code,
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
            }
        )

    return {"employees": employee_payload, "time_entries": entry_payload}


@app.post("/employees/import")
def import_employees(payload: schemas.EmployeesImportPayload, db: Session = Depends(get_db)):
    if payload.replace_existing:
        db.execute(delete(TimeEntry))
        db.execute(delete(Employee))
        db.flush()

    existing_employees = db.scalars(select(Employee)).all()
    code_to_employee: dict[str, Employee] = {emp.employee_code: emp for emp in existing_employees}

    for incoming in payload.employees:
        employee = code_to_employee.get(incoming.employee_code)
        if not employee:
            employee = Employee(
                full_name=incoming.full_name,
                employee_code=incoming.employee_code,
                hourly_rate=incoming.hourly_rate,
                active=incoming.active,
            )
            db.add(employee)
            code_to_employee[incoming.employee_code] = employee
        else:
            employee.full_name = incoming.full_name
            employee.hourly_rate = incoming.hourly_rate
            employee.active = incoming.active

    db.flush()

    # refresh mapping with IDs
    code_to_employee = {
        emp.employee_code: emp
        for emp in db.scalars(select(Employee)).all()
    }

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
        )
        db.add(new_entry)

    db.flush()
    return {"employees": len(code_to_employee), "time_entries": len(payload.time_entries)}


@app.put("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(employee_id: int, payload: schemas.EmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")

    if payload.full_name is not None:
        employee.full_name = payload.full_name
    if payload.employee_code is not None:
        employee.employee_code = payload.employee_code
    if payload.hourly_rate is not None:
        employee.hourly_rate = Decimal(payload.hourly_rate)
    if payload.active is not None:
        employee.active = payload.active

    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="קוד העובד כבר בשימוש")

    return employee


@app.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")
    db.delete(employee)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/employees/{employee_id}/entries", response_model=schemas.ManualEntryOut, status_code=status.HTTP_201_CREATED)
def add_manual_entry(employee_id: int, payload: schemas.ManualEntryCreate, db: Session = Depends(get_db)):
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="העובד לא נמצא")
    clock_in = payload.clock_in.replace(tzinfo=None) if payload.clock_in.tzinfo else payload.clock_in
    clock_out = payload.clock_out.replace(tzinfo=None) if payload.clock_out.tzinfo else payload.clock_out
    entry = TimeEntry(employee=employee, clock_in=clock_in, clock_out=clock_out, is_manual=True)
    db.add(entry)
    db.flush()
    return entry
    

@app.put("/time-entries/{entry_id}", response_model=schemas.ManualEntryOut)
def update_time_entry(entry_id: int, payload: schemas.TimeEntryUpdate, db: Session = Depends(get_db)):
    if not payload.pin:
        raise HTTPException(status_code=400, detail="יש להזין קוד PIN")
    setting = _validate_admin_pin(db, payload.pin)
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

    return schemas.ManualEntryOut(
        id=entry.id,
        employee_id=entry.employee_id,
        clock_in=entry.clock_in,
        clock_out=entry.clock_out,
        manual=entry.is_manual,
    )


@app.delete("/time-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_entry(
    entry_id: int,
    payload: schemas.TimeEntryDelete = Body(...),
    db: Session = Depends(get_db),
):
    if not payload.pin:
        raise HTTPException(status_code=400, detail="יש להזין קוד PIN")
    setting = _validate_admin_pin(db, payload.pin)
    if setting.schema_version < SCHEMA_VERSION:
        raise HTTPException(status_code=409, detail="גרסת הסכימה בבסיס הנתונים ישנה. אנא הריצו יצירת/עדכון סכימה במסך ההגדרות לפני מחיקת משמרות.")

    entry = db.get(TimeEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="רשומת המשמרת לא נמצאה")

    db.delete(entry)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/clock/in", response_model=schemas.ClockResponse)
def clock_in(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
    employee = get_active_employee_by_code(db, payload.employee_code)
    open_entry = db.scalar(
        select(TimeEntry).where(TimeEntry.employee_id == employee.id, TimeEntry.clock_out.is_(None))
    )
    if open_entry:
        return schemas.ClockResponse(
            status="already_in",
            message=f"{employee.full_name} כבר במשמרת פעילה",
            entry_id=open_entry.id,
        )
    now = dt.datetime.now()
    entry = TimeEntry(employee=employee, clock_in=now, is_manual=False)
    db.add(entry)
    db.flush()
    return schemas.ClockResponse(status="clocked_in", message="הכניסה נרשמה בהצלחה", entry_id=entry.id)


@app.post("/clock/out", response_model=schemas.ClockResponse)
def clock_out(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
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
    db.flush()
    return schemas.ClockResponse(status="clocked_out", message="היציאה נרשמה בהצלחה", entry_id=open_entry.id)


@app.post("/clock/status", response_model=schemas.ClockStatus)
def clock_status(payload: schemas.ClockRequest, db: Session = Depends(get_db)):
    employee = get_active_employee_by_code(db, payload.employee_code)
    open_entry = db.scalar(
        select(TimeEntry).where(TimeEntry.employee_id == employee.id, TimeEntry.clock_out.is_(None))
    )
    return schemas.ClockStatus(is_clocked_in=open_entry is not None)


@app.get("/clock/active", response_model=list[schemas.ActiveShift])
def list_active_shifts(db: Session = Depends(get_db)):
    now = dt.datetime.now()
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
                total_seconds=seconds,
                total_hours=hours,
                hourly_rate=rate,
                total_pay=total_pay,
            )
        )
    return range_start, range_end, response_rows


@app.get("/reports", response_model=schemas.ReportResponse)
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
    employee_meta: dict[int, tuple[str, Decimal]] = {}

    for entry, employee in rows:
        if not entry.clock_out:
            continue
        employee_meta[employee.id] = (employee.full_name, Decimal(employee.hourly_rate or 0))
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
            )
        )

    employees_response: list[schemas.DailyEmployeeReport] = []
    for emp_id, shifts in grouped.items():
        full_name, _ = employee_meta.get(emp_id, ("", Decimal(0)))
        employees_response.append(
            schemas.DailyEmployeeReport(employee_id=emp_id, full_name=full_name, shifts=shifts)
        )

    employees_response.sort(key=lambda item: item.full_name)

    return range_start, range_end, employees_response


@app.get("/reports/daily", response_model=schemas.DailyReportResponse)
def generate_daily_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    range_start, range_end, employees_response = _collect_daily_report(
        db, month, start, end, employee_id
    )
    return schemas.DailyReportResponse(
        range_start=range_start,
        range_end=range_end,
        employees=employees_response,
    )


@app.get("/reports/daily/export")
def export_daily_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    include_payments: bool = False,
    db: Session = Depends(get_db),
):
    range_start, range_end, employees_response = _collect_daily_report(
        db, month, start, end, employee_id
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Report"
    headers = ["Employee", "Start Date", "Start Time", "End Date", "End Time", "Total Hours (HH:MM)"]
    if include_payments:
        headers.append("Estimated Pay")
    ws.append(headers)

    for employee in employees_response:
        for shift in employee.shifts:
            total_hours = format_minutes_hhmm(shift.duration_minutes)
            start_date = shift.clock_in.date().isoformat()
            end_date = shift.clock_out.date().isoformat()
            row = [
                employee.full_name,
                start_date,
                shift.clock_in.strftime("%H:%M"),
                end_date,
                shift.clock_out.strftime("%H:%M"),
                total_hours,
            ]
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


@app.get("/reports/export")
def export_summary_report(
    month: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
    employee_id: Optional[int] = None,
    include_payments: bool = True,
    db: Session = Depends(get_db),
):
    range_start, range_end, rows = _collect_summary_report(db, month, start, end, employee_id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary Report"

    headers = ["Employee", "Total Hours (HH:MM)"]
    if include_payments:
        headers.extend(["Hourly Rate", "Estimated Pay"])
    ws.append(headers)

    for row in rows:
        formatted_duration = format_seconds_hhmm(int(row.total_seconds or 0))
        line = [row.full_name, formatted_duration]
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


@app.get("/settings", response_model=schemas.SettingsOut)
def get_settings_endpoint(db: Session = Depends(get_db)):
    ensure_legacy_schema(get_engine())
    setting = db.scalar(select(Setting))
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
            schema_version=SCHEMA_VERSION,
            brand_name="העסק שלי",
            theme_color="#1b3aa6",
        )
        db.add(setting)
        db.flush()
    populate_setting_defaults(setting)
    return schemas.SettingsOut(
        currency=setting.currency,
        pin_set=bool(setting.pin_hash),
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
        schema_ok=setting.schema_version == SCHEMA_VERSION,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
    )


@app.put("/settings", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    ensure_legacy_schema(get_engine())
    setting = db.scalar(select(Setting))
    if not setting:
        setting = Setting(currency="ILS")
        db.add(setting)
        db.flush()

    if payload.currency:
        setting.currency = payload.currency

    def normalize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    if payload.db_host is not None:
        setting.db_host = normalize(payload.db_host)
    if payload.db_port is not None:
        setting.db_port = payload.db_port
    if payload.db_user is not None:
        setting.db_user = normalize(payload.db_user)
    if payload.db_password is not None:
        setting.db_password = payload.db_password
    if payload.secondary_db_host is not None:
        setting.secondary_db_host = normalize(payload.secondary_db_host)
    if payload.secondary_db_port is not None:
        setting.secondary_db_port = payload.secondary_db_port
    if payload.secondary_db_user is not None:
        setting.secondary_db_user = normalize(payload.secondary_db_user)
    if payload.secondary_db_password is not None:
        setting.secondary_db_password = payload.secondary_db_password
    if payload.primary_db_active is not None:
        setting.primary_db_active = payload.primary_db_active
    if payload.secondary_db_active is not None:
        setting.secondary_db_active = payload.secondary_db_active

    if not connection_active(setting, "primary") and not connection_active(setting, "secondary"):
        raise HTTPException(status_code=400, detail="יש להפעיל לפחות מסד נתונים אחד")

    if payload.primary_database is not None:
        if payload.primary_database not in DATABASE_TARGETS:
            raise HTTPException(status_code=400, detail="בחירה לא תקינה של מסד נתונים ראשי")
        setting.primary_database = payload.primary_database

    if payload.brand_name is not None:
        setting.brand_name = payload.brand_name
    if payload.theme_color is not None:
        setting.theme_color = payload.theme_color

    if payload.new_pin:
        if setting.pin_hash:
            if not payload.current_pin:
                raise HTTPException(status_code=400, detail="יש להזין PIN נוכחי כדי לעדכן")
            if not verify_pin(payload.current_pin, setting.pin_hash):
                raise HTTPException(status_code=403, detail="קוד ה-PIN הנוכחי שגוי")
        setting.pin_hash = hash_pin(payload.new_pin)

    if setting.primary_database == "secondary" and not connection_configured(setting, "secondary"):
        raise HTTPException(status_code=400, detail="לא הוגדרו פרטי חיבור למסד הנתונים המשני")

    db.flush()
    populate_setting_defaults(setting)
    try:
        configure_from_setting(setting)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.SettingsOut(
        currency=setting.currency,
        pin_set=bool(setting.pin_hash),
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
        schema_ok=setting.schema_version == SCHEMA_VERSION,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
    )


@app.get("/settings/export", response_model=schemas.SettingsExport)
def export_settings(db: Session = Depends(get_db)):
    ensure_legacy_schema(get_engine())
    setting = db.scalar(select(Setting))
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
            schema_version=SCHEMA_VERSION,
            brand_name="העסק שלי",
            theme_color="#1b3aa6",
        )
        db.add(setting)
        db.flush()
    populate_setting_defaults(setting)
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
        pin_hash=setting.pin_hash,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
    )


@app.post("/settings/import", response_model=schemas.SettingsOut)
def import_settings(payload: schemas.SettingsImport, db: Session = Depends(get_db)):
    ensure_legacy_schema(get_engine())
    setting = db.scalar(select(Setting))
    if not setting:
        setting = Setting(currency="ILS")
        db.add(setting)
        db.flush()

    if payload.currency is not None:
        setting.currency = payload.currency
    if payload.db_host is not None:
        setting.db_host = payload.db_host.strip() if payload.db_host else None
    if payload.db_port is not None:
        setting.db_port = payload.db_port
    if payload.db_user is not None:
        setting.db_user = payload.db_user.strip() if payload.db_user else None
    if payload.db_password is not None:
        setting.db_password = payload.db_password
    if payload.secondary_db_host is not None:
        setting.secondary_db_host = payload.secondary_db_host.strip() if payload.secondary_db_host else None
    if payload.secondary_db_port is not None:
        setting.secondary_db_port = payload.secondary_db_port
    if payload.secondary_db_user is not None:
        setting.secondary_db_user = payload.secondary_db_user.strip() if payload.secondary_db_user else None
    if payload.secondary_db_password is not None:
        setting.secondary_db_password = payload.secondary_db_password
    if payload.primary_db_active is not None:
        setting.primary_db_active = payload.primary_db_active
    if payload.secondary_db_active is not None:
        setting.secondary_db_active = payload.secondary_db_active
    if not connection_active(setting, "primary") and not connection_active(setting, "secondary"):
        setting.primary_db_active = True
        setting.secondary_db_active = False

    if payload.primary_database is not None and payload.primary_database in DATABASE_TARGETS:
        setting.primary_database = payload.primary_database
    if payload.schema_version is not None:
        setting.schema_version = payload.schema_version
    if payload.brand_name is not None:
        setting.brand_name = payload.brand_name
    if payload.theme_color is not None:
        setting.theme_color = payload.theme_color

    if payload.pin:
        setting.pin_hash = hash_pin(payload.pin)
    elif payload.pin_hash:
        setting.pin_hash = payload.pin_hash

    if setting.primary_database == "secondary" and not connection_configured(setting, "secondary"):
        setting.primary_database = "primary"

    db.flush()
    populate_setting_defaults(setting)
    try:
        configure_from_setting(setting)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.SettingsOut(
        currency=setting.currency,
        pin_set=bool(setting.pin_hash),
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
        schema_ok=setting.schema_version == SCHEMA_VERSION,
        brand_name=setting.brand_name,
        theme_color=setting.theme_color,
    )


@app.post("/auth/verify-pin", response_model=schemas.PinVerifyResponse)
def verify_pin_endpoint(payload: schemas.PinVerifyRequest, db: Session = Depends(get_db)):
    setting = db.scalar(select(Setting))
    if not setting or not setting.pin_hash:
        raise HTTPException(status_code=404, detail="לא הוגדר קוד PIN")
    if not verify_pin(payload.pin, setting.pin_hash):
        raise HTTPException(status_code=403, detail="קוד PIN שגוי")
    return schemas.PinVerifyResponse(ok=True)


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
def format_minutes_hhmm(total_minutes: int) -> str:
    hours, minutes = divmod(max(total_minutes, 0), 60)
    return f"{hours:02d}:{minutes:02d}"


def format_seconds_hhmm(total_seconds: int) -> str:
    total_minutes = int(round(max(total_seconds, 0) / 60))
    return format_minutes_hhmm(total_minutes)
