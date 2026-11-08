from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import create_token
from src.api.models import User
from src.api.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.openid == body.openid))
    if user is None:
        user = User(openid=body.openid, nickname=body.nickname)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif body.nickname and user.nickname != body.nickname:
        user.nickname = body.nickname
        db.commit()

    return TokenResponse(token=create_token(user.id), user_id=user.id)
