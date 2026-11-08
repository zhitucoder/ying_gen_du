from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import create_token, get_current_user
from src.api.models import User
from src.api.nicknames import (
    NicknameError,
    NicknameTaken,
    create_user_with_nickname,
    normalize_nickname,
    validate_nickname,
)
from src.api.schemas import (
    LoginRequest,
    NicknameUpdate,
    RegisterRequest,
    SmsBindRequest,
    SmsLoginRequest,
    SmsRegisterRequest,
    SmsResetPasswordRequest,
    SmsSendRequest,
    TokenResponse,
    UserOut,
)
from src.api.security import hash_password, verify_password
from src.api.sms.utils import mask_phone, normalize_phone
from src.api.sms_service import SmsError, send_code, verify_phone_code

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        phone=mask_phone(user.phone) if user.phone else None,
        has_password=bool(user.password_hash),
        auth_type=user.auth_type,
        created_at=user.created_at,
    )


def _auth_response(user: User) -> TokenResponse:
    return TokenResponse(
        token=create_token(user.id, user.token_version),
        user=_user_out(user),
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _raise_sms(exc: SmsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(User).where(User.username == body.username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    try:
        user = create_user_with_nickname(
            db,
            nickname=body.nickname,
            nickname_prefix=body.nickname_prefix,
            openid=f"local:{body.username}",
            username=body.username,
            password_hash=hash_password(body.password),
            auth_type="local",
        )
    except NicknameTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NicknameError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    identifier = body.username.strip()

    try:
        phone = normalize_phone(identifier)
    except ValueError:
        phone = None

    if phone:
        user = db.scalar(select(User).where(User.phone == phone))
    else:
        user = db.scalar(select(User).where(User.username == identifier))

    if (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: NicknameUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        nickname = validate_nickname(normalize_nickname(body.nickname))
    except NicknameError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    existing = db.scalar(
        select(User.id).where(User.nickname == nickname, User.id != user.id)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="昵称已被使用")

    user.nickname = nickname
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="昵称已被使用")
    db.refresh(user)
    return _user_out(user)


@router.post("/sms/send")
def sms_send(
    body: SmsSendRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return send_code(
            db,
            body.phone,
            body.scene,
            _client_ip(request),
            body.device_id,
        )
    except SmsError as exc:
        raise _raise_sms(exc)


@router.post("/sms/register", response_model=TokenResponse)
def sms_register(
    body: SmsRegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        phone = verify_phone_code(db, body.phone, "register", body.code)
    except SmsError as exc:
        raise _raise_sms(exc)

    existing = db.scalar(select(User).where(User.phone == phone))
    if existing is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册")

    try:
        user = create_user_with_nickname(
            db,
            nickname=body.nickname,
            nickname_prefix=body.nickname_prefix,
            openid=f"phone:{phone}",
            username=None,
            password_hash=hash_password(body.password),
            phone=phone,
            phone_verified_at=datetime.utcnow(),
            auth_type="phone",
        )
    except NicknameTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except NicknameError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.refresh(user)
    return _auth_response(user)


@router.post("/sms/login", response_model=TokenResponse)
def sms_login(
    body: SmsLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        phone = verify_phone_code(db, body.phone, "login", body.code)
    except SmsError as exc:
        raise _raise_sms(exc)

    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise HTTPException(status_code=404, detail="该手机号未注册")
    return _auth_response(user)


@router.post("/sms/reset-password", response_model=TokenResponse)
def sms_reset_password(
    body: SmsResetPasswordRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        phone = verify_phone_code(db, body.phone, "reset_password", body.code)
    except SmsError as exc:
        raise _raise_sms(exc)

    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise HTTPException(status_code=404, detail="该手机号未注册")

    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.post("/sms/bind", response_model=UserOut)
def sms_bind(
    body: SmsBindRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        phone = verify_phone_code(db, body.phone, "bind", body.code)
    except SmsError as exc:
        raise _raise_sms(exc)

    other = db.scalar(
        select(User).where(User.phone == phone, User.id != user.id)
    )
    if other is not None:
        raise HTTPException(status_code=409, detail="该手机号已被其他账号绑定")

    user.phone = phone
    user.phone_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _user_out(user)
