import re
import unicodedata
from typing import Optional

from sqlalchemy import inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.models import User
from src.common.config import settings

CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)


class NicknameError(Exception):
    pass


class NicknameTaken(NicknameError):
    pass


def normalize_nickname(raw: str) -> str:
    value = unicodedata.normalize("NFKC", raw or "").translate(ZERO_WIDTH).strip()
    return CONTROL_RE.sub("", value)


def validate_nickname(value: str) -> str:
    if len(value) < 2 or len(value) > 20:
        raise NicknameError("昵称长度需为 2-20 个字符")
    return value


def allowed_prefixes() -> list[str]:
    values = [
        item.strip()
        for item in settings.nickname_allowed_prefixes.split(",")
        if item.strip()
    ]
    return values or [settings.nickname_default_prefix]


def resolve_prefix(prefix: Optional[str]) -> str:
    value = (prefix or settings.nickname_default_prefix).strip()
    if value not in allowed_prefixes():
        raise NicknameError("不支持的昵称前缀")
    return value


def _next_sequence(db: Session, prefix: str) -> int:
    db.execute(
        text(
            "INSERT INTO nickname_counters (prefix, next_value) VALUES (:prefix, 1) "
            "ON DUPLICATE KEY UPDATE next_value = LAST_INSERT_ID(next_value + 1)"
        ),
        {"prefix": prefix},
    )
    db.commit()
    value = db.execute(
        text("SELECT next_value FROM nickname_counters WHERE prefix = :prefix"),
        {"prefix": prefix},
    ).scalar_one()
    return int(value)


def generate_nickname(db: Session, prefix: str) -> str:
    width = settings.nickname_sequence_width
    for _ in range(20):
        value = _next_sequence(db, prefix)
        candidate = f"{prefix}{value:0{width}d}"
        if not db.scalar(select(User.id).where(User.nickname == candidate)):
            return candidate
    raise NicknameError("昵称生成失败，请稍后重试")


def create_user_with_nickname(
    db: Session,
    *,
    nickname: Optional[str],
    nickname_prefix: Optional[str],
    **fields,
) -> User:
    provided = normalize_nickname(nickname or "")
    if provided:
        provided = validate_nickname(provided)
        if db.scalar(select(User.id).where(User.nickname == provided)):
            raise NicknameTaken("昵称已被使用")
        user = User(nickname=provided, **fields)
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise NicknameTaken("昵称已被使用") from exc
        return user

    prefix = resolve_prefix(nickname_prefix)
    for _ in range(5):
        candidate = generate_nickname(db, prefix)
        user = User(nickname=candidate, **fields)
        db.add(user)
        try:
            db.commit()
            return user
        except IntegrityError:
            db.rollback()
            continue
    raise NicknameError("昵称生成失败，请稍后重试")


def ensure_nickname_unique(engine) -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    indexes = inspector.get_indexes("users")
    if any(
        index.get("unique") and index.get("column_names") == ["nickname"]
        for index in indexes
    ):
        return

    with Session(engine) as db:
        empty_users = db.scalars(
            select(User).where(or_(User.nickname.is_(None), User.nickname == ""))
        ).all()
        for user in empty_users:
            user.nickname = generate_nickname(db, resolve_prefix(None))
        db.commit()

        duplicates = db.execute(
            text(
                "SELECT nickname FROM users WHERE nickname IS NOT NULL "
                "GROUP BY nickname HAVING COUNT(*) > 1"
            )
        ).all()
        for (nickname,) in duplicates:
            users = db.scalars(
                select(User).where(User.nickname == nickname).order_by(User.id)
            ).all()
            for user in users[1:]:
                user.nickname = generate_nickname(db, resolve_prefix(None))
            db.commit()

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE users ADD UNIQUE KEY uk_users_nickname (nickname)")
        )
