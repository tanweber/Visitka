from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

import security
import config
from db import User, get_session


PASSWORD_CHANGE_PATHS = {"/account/password", "/logout"}


class SessionUser:
    def __init__(self, user: User, csrf: str):
        self.user = user
        self.csrf = csrf


def current_session(request: Request, session: Session = Depends(get_session)) -> SessionUser:
    raw = request.cookies.get(config.settings.session_cookie, "")
    data = security.load_session(raw) if raw else None
    if not data or "user" not in data:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    user = session.scalar(select(User).where(User.username == data["user"]))
    if not user or data.get("pwd") != security.password_fingerprint(user.password_hash):
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    # пароль по умолчанию: пока не сменён, доступна только смена пароля
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_PATHS:
        raise HTTPException(status_code=303, headers={"Location": "/account/password"})
    return SessionUser(user, data.get("csrf", ""))


def require_csrf(token: str, current: SessionUser) -> None:
    if not token or not current.csrf or token != current.csrf:
        raise HTTPException(status_code=400, detail="CSRF-токен неверен, обновите страницу")


def require_admin(current: SessionUser) -> None:
    if not current.user.is_admin:
        raise HTTPException(status_code=403, detail="Только для администратора")
