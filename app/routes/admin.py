from __future__ import annotations

import datetime as dt
import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import security
from dav_client import DavClient, DavError
from db import DevicePassword, User, get_session
from routes.deps import SessionUser, current_session, require_admin, require_csrf

router = APIRouter()
USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,32}$")


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, session: Session = Depends(get_session),
               current: SessionUser = Depends(current_session)):
    from main import templates
    require_admin(current)
    users = session.scalars(select(User).order_by(User.username)).all()
    return templates.TemplateResponse(request, "admin.html", {
        "user": current.user, "csrf": current.csrf, "users": users,
        "ok": request.query_params.get("ok"),
        "error": request.query_params.get("error"),
    })


@router.post("/admin/users")
def create_user(
    request: Request,
    csrf: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    is_admin: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    require_admin(current)
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username):
        return RedirectResponse("/admin?error=username", status_code=303)
    if len(password or "") < 8:
        return RedirectResponse("/admin?error=password", status_code=303)
    if password != password2:
        return RedirectResponse("/admin?error=mismatch", status_code=303)
    if session.scalar(select(User).where(User.username == username)):
        return RedirectResponse("/admin?error=exists", status_code=303)
    user = User(username=username, password_hash=security.hash_password(password),
                is_admin=bool(is_admin), created_at=dt.datetime.utcnow())
    session.add(user)
    session.commit()
    try:
        DavClient(username).ensure_addressbook()
    except DavError:
        pass
    return RedirectResponse("/admin?ok=created", status_code=303)


@router.post("/admin/users/{username}/password")
def change_password(
    username: str,
    csrf: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    require_admin(current)
    user = session.scalar(select(User).where(User.username == username.lower()))
    if not user or len(password or "") < 8:
        return RedirectResponse("/admin?error=password", status_code=303)
    if password != password2:
        return RedirectResponse("/admin?error=mismatch", status_code=303)
    user.password_hash = security.hash_password(password)
    session.commit()
    return RedirectResponse("/admin?ok=password", status_code=303)


@router.post("/admin/users/{username}/delete")
def delete_user(
    username: str,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    require_admin(current)
    username = username.lower()
    if username == current.user.username:
        return RedirectResponse("/admin?error=self", status_code=303)
    user = session.scalar(select(User).where(User.username == username))
    if user:
        # сначала коллекция в Radicale, потом записи в базе
        try:
            DavClient(username).delete_collection()
        except DavError:
            pass
        session.delete(user)
        session.commit()
    return RedirectResponse("/admin?ok=deleted", status_code=303)
