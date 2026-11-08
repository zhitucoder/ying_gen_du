from typing import Optional

from src.common.config import settings
from src.worker.asr.base import ASRProvider, ASRSegment


class TencentASR(ASRProvider):
    """Tencent Cloud recording-file ASR adapter (skeleton).

    To enable:
      1. set ASR_PROVIDER=tencent
      2. set TENCENT_SECRET_ID / TENCENT_SECRET_KEY
      3. install/implement the tencentcloud SDK call below
    """

    def __init__(self) -> None:
        if not settings.asr_tencent_secret_id or not settings.asr_tencent_secret_key:
            raise RuntimeError(
                "Tencent ASR credentials are not configured "
                "(ASR_TENCENT_SECRET_ID / ASR_TENCENT_SECRET_KEY)"
            )

    def transcribe(
        self,
        audio_path: str,
        duration_ms: Optional[int] = None,
        lang: Optional[str] = None,
    ) -> list[ASRSegment]:
        raise NotImplementedError(
            "Tencent ASR adapter is not implemented yet. "
            "Keep ASR_PROVIDER=mock until credentials and SDK integration are ready."
        )
