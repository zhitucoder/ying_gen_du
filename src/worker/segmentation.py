import re
from typing import Optional

from src.worker.asr.base import ASRSegment

_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_PIECE_RE = re.compile(r"(?<=[，,、\s])")


def _split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENTENCE_RE.findall(text) if p.strip()]


def _chunk(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    buf = ""
    for piece in _PIECE_RE.split(text):
        if not piece:
            continue
        if buf and len(buf) + len(piece) > max_chars:
            chunks.append(buf)
            buf = piece
        else:
            buf += piece
    if buf:
        chunks.append(buf)

    result: list[str] = []
    for chunk in chunks:
        while len(chunk) > max_chars:
            result.append(chunk[:max_chars])
            chunk = chunk[max_chars:]
        if chunk:
            result.append(chunk)
    return result


def split_asr_segment(segment: ASRSegment, max_chars: int = 60) -> list[ASRSegment]:
    text = (segment.text or "").strip()
    if not text:
        return []

    pieces: list[str] = []
    for sentence in _split_sentences(text) or [text]:
        pieces.extend(_chunk(sentence, max_chars))

    total_chars = sum(len(p) for p in pieces) or 1
    duration = max(0, segment.end_ms - segment.start_ms)

    out: list[ASRSegment] = []
    consumed = 0
    for piece in pieces:
        start = segment.start_ms + int(duration * consumed / total_chars)
        consumed += len(piece)
        end = segment.start_ms + int(duration * consumed / total_chars)
        out.append(ASRSegment(text=piece, start_ms=start, end_ms=end))
    return out


def normalize_segments(
    segments: list[ASRSegment],
    pad_ms: int = 100,
    max_chars: int = 60,
    duration_ms: Optional[int] = None,
) -> list[ASRSegment]:
    expanded: list[ASRSegment] = []
    for segment in segments:
        expanded.extend(split_asr_segment(segment, max_chars=max_chars))

    cleaned: list[ASRSegment] = []
    for segment in expanded:
        start = max(0, segment.start_ms - pad_ms)
        end = segment.end_ms + pad_ms
        if duration_ms is not None:
            end = min(end, duration_ms)
        if end <= start:
            continue
        cleaned.append(ASRSegment(text=segment.text, start_ms=start, end_ms=end))

    # padding may cause neighbours to overlap; split the difference at midpoints
    for i in range(len(cleaned) - 1):
        if cleaned[i].end_ms > cleaned[i + 1].start_ms:
            mid = (cleaned[i].end_ms + cleaned[i + 1].start_ms) // 2
            cleaned[i].end_ms = mid
            cleaned[i + 1].start_ms = mid

    return [s for s in cleaned if s.end_ms > s.start_ms]
