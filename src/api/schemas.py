from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)
    nickname: Optional[str] = Field(default=None, max_length=64)
    nickname_prefix: Optional[str] = Field(default=None, max_length=16)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=64)


class UserOut(BaseModel):
    id: int
    username: Optional[str]
    nickname: Optional[str]
    phone: Optional[str] = None
    has_password: bool = False
    auth_type: str
    created_at: datetime


class TokenResponse(BaseModel):
    token: str
    user: UserOut


class NicknameUpdate(BaseModel):
    nickname: str


class SmsSendRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    scene: str = Field(default="login", max_length=20)
    device_id: Optional[str] = Field(default=None, max_length=64)
    captcha_token: Optional[str] = Field(default=None, max_length=256)


class SmsRegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    password: str = Field(min_length=6, max_length=64)
    nickname: Optional[str] = Field(default=None, max_length=64)
    nickname_prefix: Optional[str] = Field(default=None, max_length=16)


class SmsLoginRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class SmsResetPasswordRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    new_password: str = Field(min_length=6, max_length=64)


class SmsBindRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)


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
    source_type: str
    status: str
    progress: int
    error_msg: Optional[str] = None
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
