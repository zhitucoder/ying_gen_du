import logging
import uuid

from src.api.sms.base import SMSProvider
from src.api.sms.utils import mask_phone

logger = logging.getLogger(__name__)


class MockSMS(SMSProvider):
    def send(self, phone: str, code: str, scene: str) -> str:
        logger.info(
            "mock sms phone=%s scene=%s code=%s",
            mask_phone(phone),
            scene,
            code,
        )
        return f"mock-{uuid.uuid4().hex[:12]}"
