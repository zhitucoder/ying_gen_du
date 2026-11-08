import base64
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from src.common.config import settings
from src.worker.asr.base import ASRProvider, ASRSegment

SUBMIT_PATH = "/api/v3/auc/bigmodel/submit"
QUERY_PATH = "/api/v3/auc/bigmodel/query"

STATUS_OK = "20000000"
STATUS_PROCESSING = {"20000001", "20000002"}


class VolcengineASR(ASRProvider):
    def __init__(self) -> None:
        if not settings.asr_volcengine_api_key:
            raise RuntimeError(
                "Volcengine ASR is selected but ASR_VOLCENGINE_API_KEY is empty"
            )
        self.base_url = settings.asr_volcengine_base_url.rstrip("/")
        self.api_key = settings.asr_volcengine_api_key
        self.resource_id = settings.asr_volcengine_resource_id
        self.poll_interval = settings.asr_volcengine_poll_interval
        self.poll_timeout = settings.asr_volcengine_poll_timeout

    def _headers(self, request_id: str, submit: bool) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": request_id,
        }
        if submit:
            headers["X-Api-Sequence"] = "-1"
        return headers

    @staticmethod
    def _audio_format(path: str) -> str:
        suffix = Path(path).suffix.lower().lstrip(".")
        return suffix if suffix in {"wav", "mp3", "ogg"} else "mp3"

    def _submit(self, audio_path: str, lang: Optional[str]) -> str:
        request_id = str(uuid.uuid4())
        audio_b64 = base64.b64encode(Path(audio_path).read_bytes()).decode("utf-8")

        payload: dict[str, Any] = {
            "user": {"uid": settings.asr_volcengine_app_id or "yinggen"},
            "audio": {
                "data": audio_b64,
                "format": self._audio_format(audio_path),
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {
                "model_name": "bigmodel",
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": False,
                "enable_speaker_info": False,
                "enable_channel_split": False,
                "show_utterances": True,
                "vad_segment": False,
            },
        }
        if lang:
            payload["audio"]["language"] = lang

        response = httpx.post(
            f"{self.base_url}{SUBMIT_PATH}",
            json=payload,
            headers=self._headers(request_id, submit=True),
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        code = response.headers.get("X-Api-Status-Code", "")
        message = response.headers.get("X-Api-Message", "")
        if code != STATUS_OK:
            raise RuntimeError(
                f"Volcengine submit failed: code={code} message={message} "
                f"http={response.status_code} body={response.text[:500]}"
            )
        return request_id

    def _query_once(self, request_id: str) -> tuple[str, str, dict[str, Any]]:
        response = httpx.post(
            f"{self.base_url}{QUERY_PATH}",
            json={},
            headers=self._headers(request_id, submit=False),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        code = response.headers.get("X-Api-Status-Code", "")
        message = response.headers.get("X-Api-Message", "")
        try:
            body = response.json()
        except Exception:
            body = {}
        return code, message, body

    def _wait_result(self, request_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.poll_timeout
        while time.monotonic() < deadline:
            code, message, body = self._query_once(request_id)
            if code == STATUS_OK:
                return body
            if code in STATUS_PROCESSING:
                time.sleep(self.poll_interval)
                continue
            raise RuntimeError(
                f"Volcengine query failed: code={code} message={message} body={body}"
            )
        raise TimeoutError(f"Volcengine ASR timed out after {self.poll_timeout}s")

    @staticmethod
    def _parse(body: dict[str, Any], duration_ms: Optional[int]) -> list[ASRSegment]:
        result = body.get("result")
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict):
            result = {}

        segments: list[ASRSegment] = []
        for utterance in result.get("utterances") or []:
            text = (utterance.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                ASRSegment(
                    text=text,
                    start_ms=int(utterance.get("start_time") or 0),
                    end_ms=int(utterance.get("end_time") or 0),
                )
            )
        if segments:
            return segments

        text = (result.get("text") or "").strip()
        if text:
            return [ASRSegment(text=text, start_ms=0, end_ms=int(duration_ms or 0))]

        raise RuntimeError(f"Volcengine ASR returned no text: {body}")

    def transcribe(
        self,
        audio_path: str,
        duration_ms: Optional[int] = None,
        lang: Optional[str] = None,
    ) -> list[ASRSegment]:
        request_id = self._submit(audio_path, lang)
        body = self._wait_result(request_id)
        return self._parse(body, duration_ms)
