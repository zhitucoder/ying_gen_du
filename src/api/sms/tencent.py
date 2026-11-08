import logging

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sms.v20210111 import models, sms_client

from src.api.sms.base import SMSProvider
from src.api.sms.utils import to_e164
from src.common.config import settings

logger = logging.getLogger(__name__)


class TencentSMS(SMSProvider):
    def __init__(self) -> None:
        missing = [
            name
            for name, value in {
                "SMS_TENCENT_SECRET_ID": settings.sms_tencent_secret_id,
                "SMS_TENCENT_SECRET_KEY": settings.sms_tencent_secret_key,
                "SMS_TENCENT_SDK_APP_ID": settings.sms_tencent_sdk_app_id,
                "SMS_TENCENT_SIGN_NAME": settings.sms_tencent_sign_name,
                "SMS_TENCENT_TEMPLATE_ID": settings.sms_tencent_template_id,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Tencent SMS is selected but missing config: " + ", ".join(missing)
            )

        http_profile = HttpProfile(endpoint="sms.tencentcloudapi.com", reqTimeout=5)
        client_profile = ClientProfile(httpProfile=http_profile)
        cred = credential.Credential(
            settings.sms_tencent_secret_id,
            settings.sms_tencent_secret_key,
        )
        self.client = sms_client.SmsClient(
            cred,
            settings.sms_tencent_region,
            client_profile,
        )

    def send(self, phone: str, code: str, scene: str) -> str:
        request = models.SendSmsRequest()
        request.SmsSdkAppId = settings.sms_tencent_sdk_app_id
        request.SignName = settings.sms_tencent_sign_name
        request.TemplateId = settings.sms_tencent_template_id
        request.TemplateParamSet = [code, str(settings.sms_code_ttl_seconds // 60)]
        request.PhoneNumberSet = [to_e164(phone)]

        try:
            response = self.client.SendSms(request)
        except TencentCloudSDKException as exc:
            raise RuntimeError(
                f"tencent sms error: {exc.code} {exc.message}"
            ) from exc

        if not response.SendStatusSet:
            raise RuntimeError("tencent sms returned no status")
        status = response.SendStatusSet[0]
        if status.Code != "Ok":
            raise RuntimeError(
                f"tencent sms failed: {status.Code} {status.Message}"
            )
        return status.SerialNo or ""
