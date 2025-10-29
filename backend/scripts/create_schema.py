"""Create or update the HubClock MySQL schema."""

from sqlalchemy import select

from app.config import get_settings
from app.database import get_engine, session_scope
from app.main import ensure_legacy_schema, populate_setting_defaults
from app.models import Base, Setting


def main() -> None:
    engine = get_engine()
    ensure_legacy_schema(engine)
    Base.metadata.create_all(engine)
    with session_scope() as session:
        setting = session.scalars(select(Setting)).first()
        if not setting:
            settings = get_settings()
            setting = Setting(
                currency="ILS",
                db_host=settings.mysql_host,
                db_port=settings.mysql_port,
                db_user=settings.mysql_user,
                db_password=settings.mysql_password,
                brand_name="העסק שלי",
                theme_color="#1b3aa6",
            )
            session.add(setting)
        else:
            populate_setting_defaults(setting)
    print("Schema ensured.")


if __name__ == "__main__":
    main()
