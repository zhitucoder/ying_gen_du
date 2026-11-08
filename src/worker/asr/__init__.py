from src.common.config import settings
from src.worker.asr.base import ASRProvider, ASRSegment
from src.worker.asr.mock import MockASR
from src.worker.asr.tencent import TencentASR
from src.worker.asr.volcengine import VolcengineASR

_PROVIDERS: dict[str, type[ASRProvider]] = {
    "mock": MockASR,
    "volcengine": VolcengineASR,
    "volcano": VolcengineASR,
    "tencent": TencentASR,
}


def get_asr_provider() -> ASRProvider:
    name = (settings.asr_provider or "mock").lower()
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"unsupported ASR provider: {name} (supported: {supported})")
    return provider_cls()


__all__ = [
    "ASRProvider",
    "ASRSegment",
    "MockASR",
    "TencentASR",
    "VolcengineASR",
    "get_asr_provider",
]
