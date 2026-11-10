from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "yinggen-du"
    env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = (
        "mysql+pymysql://yinggen:yinggen@127.0.0.1:3307/yinggen?charset=utf8mb4"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"

    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "yinggen"
    minio_secure: bool = False
    signed_url_expire: int = 3600

    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30

    asr_provider: str = "mock"

    asr_volcengine_api_key: str = ""
    asr_volcengine_app_id: str = ""
    asr_volcengine_resource_id: str = "volc.seedasr.auc"
    asr_volcengine_base_url: str = "https://openspeech.bytedance.com"
    asr_volcengine_poll_interval: float = 2.0
    asr_volcengine_poll_timeout: int = 600

    asr_tencent_secret_id: str = ""
    asr_tencent_secret_key: str = ""
    asr_tencent_region: str = "ap-guangzhou"

    asr_aliyun_access_key_id: str = ""
    asr_aliyun_access_key_secret: str = ""
    asr_aliyun_region: str = "cn-shanghai"

    asr_iflytek_app_id: str = ""
    asr_iflytek_api_key: str = ""
    asr_iflytek_api_secret: str = ""

    sms_enabled: bool = True
    sms_provider: str = "mock"
    sms_tencent_secret_id: str = ""
    sms_tencent_secret_key: str = ""
    sms_tencent_sdk_app_id: str = ""
    sms_tencent_sign_name: str = ""
    sms_tencent_template_id: str = ""
    sms_tencent_region: str = "ap-guangzhou"
    sms_code_length: int = 6
    sms_code_ttl_seconds: int = 300
    sms_code_secret: str = "dev-sms-secret-change-me"
    sms_mock_code: str = "123456"
    sms_cooldown_seconds: int = 60
    sms_hourly_limit: int = 3
    sms_daily_limit: int = 5
    sms_ip_hourly_limit: int = 10
    sms_ip_daily_limit: int = 30
    sms_device_daily_limit: int = 5
    sms_max_verify_attempts: int = 5

    nickname_default_prefix: str = "学神"
    nickname_allowed_prefixes: str = "学神,学霸"
    nickname_sequence_width: int = 2

    media_dedup_enabled: bool = True
    media_gc_grace_seconds: int = 86400
    media_staging_prefix: str = "staging/"
    media_asset_prefix: str = "media/"

    recording_max_seconds: int = 15

    max_video_seconds: int = 1800
    max_upload_mb: int = 300
    transcode_video: bool = True
    video_retention_days: int = 30
    work_dir: str = "/tmp/yinggen"

    node_bin: str = "node"
    douyin_resolver_enabled: bool = True
    douyin_resolver_timeout: int = 180


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
