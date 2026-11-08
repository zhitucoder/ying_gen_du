from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    openid: str = Field(min_length=1, max_length=64)
    nickname: Optional[str] = None


class TokenResponse(BaseModel):
    token: str
    user_id: int


class TaskCreateRequest(BaseModel):
    url: str = Field(min_length=1)
    title: Optional[str] = None


class TaskCreated(BaseModel):
    task_id: int
    status: str


class TaskStatus(BaseModel):
    task_id: int
    status: str
    progress: int
    error_msg: Optional[str] = None
    title: Optional[str] = None
    duration_ms: Optional[int] = None


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idx: int
    text: str
    start_ms: int
    end_ms: int
    audio_url: Optional[str] = None
    video_url: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    title: Optional[str]
    status: str
    progress: int
    duration_ms: Optional[int]
    cover_url: Optional[str]
    source_url: Optional[str]
    video_url: Optional[str] = None
    created_at: datetime


class ProjectUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class TranscriptOut(BaseModel):
    project_id: int
    title: Optional[str]
    duration_ms: Optional[int]
    segments: list[SegmentOut]


class RecordingOut(BaseModel):
    id: int
    segment_id: int
    audio_url: Optional[str]
    duration_ms: Optional[int]
    created_at: datetime
