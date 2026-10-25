from __future__ import annotations

import datetime as dt
import logging
import threading
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

import config
import i18n
import security
from dav_client import DavClient, DavError
from db import DevicePassword, SessionLocal, User, get_session, init_db
from routes import admin, auth, contacts, devices, transfer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

templates = Jinja2Templates(directory="templates")
# типы TEL/EMAIL из vCard; подписи переводит _()
TYPE_LABELS = {
    "cell": "мобильный", "mobile": "мобильный", "iphone": "iPhone", "home": "домашний",
    "work": "рабочий", "main": "основной", "voice": "телефон", "fax": "факс",
    "pager": "пейджер", "internet": "e-mail", "pref": "основной", "other": "другой",
}
def _local_time(value: dt.datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """UTC из базы → местное время из TZ."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(config.timezone).strftime(fmt)


templates.env.filters["localtime"] = _local_time
templates.env.filters["type_label"] = lambda value, default="": i18n._(
    TYPE_LABELS.get((value or "").lower(), (value or "").lower() or default))
templates.env.globals["_"] = i18n._
templates.env.globals["ngettext"] = i18n.ngettext
templates.env.globals["current_lang"] = i18n.get_lang
templates.env.globals["LANG_LABELS"] = i18n.LANG_LABELS
templates.env.globals["ADDRESSBOOK_NAME"] = config.settings.addressbook_name
templates.env.globals["THEMES"] = [
    ("auto", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная"),
    ("nord", "Nord"), ("forest", "Forest"),
]
app = FastAPI(title="Visitka", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def language(request: Request, call_next):
    """Язык интерфейса на время запроса (contextvar доходит и до sync-обработчиков)."""
    i18n.set_lang(i18n.detect(request.cookies.get("lang"), request.headers.get("accept-language")))
    response = await call_next(request)
    response.headers.setdefault("Content-Language", i18n.get_lang())
    response.headers.setdefault("Vary", "Cookie, Accept-Language")
    return response

app.include_router(auth.router)
app.include_router(contacts.router)
app.include_router(devices.router)
app.include_router(admin.router)
app.include_router(transfer.router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with SessionLocal() as session:
        users = session.scalars(select(User)).all()
        if not users:
            username = config.settings.admin_username
            default = config.settings.admin_password == config.DEFAULT_ADMIN_PASSWORD
            session.add(User(
                username=username,
                password_hash=security.hash_password(config.settings.admin_password),
                is_admin=True,
                must_change_password=default,
                created_at=dt.datetime.utcnow(),
            ))
            session.commit()
            log.info("создан администратор %s", username)
            if default:
                log.warning("пароль администратора по умолчанию (%s/%s) — сменить при первом входе",
                            username, config.DEFAULT_ADMIN_PASSWORD)
        for user in session.scalars(select(User)).all():
            try:
                DavClient(user.username).ensure_addressbook()
            except DavError as exc:
                log.warning("адресная книга %s: %s", user.username, exc)
        names = [user.username for user in session.scalars(select(User)).all()]
    # первый разбор всех карточек занимает секунды — делаем его в фоне, а не на первом заходе
    threading.Thread(target=_warm_lists, args=(names,), daemon=True).start()


def _warm_lists(names: list[str]) -> None:
    for name in names:
        try:
            contacts.list_items(name)
        except DavError as exc:
            log.warning("прогрев списка %s: %s", name, exc)


THEMES = ("auto", "light", "dark", "nord", "forest")


@app.get("/theme/{name}")
def set_theme(name: str, request: Request):
    """Запасной путь без JS: ставит cookie темы и возвращает на ту же страницу."""
    back = urlsplit(request.headers.get("referer", "")).path or "/"
    if not back.startswith("/") or back.startswith("//") or back.startswith("/theme/"):
        back = "/"
    response = RedirectResponse(back, status_code=303)
    if name in THEMES:
        response.set_cookie("theme", name, max_age=60 * 60 * 24 * 365, samesite="lax",
                            secure=config.settings.cookie_secure)
    return response


@app.get("/lang/{code}")
def set_language(code: str, request: Request):
    """Переключатель языка: cookie lang и назад на ту же страницу."""
    back = urlsplit(request.headers.get("referer", "")).path or "/"
    if not back.startswith("/") or back.startswith("//") or back.startswith("/lang/"):
        back = "/"
    response = RedirectResponse(back, status_code=303)
    if code in i18n.LANGS:
        response.set_cookie("lang", code, max_age=60 * 60 * 24 * 365, samesite="lax",
                            secure=config.settings.cookie_secure)
    return response


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.exception_handler(DavError)
def dav_error_handler(request: Request, exc: DavError):
    return templates.TemplateResponse(
        request, "error.html",
        {"message": str(exc), "user": None}, status_code=502,
    )
