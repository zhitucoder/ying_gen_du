import hashlib
import hmac
import re
import secrets

from src.common.config import settings

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_phone(raw: str) -> str:
    value = re.sub(r"[\s\-]", "", raw or "")
    if value.startswith("+86"):
        value = value[3:]
    elif value.startswith("86") and len(value) == 13:
        value = value[2:]
    if not PHONE_RE.match(value):
        raise ValueError("手机号格式不正确")
    return value


def to_e164(phone: str) -> str:
    return f"+86{phone}"


def mask_phone(phone: str) -> str:
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[-4:]}"
    if len(phone) > 4:
        return f"{phone[:3]}****{phone[-2:]}"
    return "****"


def generate_code(length: int) -> str:
    return str(secrets.randbelow(10**length)).zfill(length)


def hash_code(phone: str, code: str, salt: str) -> str:
    message = f"{phone}:{code}:{salt}".encode("utf-8")
    return hmac.new(
        settings.sms_code_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


def make_code_hash(phone: str, code: str) -> str:
    salt = secrets.token_hex(8)
    return f"{salt}${hash_code(phone, code, salt)}"


def check_code_hash(phone: str, code: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_code(phone, code, salt), digest)
