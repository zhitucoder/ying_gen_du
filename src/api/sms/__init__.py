from src.api.sms.base import SMSProvider
from src.api.sms.mock import MockSMS
from src.common.config import settings


def get_sms_provider() -> SMSProvider:
    name = (settings.sms_provider or "mock").lower()
    if name == "mock":
        return MockSMS()
    if name == "tencent":
        from src.api.sms.tencent import TencentSMS

        return TencentSMS()
    raise ValueError(f"unsupported SMS provider: {name}")


__all__ = ["SMSProvider", "MockSMS", "get_sms_provider"]
