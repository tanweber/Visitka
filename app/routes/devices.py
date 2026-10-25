from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

import config
import security
from db import DevicePassword, get_session
from routes.deps import SessionUser, current_session, require_csrf

router = APIRouter()


def _render(request: Request, session: Session, current: SessionUser,
            new_secret: str | None = None, new_name: str | None = None):
    from main import templates
    devices = session.scalars(
        select(DevicePassword).where(DevicePassword.user_id == current.user.id)
        .order_by(DevicePassword.created_at.desc())
    ).all()
    response = templates.TemplateResponse(request, "devices.html", {
        "user": current.user, "csrf": current.csrf, "devices": devices,
        "new_secret": new_secret, "new_name": new_name,
        "public_url": config.public_url(request),
        "username": current.user.username,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request, session: Session = Depends(get_session),
                 current: SessionUser = Depends(current_session)):
    return _render(request, session, current)


@router.post("/devices")
def create_device(
    request: Request,
    csrf: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    name = (name or "").strip()[:64] or "Устройство"
    secret = security.new_device_secret()
    session.add(DevicePassword(
        user_id=current.user.id, name=name,
        secret_hash=security.hash_password(secret),
        created_at=dt.datetime.utcnow(),
    ))
    session.commit()
    # пароль показываем прямо в ответе: в URL он осел бы в истории и логах прокси
    return _render(request, session, current, new_secret=secret, new_name=name)


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: int,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    device = session.get(DevicePassword, device_id)
    if device and device.user_id == current.user.id:
        session.delete(device)
        session.commit()
    return RedirectResponse("/devices", status_code=303)
