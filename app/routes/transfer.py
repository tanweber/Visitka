"""Экспорт и импорт контактов в формате vCard (.vcf)."""
from __future__ import annotations

import contextvars
import datetime as dt
import logging
import secrets
import threading
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

import bday
from i18n import _, get_lang
import vcard as vcard_module
from dav_client import DavClient, DavError, DavUnavailable, href_for
from routes.contacts import UID_RE, _href
from routes.deps import SessionUser, current_session, require_csrf

router = APIRouter()
log = logging.getLogger("import")
MAX_IMPORT = 20 * 1024 * 1024
MAX_CARDS = 5000


def _vcf_response(text: str, filename: str) -> Response:
    return Response(text, media_type="text/vcard; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    })


def _decode(data: bytes) -> str:
    # старые телефоны сохраняют .vcf в cp1251
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


@router.get("/export.vcf")
def export_all(current: SessionUser = Depends(current_session)):
    items = DavClient(current.user.username).list_contacts()
    # XML-ответ REPORT приходит с LF, а vCard требует CRLF
    cards = [
        item["vcard"].strip().replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n"
        for item in items if item["vcard"].strip()
    ]
    return _vcf_response("".join(cards), f"contacts-{dt.date.today().isoformat()}.vcf")


@router.get("/contacts/{uid}/export.vcf")
def export_one(uid: str, current: SessionUser = Depends(current_session)):
    text, _ = DavClient(current.user.username).get_contact(_href(uid))
    fn = vcard_module.parse(text)["fn"]
    # ASCII-имя для старых клиентов и UTF-8 (RFC 6266) — с именем контакта
    safe = "".join(ch for ch in fn if ch.isalnum() or ch in " -_").strip() or "contact"
    response = _vcf_response(text, "contact.vcf")
    response.headers["Content-Disposition"] += f"; filename*=UTF-8''{quote(safe)}.vcf"
    return response


# слово-подтверждение очистки; принимаем любое из двух, показываем — на языке интерфейса
CLEAR_WORDS = {"ru": "УДАЛИТЬ", "en": "DELETE"}


def _clear_word() -> str:
    return CLEAR_WORDS.get(get_lang(), CLEAR_WORDS["ru"])


@router.get("/clear", response_class=HTMLResponse)
def clear_form(request: Request, current: SessionUser = Depends(current_session)):
    from main import templates
    count = len(DavClient(current.user.username).list_hrefs())
    return templates.TemplateResponse(request, "clear.html", {
        "user": current.user, "csrf": current.csrf, "count": count, "word": _clear_word(),
        "error": None,
    })


@router.post("/clear")
def clear_submit(
    request: Request,
    csrf: str = Form(""),
    confirm: str = Form(""),
    current: SessionUser = Depends(current_session),
):
    from main import templates
    require_csrf(csrf, current)
    client = DavClient(current.user.username)
    if confirm.strip().upper() not in CLEAR_WORDS.values():
        return templates.TemplateResponse(request, "clear.html", {
            "user": current.user, "csrf": current.csrf, "count": len(client.list_hrefs()),
            "word": _clear_word(), "error": _("Введите слово {word}, чтобы подтвердить.", word=_clear_word()),
        }, status_code=400)
    # удаляем карточки по одной, а не всю коллекцию: телефоны увидят обычные
    # удаления при синхронизации, а адрес адресной книги не изменится
    removed = 0
    for href in client.list_hrefs():
        client.delete_contact(href, None)
        removed += 1
    return RedirectResponse(f"/?ok=cleared&n={removed}", status_code=303)


# ===== импорт =====
# Фоновые задачи импорта живут в памяти процесса (uvicorn — один воркер):
# страница опрашивает /import/jobs/<id> и показывает «N из M».
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
JOB_TTL = 3600


def _new_result(total: int = 0) -> dict:
    return {"added": 0, "updated": 0, "skipped": 0, "failed": 0, "errors": [], "total": total}


def _read_cards(files: list[UploadFile], result: dict) -> list[str]:
    cards: list[str] = []
    budget = MAX_IMPORT
    for upload in files:
        data = upload.file.read(budget + 1)
        if len(data) > budget:
            result["errors"].append(_("Файлы больше 20 МБ — разделите импорт на части."))
            break
        budget -= len(data)
        cards.extend(vcard_module.split_cards(_decode(data)))
    if len(cards) > MAX_CARDS:
        result["errors"].append(_("За раз — не больше {n} контактов; импортированы первые {n}.", n=MAX_CARDS))
        cards = cards[:MAX_CARDS]
    result["total"] = len(cards)
    return cards


def _error(result: dict, message: str) -> None:
    result["failed"] += 1
    if len(result["errors"]) < 10:
        result["errors"].append(message)


# паузы между повторами, если Radicale недоступен: переживаем его перезапуск (~30 с)
RETRY_DELAYS = (1, 2, 4, 8, 15)


def _put(client: DavClient, href: str, card: str, create: bool) -> None:
    for delay in (*RETRY_DELAYS, None):
        try:
            client.put_contact(href, card, create=create)
            return
        except DavUnavailable:
            if delay is None:
                raise
            time.sleep(delay)


def _import_cards(client: DavClient, cards: list[str], replace: bool, result: dict) -> None:
    """Записывает карточки в Radicale; result обновляется по ходу — его читает опрос."""
    for card in cards:
        card, uid = vcard_module.ensure_uid(card)
        card = bday.normalize_card(card)
        try:
            name = vcard_module.parse(card)["fn"] or uid
        except Exception:
            _error(result, _("Не удалось разобрать карточку {uid}", uid=uid[:40]))
            continue
        # имя файла — по UID, если он годится для пути; иначе новый
        fname = uid if UID_RE.match(uid) and not uid.startswith(".") else vcard_module.new_uid()
        try:
            _put(client, href_for(fname), card, create=True)
            result["added"] += 1
        except DavError as exc:
            if str(exc) != "conflict":
                _error(result, f"«{name}»: {exc}")
            elif not replace:
                result["skipped"] += 1
            else:
                try:
                    _put(client, href_for(fname), card, create=False)
                    result["updated"] += 1
                except DavError as exc2:
                    _error(result, f"«{name}»: {exc2}")


def _run_job(job: dict, username: str, cards: list[str], replace: bool) -> None:
    try:
        _import_cards(DavClient(username), cards, replace, job["result"])
    except Exception:
        log.exception("импорт %s прерван", job["id"])
        job["result"]["errors"].append(_("Импорт прерван из-за ошибки сервера, часть контактов могла не сохраниться."))
    finally:
        job["finished"] = True


def _cleanup_jobs() -> None:
    now = time.time()
    with _jobs_lock:
        for key in [k for k, j in _jobs.items() if j["finished"] and now - j["created"] > JOB_TTL]:
            del _jobs[key]


def _job_for(job_id: str, current: SessionUser) -> dict:
    job = _jobs.get(job_id)
    if not job or job["user"] != current.user.username:
        raise HTTPException(status_code=404, detail="Задача импорта не найдена")
    return job


@router.get("/import", response_class=HTMLResponse)
def import_form(request: Request, job: str = "", current: SessionUser = Depends(current_session)):
    from main import templates
    result = None
    if job:
        found = _jobs.get(job)
        if found and found["user"] == current.user.username and found["finished"]:
            result = found["result"]
    return templates.TemplateResponse(request, "import.html", {
        "user": current.user, "csrf": current.csrf, "result": result,
    })


@router.get("/import/jobs/{job_id}")
def import_progress(job_id: str, current: SessionUser = Depends(current_session)):
    job = _job_for(job_id, current)
    r = job["result"]
    done = r["added"] + r["updated"] + r["skipped"] + r["failed"]
    return JSONResponse({"total": r["total"], "done": done, "finished": job["finished"]},
                        headers={"Cache-Control": "no-store"})


@router.post("/import", response_class=HTMLResponse)
def import_submit(
    request: Request,
    csrf: str = Form(""),
    mode: str = Form("skip"),
    files: list[UploadFile] = File(...),
    current: SessionUser = Depends(current_session),
):
    from main import templates
    require_csrf(csrf, current)
    replace = mode == "replace"
    result = _new_result()
    cards = _read_cards(files, result)

    # страница с JS: запускаем в фоне и отдаём номер задачи для опроса
    if request.headers.get("x-import-progress") == "1":
        _cleanup_jobs()
        job = {"id": secrets.token_urlsafe(12), "user": current.user.username, "result": result,
               "finished": False, "created": time.time()}
        with _jobs_lock:
            _jobs[job["id"]] = job
        # copy_context: фоновый поток пишет ошибки на языке того, кто запустил импорт
        threading.Thread(target=contextvars.copy_context().run,
                         args=(_run_job, job, current.user.username, cards, replace), daemon=True).start()
        return JSONResponse({"job": job["id"], "total": len(cards)})

    # без JS — по-старому, синхронно
    _import_cards(DavClient(current.user.username), cards, replace, result)
    return templates.TemplateResponse(request, "import.html", {
        "user": current.user, "csrf": current.csrf, "result": result,
    })
