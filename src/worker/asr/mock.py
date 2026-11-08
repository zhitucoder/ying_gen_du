from typing import Optional

from src.worker.asr.base import ASRProvider, ASRSegment


class MockASR(ASRProvider):
    """Placeholder ASR used until a cloud provider is configured.

    It splits the whole duration into ~4s chunks so the rest of the pipeline
    (segmentation, slicing, playback) can be exercised end to end.
    """

    def transcribe(
        self,
        audio_path: str,
        duration_ms: Optional[int] = None,
        lang: Optional[str] = None,
    ) -> list[ASRSegment]:
        duration = duration_ms or 12000
        if duration <= 0:
            duration = 1000

        chunk = 4000
        segments: list[ASRSegment] = []
        start = 0
        idx = 1
        while start < duration:
            end = min(duration, start + chunk)
            segments.append(
                ASRSegment(
                    text=f"这是第 {idx} 句 Mock 示例文本，用于验证分句与切片流程。",
                    start_ms=start,
                    end_ms=end,
                )
            )
            start = end
            idx += 1

        return segments or [ASRSegment(text="Mock 示例文本。", start_ms=0, end_ms=duration)]
