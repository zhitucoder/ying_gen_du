from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.common.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from src.api import models  # noqa: F401  (register mappings)

    Base.metadata.create_all(bind=engine)


def ensure_schema() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "username" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(32) NULL"))
        if "password_hash" not in columns:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL")
            )
        if "auth_type" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN auth_type VARCHAR(16) "
                    "NOT NULL DEFAULT 'local'"
                )
            )
            conn.execute(
                text("UPDATE users SET auth_type='device' WHERE username IS NULL")
            )
        if "phone" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL"))
        if "phone_verified_at" not in columns:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN phone_verified_at DATETIME NULL")
            )
        if "token_version" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN token_version INT "
                    "NOT NULL DEFAULT 0"
                )
            )

    indexes = inspect(engine).get_indexes("users")
    has_username_unique = any(
        index.get("unique") and index.get("column_names") == ["username"]
        for index in indexes
    )
    if not has_username_unique:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD UNIQUE KEY uk_users_username (username)")
            )

    has_phone_unique = any(
        index.get("unique") and index.get("column_names") == ["phone"]
        for index in indexes
    )
    if not has_phone_unique:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD UNIQUE KEY uk_users_phone (phone)")
            )

    project_columns = {
        column["name"] for column in inspect(engine).get_columns("projects")
    }
    if "media_asset_id" not in project_columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE projects ADD COLUMN media_asset_id BIGINT NULL")
            )
    project_indexes = inspect(engine).get_indexes("projects")
    if not any(index["name"] == "idx_projects_asset" for index in project_indexes):
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE projects ADD KEY idx_projects_asset (media_asset_id)")
            )

    from src.api.nicknames import ensure_nickname_unique

    ensure_nickname_unique(engine)
