from __future__ import annotations

import base64
import datetime as dt
import binascii

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

import config
import security
from db import DevicePassword, User, get_session
from routes.deps import SessionUser, current_session, require_csrf

router = APIRouter()


def verify_dav_credentials(session: Session, username: str, password: str) -> str | None:
    """Проверяет Basic-пару по паролям устройств. Возвращает логин или None."""
    user = session.scalar(select(User).where(User.username == username.lower()))
    if not user:
        security.burn_time(password)
        return None
    # повторный запрос той же синхронизации: без argon2, но устройство должно
    # всё ещё существовать — отзыв пароля действует сразу
    cached_id = security.dav_cache_get(username, password)
    if cached_id is not None:
        device = session.get(DevicePassword, cached_id)
        if device and device.user_id == user.id:
            return user.username
    for device in session.scalars(select(DevicePassword).where(DevicePassword.user_id == user.id)).all():
        if security.verify_password(password, device.secret_hash):
            device.last_used_at = dt.datetime.utcnow()
            session.commit()
            security.dav_cache_put(username, password, device.id)
            return user.username
    return None


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    from main import templates
    csrf = security.new_csrf_token()
    response = templates.TemplateResponse(
        request, "login.html",
        {"csrf": csrf, "error": request.query_params.get("error"),
         "host": config.public_url(request).split("://", 1)[-1]},
    )
    response.set_cookie(
        config.settings.session_cookie,
        security.sign_session({"csrf": csrf, "reset": True}),
        max_age=600, httponly=True, secure=config.settings.cookie_secure, samesite="lax",
    )
    return response


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(""),
    session: Session = Depends(get_session),
):
    ip = request.client.host if request.client else "?"
    pre = security.load_session(request.cookies.get(config.settings.session_cookie, "")) or {}
    if not csrf or csrf != pre.get("csrf"):
        return RedirectResponse("/login?error=expired", status_code=303)
    username = username.strip().lower()
    if security.too_many_failures("web", ip, username, config.settings.web_rate_limit):
        return RedirectResponse("/login?error=too_many", status_code=303)
    user = session.scalar(select(User).where(User.username == username))
    if not user or not security.verify_password(password, user.password_hash):
        security.register_failure("web", ip, username)
        return RedirectResponse("/login?error=bad_credentials", status_code=303)
    security.clear_failures("web", ip, username)
    target = "/account/password" if user.must_change_password else "/"
    return _start_session(RedirectResponse(target, status_code=303), user)


def _start_session(response: Response, user: User) -> Response:
    """Cookie сессии; отпечаток пароля в ней гасит старые сессии после смены пароля."""
    response.set_cookie(
        config.settings.session_cookie,
        security.sign_session({
            "user": user.username, "csrf": security.new_csrf_token(),
            "pwd": security.password_fingerprint(user.password_hash),
        }),
        max_age=config.settings.session_max_age, httponly=True,
        secure=config.settings.cookie_secure, samesite="lax",
    )
    return response


@router.get("/account/password", response_class=HTMLResponse)
def password_form(request: Request, current: SessionUser = Depends(current_session)):
    from main import templates
    return templates.TemplateResponse(request, "account_password.html", {
        "user": current.user, "csrf": current.csrf,
        "forced": current.user.must_change_password,
        "error": request.query_params.get("error"),
    })


@router.post("/account/password")
def password_submit(
    request: Request,
    csrf: str = Form(""),
    current_password: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    user = session.get(User, current.user.id)
    ip = request.client.host if request.client else "?"
    if security.too_many_failures("web", ip, user.username, config.settings.web_rate_limit):
        return RedirectResponse("/account/password?error=too_many", status_code=303)
    if not security.verify_password(current_password, user.password_hash):
        security.register_failure("web", ip, user.username)
        return RedirectResponse("/account/password?error=current", status_code=303)
    if len(password) < 8:
        return RedirectResponse("/account/password?error=short", status_code=303)
    if password != password2:
        return RedirectResponse("/account/password?error=mismatch", status_code=303)
    if password == current_password:
        return RedirectResponse("/account/password?error=same", status_code=303)
    user.password_hash = security.hash_password(password)
    user.must_change_password = False
    session.commit()
    # прочие сессии этого пользователя гаснут, текущую выдаём заново
    return _start_session(RedirectResponse("/?ok=password", status_code=303), user)


@router.post("/logout")
def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(config.settings.session_cookie)
    return response


@router.get("/auth/dav")
def auth_dav(request: Request, session: Session = Depends(get_session)) -> Response:
    """Эндпоинт для Caddy forward_auth: проверяет Basic и отдаёт X-Remote-User."""
    header = request.headers.get("authorization", "")
    ip = request.client.host if request.client else "?"
    challenge = {"WWW-Authenticate": 'Basic realm="contacts"'}
    if not header.lower().startswith("basic "):
        return Response(status_code=401, headers=challenge)
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        username, _, password = raw.partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return Response(status_code=401, headers=challenge)
    if not username or not password:
        return Response(status_code=401, headers=challenge)
    if security.too_many_failures("dav", ip, username, config.settings.dav_rate_limit):
        return Response(status_code=401, headers=challenge)
    login = verify_dav_credentials(session, username, password)
    if not login:
        security.register_failure("dav", ip, username)
        return Response(status_code=401, headers=challenge)
    security.clear_failures("dav", ip, username)
    return Response(status_code=200, headers={"X-Remote-User": login})
