#!/usr/bin/env python3
"""CLI utility for resetting the HubClock admin PIN out-of-band.

This script is intended for emergency recovery when the existing admin PIN
is unknown. It requires shell access to the host and updates the single
row in the `settings` table with a freshly hashed PIN.
"""

from __future__ import annotations

import argparse
import logging
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.config import get_settings  # noqa: E402
from backend.app.database import configure_engines, session_scope  # noqa: E402
from backend.app.models import Setting  # noqa: E402
from backend.app.security import hash_pin  # noqa: E402


MIN_PIN_LENGTH = 4
MAX_PIN_LENGTH = 12

LOGGER = logging.getLogger("hubclock.reset_admin_pin")


def validate_pin(pin: str) -> str:
    candidate = pin.strip()
    if len(candidate) < MIN_PIN_LENGTH or len(candidate) > MAX_PIN_LENGTH:
        raise ValueError(
            f"PIN must be between {MIN_PIN_LENGTH} and {MAX_PIN_LENGTH} characters."
        )
    return candidate


def prompt_for_pin(echo: bool = False) -> str:
    while True:
        prompt_fn = input if echo else getpass
        first = prompt_fn("Enter new admin PIN: ").strip()
        second = prompt_fn("Confirm new admin PIN: ").strip()
        if first != second:
            print("PINs did not match. Please try again.", file=sys.stderr)
            continue
        try:
            return validate_pin(first)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)


def acquire_pin(pin_arg: Optional[str], echo: bool, require_confirmation: bool) -> str:
    if pin_arg:
        candidate = validate_pin(pin_arg)
        if require_confirmation:
            confirmer = input if echo else getpass
            confirmation = confirmer("Confirm new admin PIN: ").strip()
            if candidate != confirmation:
                raise ValueError("Provided PIN and confirmation do not match.")
        return candidate
    return prompt_for_pin(echo=echo)


def reset_pin(new_pin: str) -> None:
    LOGGER.info("Loading application settings")
    settings = get_settings()
    configure_engines(settings.sqlalchemy_database_uri)

    with session_scope() as session:
        setting = session.scalar(select(Setting))
        if not setting:
            LOGGER.info("No settings row found; creating a new one before assigning PIN")
            setting = Setting(currency="ILS")
            session.add(setting)
            session.flush()
        else:
            LOGGER.info("Existing settings row located (id=%s)", setting.id)

        LOGGER.info("Updating admin PIN hash")
        setting.pin_hash = hash_pin(new_pin)
        session.flush()
        LOGGER.info("Admin PIN hash persisted to database")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the HubClock admin PIN by directly updating the database."
    )
    parser.add_argument(
        "--pin",
        help="New admin PIN value. If omitted, you will be prompted securely.",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Echo PIN input to the console (useful for automation, avoid in production).",
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="Skip confirmation prompt when --pin is provided.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = parse_args(argv or sys.argv[1:])

    try:
        new_pin = acquire_pin(
            pin_arg=args.pin,
            echo=args.echo,
            require_confirmation=not args.no_confirm,
        )
    except ValueError as exc:
        print(f"Aborting: {exc}", file=sys.stderr)
        return 1

    try:
        reset_pin(new_pin)
    except Exception as exc:  # pragma: no cover - defensive guardrail
        print(f"Failed to reset admin PIN: {exc}", file=sys.stderr)
        return 1

    LOGGER.info("Admin PIN updated successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
