from __future__ import annotations

import datetime as dt

from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    id_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, unique=True)
    hourly_rate: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    entries: Mapped[list[TimeEntry]] = relationship(
        "TimeEntry", back_populates="employee", cascade="all, delete-orphan"
    )


class TimeEntry(Base):
    __tablename__ = "time_entries"
    __table_args__ = (UniqueConstraint("employee_id", "clock_out", name="uq_employee_clock_out"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    clock_in: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    clock_out: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=False))
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    clock_in_device_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    clock_out_device_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    employee: Mapped[Employee] = relationship("Employee", back_populates="entries")

    @property
    def manual(self) -> bool:
        return self.is_manual

    @manual.setter
    def manual(self, value: bool) -> None:
        self.is_manual = value


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="ILS")
    pin_hash: Mapped[Optional[str]] = mapped_column(String(255))
    db_host: Mapped[Optional[str]] = mapped_column(String(128))
    db_port: Mapped[Optional[int]] = mapped_column(Integer)
    db_user: Mapped[Optional[str]] = mapped_column(String(64))
    db_password: Mapped[Optional[str]] = mapped_column(String(128))
    brand_name: Mapped[Optional[str]] = mapped_column(String(120))
    theme_color: Mapped[Optional[str]] = mapped_column(String(16))
    secondary_db_host: Mapped[Optional[str]] = mapped_column(String(128))
    secondary_db_port: Mapped[Optional[int]] = mapped_column(Integer)
    secondary_db_user: Mapped[Optional[str]] = mapped_column(String(64))
    secondary_db_password: Mapped[Optional[str]] = mapped_column(String(128))
    primary_database: Mapped[Optional[str]] = mapped_column(String(16), default="primary")
    primary_db_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    secondary_db_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_clock_device_ids: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class AdminAccount(Base):
    __tablename__ = "admin_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )

    audit_logs: Mapped[list["AdminAuditLog"]] = relationship(
        "AdminAuditLog",
        back_populates="admin",
        cascade="all, delete-orphan",
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admin_accounts.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=dt.datetime.utcnow)

    admin: Mapped[AdminAccount] = relationship("AdminAccount", back_populates="audit_logs")
