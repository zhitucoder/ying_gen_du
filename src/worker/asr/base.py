from dataclasses import dataclass
from typing import Optional


@dataclass
class ASRSegment:
    text: str
    start_ms: int
    end_ms: int


class ASRProvider:
    def transcribe(
        self,
        audio_path: str,
        duration_ms: Optional[int] = None,
        lang: Optional[str] = None,
    ) -> list[ASRSegment]:
        raise NotImplementedError
