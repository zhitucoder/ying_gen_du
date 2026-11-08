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
