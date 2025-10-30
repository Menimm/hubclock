from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class EmployeeBase(BaseModel):
    full_name: str = Field(..., max_length=120)
    employee_code: str = Field(..., max_length=32)
    id_number: Optional[str] = Field(
        None,
        max_length=32,
        pattern=r"^\d{1,32}$",
        description="External employee identifier (numeric string, leading zeros allowed)",
    )
    hourly_rate: Decimal = Field(ge=0)
    active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    employee_code: Optional[str] = Field(None, max_length=32)
    id_number: Optional[str] = Field(
        None,
        max_length=32,
        pattern=r"^\d{1,32}$",
    )
    hourly_rate: Optional[Decimal] = Field(None, ge=0)
    active: Optional[bool] = None


class EmployeeOut(EmployeeBase):
    id: int

    class Config:
        from_attributes = True


class ClockRequest(BaseModel):
    employee_code: str = Field(..., max_length=32)
    device_id: Optional[str] = Field(None, max_length=64)


class ActiveShift(BaseModel):
    employee_id: int
    full_name: str
    clock_in: dt.datetime
    elapsed_minutes: int
    clock_in_device_id: Optional[str] = None


class ClockResponse(BaseModel):
    status: str
    message: str
    entry_id: Optional[int] = None
    device_id: Optional[str] = None
    device_match: Optional[bool] = None


class ClockStatus(BaseModel):
    is_clocked_in: bool


class ManualEntryCreate(BaseModel):
    employee_id: int
    clock_in: dt.datetime
    clock_out: dt.datetime
    manual: bool = True

    def model_post_init(self, __context):
        if self.clock_out <= self.clock_in:
            raise ValueError("clock_out must be after clock_in")


class ManualEntryOut(BaseModel):
    id: int
    employee_id: int
    clock_in: dt.datetime
    clock_out: Optional[dt.datetime]
    manual: bool

    class Config:
        from_attributes = True


class ReportResponseRow(BaseModel):
    employee_id: int
    full_name: str
    id_number: Optional[str] = None
    total_seconds: int
    total_hours: float
    hourly_rate: Decimal
    total_pay: float


class ReportResponse(BaseModel):
    rows: list[ReportResponseRow]
    range_start: dt.date
    range_end: dt.date


class DailyShiftRow(BaseModel):
    entry_id: int
    shift_date: dt.date
    clock_in: dt.datetime
    clock_out: dt.datetime
    duration_minutes: int
    hourly_rate: Decimal
    estimated_pay: float
    clock_in_device_id: Optional[str] = None
    clock_out_device_id: Optional[str] = None


class DailyEmployeeReport(BaseModel):
    employee_id: int
    full_name: str
    id_number: Optional[str] = None
    shifts: list[DailyShiftRow]


class DailyReportResponse(BaseModel):
    range_start: dt.date
    range_end: dt.date
    employees: list[DailyEmployeeReport]


class SettingsOut(BaseModel):
    currency: str
    pin_set: bool
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    secondary_db_host: Optional[str] = None
    secondary_db_port: Optional[int] = None
    secondary_db_user: Optional[str] = None
    secondary_db_password: Optional[str] = None
    primary_db_active: bool = True
    secondary_db_active: bool = False
    primary_database: str = "primary"
    schema_version: int
    schema_ok: bool
    brand_name: Optional[str] = None
    theme_color: Optional[str] = None
    show_clock_device_ids: bool = True


class SettingsUpdate(BaseModel):
    currency: Optional[str] = Field(None, max_length=8)
    current_pin: Optional[str] = Field(None, min_length=4, max_length=12)
    new_pin: Optional[str] = Field(None, min_length=4, max_length=12)
    db_host: Optional[str] = Field(None, max_length=128)
    db_port: Optional[int] = None
    db_user: Optional[str] = Field(None, max_length=64)
    db_password: Optional[str] = Field(None, max_length=128)
    secondary_db_host: Optional[str] = Field(None, max_length=128)
    secondary_db_port: Optional[int] = None
    secondary_db_user: Optional[str] = Field(None, max_length=64)
    secondary_db_password: Optional[str] = Field(None, max_length=128)
    primary_database: Optional[str] = Field(None, pattern="^(primary|secondary)$")
    primary_db_active: Optional[bool] = None
    secondary_db_active: Optional[bool] = None
    brand_name: Optional[str] = Field(None, max_length=120)
    theme_color: Optional[str] = Field(None, max_length=16)
    show_clock_device_ids: Optional[bool] = None


class DBTestResponse(BaseModel):
    ok: bool
    message: str
    schema_version: Optional[int] = None
    schema_ok: Optional[bool] = None


class DBTestRequest(BaseModel):
    db_host: Optional[str] = Field(None, max_length=128)
    db_port: Optional[int] = None
    db_user: Optional[str] = Field(None, max_length=64)
    db_password: Optional[str] = Field(None, max_length=128)
    target: str = Field("primary", pattern="^(primary|secondary)$")


class PinVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=12)


class PinVerifyResponse(BaseModel):
    ok: bool


class SettingsExport(BaseModel):
    currency: str
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    secondary_db_host: Optional[str] = None
    secondary_db_port: Optional[int] = None
    secondary_db_user: Optional[str] = None
    secondary_db_password: Optional[str] = None
    primary_database: Optional[str] = None
    primary_db_active: Optional[bool] = None
    secondary_db_active: Optional[bool] = None
    schema_version: Optional[int] = None
    pin_hash: Optional[str] = None
    brand_name: Optional[str] = None
    theme_color: Optional[str] = None
    show_clock_device_ids: Optional[bool] = None


class SettingsImport(BaseModel):
    currency: Optional[str] = None
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    secondary_db_host: Optional[str] = None
    secondary_db_port: Optional[int] = None
    secondary_db_user: Optional[str] = None
    secondary_db_password: Optional[str] = None
    primary_database: Optional[str] = Field(None, pattern="^(primary|secondary)$")
    primary_db_active: Optional[bool] = None
    secondary_db_active: Optional[bool] = None
    schema_version: Optional[int] = None
    pin: Optional[str] = Field(None, min_length=4, max_length=12)
    pin_hash: Optional[str] = None
    brand_name: Optional[str] = None
    theme_color: Optional[str] = None
    show_clock_device_ids: Optional[bool] = None


class EmployeeImport(BaseModel):
    full_name: str
    employee_code: str
    id_number: Optional[str] = None
    hourly_rate: Decimal = Field(ge=0)
    active: bool = True


class TimeEntryImport(BaseModel):
    employee_code: str
    clock_in: dt.datetime
    clock_out: Optional[dt.datetime] = None
    manual: Optional[bool] = None
    clock_in_device_id: Optional[str] = None
    clock_out_device_id: Optional[str] = None


class TimeEntryUpdate(BaseModel):
    clock_in: Optional[dt.datetime] = None
    clock_out: Optional[dt.datetime] = None
    pin: str = Field(..., min_length=4, max_length=12)


class TimeEntryDelete(BaseModel):
    pin: str = Field(..., min_length=4, max_length=12)


class EmployeesImportPayload(BaseModel):
    replace_existing: bool = False
    employees: list[EmployeeImport]
    time_entries: list[TimeEntryImport] = []
