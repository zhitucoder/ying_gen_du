import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.api.models import SmsCode, SmsSendLog
from src.api.redis_client import get_redis
from src.api.sms import get_sms_provider
from src.api.sms.utils import (
    check_code_hash,
    generate_code,
    make_code_hash,
    normalize_phone,
)
from src.common.config import settings

logger = logging.getLogger(__name__)

ALLOWED_SCENES = {"register", "login", "bind", "reset_password"}
TZ = ZoneInfo("Asia/Shanghai")

RATE_LIMIT_LUA = """
local function current(key) return tonumber(redis.call('GET', key) or '0') end
if current(KEYS[2]) >= tonumber(ARGV[2]) then return -1 end
if current(KEYS[3]) >= tonumber(ARGV[4]) then return -2 end
if current(KEYS[4]) >= tonumber(ARGV[6]) then return -3 end
if current(KEYS[5]) >= tonumber(ARGV[8]) then return -4 end
if current(KEYS[6]) >= tonumber(ARGV[10]) then return -5 end
if not redis.call('SET', KEYS[1], '1', 'NX', 'EX', ARGV[1]) then return 0 end
local keys = {KEYS[2], KEYS[3], KEYS[4], KEYS[5], KEYS[6]}
local ttls = {ARGV[3], ARGV[5], ARGV[7], ARGV[9], ARGV[11]}
for i = 1, 5 do
  redis.call('INCR', keys[i])
  redis.call('EXPIRE', keys[i], ttls[i])
end
return 1
"""


class SmsError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _rate_limit(phone: str, request_ip: str, device_id: str | None) -> None:
    now = datetime.now(TZ)
    day = now.strftime("%Y%m%d")
    hour = now.strftime("%Y%m%d%H")
    ip = (request_ip or "unknown")[:64]

    keys = [
        f"sms:cd:{phone}",
        f"sms:day:{phone}:{day}",
        f"sms:hour:{phone}:{hour}",
        f"sms:ip:hour:{ip}:{hour}",
        f"sms:ip:day:{ip}:{day}",
        f"sms:device:day:{device_id or phone}:{day}",
    ]
    args = [
        settings.sms_cooldown_seconds,
        settings.sms_daily_limit,
        90000,
        settings.sms_hourly_limit,
        3600,
        settings.sms_ip_hourly_limit,
        3600,
        settings.sms_ip_daily_limit,
        90000,
        settings.sms_device_daily_limit,
        90000,
    ]

    result = get_redis().eval(RATE_LIMIT_LUA, len(keys), *keys, *args)
    if result == 1:
        return
    if result == 0:
        raise SmsError(429, "发送过于频繁，请稍后再试")
    if result == -1:
        raise SmsError(429, "今日验证码发送次数已达上限")
    if result == -2:
        raise SmsError(429, "本小时验证码发送次数已达上限")
    if result == -3:
        raise SmsError(429, "当前网络发送过于频繁，请稍后再试")
    if result == -4:
        raise SmsError(429, "当前网络今日验证码发送次数已达上限")
    if result == -5:
        raise SmsError(429, "当前设备今日验证码发送次数已达上限")
    raise SmsError(429, "发送过于频繁，请稍后再试")


def send_code(
    db: Session,
    raw_phone: str,
    scene: str,
    request_ip: str,
    device_id: str | None,
) -> dict:
    if not settings.sms_enabled:
        raise SmsError(503, "短信服务暂不可用")
    if scene not in ALLOWED_SCENES:
        raise SmsError(400, "无效的验证码场景")
    try:
        phone = normalize_phone(raw_phone)
    except ValueError as exc:
        raise SmsError(400, str(exc)) from exc

    _rate_limit(phone, request_ip, device_id)

    now = datetime.utcnow()
    db.execute(
        update(SmsCode)
        .where(
            SmsCode.phone == phone,
            SmsCode.scene == scene,
            SmsCode.used_at.is_(None),
        )
        .values(used_at=now)
    )

    use_mock_code = (
        (settings.sms_provider or "").lower() == "mock" and settings.sms_mock_code
    )
    code = settings.sms_mock_code if use_mock_code else generate_code(settings.sms_code_length)

    record = SmsCode(
        phone=phone,
        scene=scene,
        code_hash=make_code_hash(phone, code),
        expires_at=now + timedelta(seconds=settings.sms_code_ttl_seconds),
        request_ip=request_ip[:64] if request_ip else None,
        device_id=device_id[:64] if device_id else None,
    )
    db.add(record)
    db.commit()

    provider = get_sms_provider()
    try:
        message_id = provider.send(phone, code, scene)
    except Exception as exc:
        logger.exception("sms send failed")
        record.used_at = now
        db.add(
            SmsSendLog(
                phone=phone,
                scene=scene,
                provider=settings.sms_provider,
                status="failed",
                error_code=str(exc)[:64],
                request_ip=request_ip[:64] if request_ip else None,
                device_id=device_id[:64] if device_id else None,
            )
        )
        db.commit()
        raise SmsError(502, "短信发送失败，请稍后重试") from exc

    db.add(
        SmsSendLog(
            phone=phone,
            scene=scene,
            provider=settings.sms_provider,
            provider_msg_id=message_id,
            status="sent",
            request_ip=request_ip[:64] if request_ip else None,
            device_id=device_id[:64] if device_id else None,
        )
    )
    db.commit()

    return {
        "sent": True,
        "retry_after": settings.sms_cooldown_seconds,
        "expires_in": settings.sms_code_ttl_seconds,
    }


def verify_phone_code(db: Session, raw_phone: str, scene: str, code: str) -> str:
    try:
        phone = normalize_phone(raw_phone)
    except ValueError as exc:
        raise SmsError(400, str(exc)) from exc

    now = datetime.utcnow()
    record = db.scalars(
        select(SmsCode)
        .where(SmsCode.phone == phone, SmsCode.scene == scene)
        .order_by(SmsCode.id.desc())
        .with_for_update()
    ).first()

    if record is None or record.used_at is not None or record.expires_at < now:
        raise SmsError(401, "验证码错误或已过期")

    if record.attempts >= settings.sms_max_verify_attempts:
        record.used_at = now
        db.commit()
        raise SmsError(429, "验证码尝试次数过多，请重新获取")

    if not check_code_hash(phone, code.strip(), record.code_hash):
        record.attempts += 1
        if record.attempts >= settings.sms_max_verify_attempts:
            record.used_at = now
        db.commit()
        raise SmsError(401, "验证码错误或已过期")

    record.used_at = now
    db.commit()
    return phone
