import subprocess
import sys
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


def run(cmd: list[str], timeout: int = 1800) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "")[-2000:]
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{detail}")
    return result.stdout


def ffprobe_duration_ms(path: PathLike) -> int:
    out = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return int(float(out.strip()) * 1000)
    except ValueError:
        raise RuntimeError(f"cannot probe duration: {path}")


def has_video_stream(path: PathLike) -> bool:
    out = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    return bool(out.strip())


def has_audio_stream(path: PathLike) -> bool:
    out = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ]
    )
    return bool(out.strip())


def extract_audio(input_path: PathLike, wav_path: PathLike, mp3_path: PathLike) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(mp3_path),
        ]
    )


def slice_audio(
    wav_path: PathLike, start_ms: int, end_ms: int, out_path: PathLike
) -> None:
    start_s = max(0, start_ms) / 1000
    duration_s = max(0.05, (end_ms - start_ms) / 1000)
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_s:.3f}",
            "-i",
            str(wav_path),
            "-t",
            f"{duration_s:.3f}",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            str(out_path),
        ]
    )


def transcode_video(input_path: PathLike, out_path: PathLike) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            "scale=-2:720",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(out_path),
        ],
        timeout=3600,
    )


def download_with_ytdlp(url: str, work_dir: Path) -> Path:
    template = str(work_dir / "source.%(ext)s")
    run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--no-warnings",
            "--max-filesize",
            "300M",
            "-f",
            "bv*[vcodec^=avc1]+ba/bv*+ba/b",
            "--merge-output-format",
            "mp4",
            "-o",
            template,
            url,
        ],
        timeout=1800,
    )
    merged = work_dir / "source.mp4"
    if merged.exists():
        return merged
    files = sorted(work_dir.glob("source.*"))
    if not files:
        raise RuntimeError("yt-dlp did not produce a file")
    return files[0]


def download_direct(url: str, dest: Path) -> Path:
    import httpx

    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" in content_type or content_type.startswith("text/"):
            raise RuntimeError(
                "链接返回的是网页而不是媒体文件，可能需要登录凭证；请改用本地上传"
            )
        with dest.open("wb") as out:
            for chunk in response.iter_bytes(1024 * 1024):
                out.write(chunk)
    if dest.stat().st_size < 1024:
        raise RuntimeError("下载内容过小，不是有效的音视频文件；请改用本地上传")
    return dest


def find_media_file(directory: Path) -> Optional[Path]:
    for pattern in ("*.mp4", "*.mkv", "*.webm", "*.mov", "*.mp3", "*.m4a", "*.wav"):
        files = sorted(directory.glob(pattern))
        if files:
            return files[0]
    return None
