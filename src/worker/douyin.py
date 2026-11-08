import json
import shutil
import subprocess
from pathlib import Path

from src.common.config import settings

SCRIPT = Path(__file__).parent / "resolvers" / "douyin.js"


def download_douyin(url: str, output: Path) -> dict:
    if not settings.douyin_resolver_enabled:
        raise RuntimeError("Douyin resolver is disabled")

    node = shutil.which(settings.node_bin)
    if not node:
        raise RuntimeError(f"node not found: {settings.node_bin}")

    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [node, str(SCRIPT), url, str(output)],
        capture_output=True,
        text=True,
        timeout=settings.douyin_resolver_timeout,
    )

    lines = (result.stdout or "").strip().splitlines()
    payload: dict = {}
    if lines:
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            payload = {}

    if result.returncode != 0 or not payload.get("ok"):
        detail = payload.get("error") or (result.stderr or "")[-500:] or "unknown error"
        raise RuntimeError(f"抖音解析失败：{detail}")

    return payload
