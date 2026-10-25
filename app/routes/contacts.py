from __future__ import annotations

import itertools
import re
import threading
import zlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

import bday
import photos
import vcard as vcard_module
from dav_client import DavClient, DavError, href_for
from routes.deps import SessionUser, current_session, require_csrf
from i18n import _

router = APIRouter()
# имя файла карточки: клиенты пишут разное, но без разделителей пути и URL
UID_RE = re.compile(r"^[^/\\?#\s\x00-\x1f]{1,255}$")
AVATAR_TONES = 8
# разобранные карточки для списка: {пользователь: {href: (etag, item)}}.
# Полный разбор 300+ карточек с фото — секунды; сверка etag — доли секунды.
_list_cache: dict[str, dict[str, tuple[str, dict]]] = {}
_list_lock = threading.Lock()


def _href(uid: str) -> str:
    if not UID_RE.match(uid) or uid.startswith("."):
        raise HTTPException(status_code=404, detail=_("Контакт не найден"))
    return href_for(uid)


def _decorate(item: dict) -> dict:
    """Поля для отрисовки: буква раздела, инициалы и цвет аватара."""
    fn = (item.get("fn") or "").strip()
    first = fn[:1].upper()
    # Ё — в разделе Е, как в телефонах; иначе сортировка с ё→е разорвала бы раздел
    item["letter"] = ("Е" if first == "Ё" else first) if first.isalpha() else "#"
    given, family = (item.get("given") or "").strip(), (item.get("family") or "").strip()
    if given or family:
        initials = (given[:1] + family[:1])
    else:
        words = fn.split()
        initials = "".join(w[:1] for w in words[:2])
    item["initials"] = initials.upper() or "?"
    item["tone"] = zlib.crc32(fn.encode()) % AVATAR_TONES
    return item


def _search_text(item: dict) -> tuple[str, str]:
    """Строка для поиска (имя, организация, e-mail) и цифры телефонов."""
    text = " ".join([item.get("fn", ""), item.get("org", ""), item.get("title", ""),
                     " ".join(e["value"] for e in item.get("email", []))])
    digits = " ".join(re.sub(r"\D", "", t["value"]) for t in item.get("tel", []))
    return text.lower().replace("ё", "е"), digits


def _list_item(raw: dict) -> dict | None:
    try:
        parsed = vcard_module.parse(raw["vcard"])
    except Exception:
        return None
    parsed.pop("raw", None)
    parsed["href"] = raw["href"]
    parsed["etag"] = raw["etag"]
    # UID внутри карточки может не совпадать с именем файла — ссылки в вебе
    # строим по имени файла, иначе карточка отдаёт 404
    fname = raw["href"].rstrip("/").rsplit("/", 1)[-1]
    parsed["uid"] = fname[:-4] if fname.endswith(".vcf") else fname
    parsed["search"], parsed["digits"] = _search_text(parsed)
    parsed["org_key"] = " ".join((parsed.get("org") or "").split()).lower()
    return _decorate(parsed)


def list_items(username: str) -> list[dict]:
    """Все контакты пользователя; заново разбираются только изменённые карточки."""
    client = DavClient(username)
    etags = client.list_etags()
    with _list_lock:
        cached = dict(_list_cache.get(username, {}))
    stale = [href for href, etag in etags.items() if href not in cached or cached[href][0] != etag]
    for raw in client.fetch(stale):
        cached[raw["href"]] = (raw["etag"], _list_item(raw))
    fresh = {href: cached[href] for href in etags if href in cached}
    with _list_lock:
        _list_cache[username] = fresh
    items = [item for _, item in fresh.values() if item]
    items.sort(key=_sort_key)
    return items


def _sort_key(item: dict) -> tuple:
    """Как в телефоне с русским языком: сначала А–Я, потом A–Z, в конце «#»."""
    letter = item["letter"]
    rank = 2 if letter == "#" else (0 if "А" <= letter <= "Я" else 1)
    return rank, (item.get("fn") or "").lower().replace("ё", "е")


def _word_matches(word: str, item: dict) -> bool:
    if word in item["search"]:
        return True
    digits = re.sub(r"[\s()+.-]", "", word)
    if len(digits) < 2 or not digits.isdigit():
        return False
    # 8 900… и +7 900… — один и тот же номер
    variants = {digits, "7" + digits[1:] if digits[0] == "8" else digits}
    return any(v in item["digits"] for v in variants)


def _search(items: list[dict], query: str) -> list[dict]:
    """Каждое слово запроса должно найтись; та же логика — в app.js для поиска на лету."""
    query = query.lower().replace("ё", "е").strip()
    # номер, набранный с пробелами («8 900 123»), ищем целиком, а не по словам
    words = [query] if re.fullmatch(r"[\d\s()+.-]+", query) else query.split()
    if not words:
        return items
    return [item for item in items if all(_word_matches(w, item) for w in words)]


class ContactForm:
    """Поля формы контакта (общие для создания и правки)."""

    def __init__(
        self,
        csrf: str = Form(""),
        etag: str = Form(""),
        fn: str = Form(""),
        family: str = Form(""),
        given: str = Form(""),
        org: str = Form(""),
        title: str = Form(""),
        tel: str = Form(""),
        email: str = Form(""),
        note: str = Form(""),
        bday: str = Form(""),
        url: str = Form(""),
        photo: UploadFile | None = File(None),
        photo_remove: str = Form(""),
        photo_crop: str = Form(""),
    ):
        self.csrf, self.etag = csrf, etag
        self.values = {
            "fn": fn or " ".join(x for x in (given, family) if x),
            "family": family, "given": given, "org": org, "title": title,
            "tel": tel.splitlines(), "email": email.splitlines(),
            "note": note, "bday": bday, "url": url,
        }
        self.upload = photo if photo and photo.filename else None
        self.photo_remove = bool(photo_remove)
        self.photo_crop = photos.parse_crop(photo_crop)

    def fields(self) -> dict:
        """Поля для vcard.build; фото приводится к JPEG 512×512 (PhotoError при сбое)."""
        fields = dict(self.values, photo_remove=self.photo_remove)
        if self.upload:
            data = self.upload.file.read(photos.MAX_UPLOAD + 1)
            fields["photo"] = photos.normalize(data, self.photo_crop)
        return fields

    def as_contact(self, has_photo: bool = False) -> dict:
        """Введённые значения — чтобы вернуть форму с ошибкой без потери данных."""
        contact = dict(self.values, etag=self.etag, has_photo=has_photo)
        contact["tel"] = [{"value": v} for v in self.values["tel"] if v.strip()]
        contact["email"] = [{"value": v} for v in self.values["email"] if v.strip()]
        return contact


def _form_error(exc: Exception) -> str:
    return _("Фото: {error}.", error=exc) if isinstance(exc, photos.PhotoError) else str(exc)


def _form(request: Request, current: SessionUser, mode: str, contact: dict,
          uid: str = "", error: str | None = None, status_code: int = 200):
    from main import templates
    return templates.TemplateResponse(request, "contact_form.html", {
        "user": current.user, "csrf": current.csrf, "mode": mode,
        "contact": _decorate(contact), "uid": uid, "error": error,
    }, status_code=status_code)


NO_ORG = "-"  # значение фильтра «без организации»


def _filter(items: list[dict], q: str, photo: str, org: str) -> list[dict]:
    """Поиск + фильтры; та же логика — в app.js."""
    result = _search(items, q)
    if photo in ("with", "without"):
        result = [i for i in result if i["has_photo"] == (photo == "with")]
    if org:
        key = "" if org == NO_ORG else org
        result = [i for i in result if i["org_key"] == key]
    return result


def _orgs(items: list[dict]) -> list[tuple[str, str, int]]:
    """Организации для фильтра: (ключ, название, сколько контактов)."""
    found: dict[str, list] = {}
    for item in items:
        if item["org_key"]:
            found.setdefault(item["org_key"], [" ".join(item["org"].split()), 0])[1] += 1
    return sorted(((k, label, n) for k, (label, n) in found.items()), key=lambda x: x[1].lower())


@router.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", photo: str = "", org: str = "",
          current: SessionUser = Depends(current_session)):
    from main import templates
    items = list_items(current.user.username)
    total = len(items)
    photo = photo if photo in ("with", "without") else ""
    org = org.strip().lower()
    # в разметку идут все контакты: поиск и фильтры в браузере работают без запросов,
    # а ?q=…&photo=…&org=… (без JS) лишь скрывают лишние строки
    filtering = bool(q.strip() or photo or org)
    matched = {item["href"] for item in _filter(items, q, photo, org)} if filtering else set()
    with_photo = sum(1 for i in items if i["has_photo"])
    return templates.TemplateResponse(request, "index.html", {
        "user": current.user, "csrf": current.csrf, "contacts": items,
        # группируем здесь: groupby в Jinja пересортировал бы буквы (латиница раньше кириллицы)
        "groups": [(letter, list(group)) for letter, group in itertools.groupby(items, key=lambda x: x["letter"])],
        "matched": matched, "q": q, "total": total, "filtering": filtering,
        "photo": photo, "org": org, "orgs": _orgs(items), "no_org": NO_ORG,
        "with_photo": with_photo, "without_org": sum(1 for i in items if not i["org_key"]), "ok": request.query_params.get("ok"),
        "removed": request.query_params.get("n", ""),
    })


@router.get("/contacts/new", response_class=HTMLResponse)
def new_form(request: Request, current: SessionUser = Depends(current_session)):
    return _form(request, current, "new", {})


@router.post("/contacts/new")
def create_contact(
    request: Request,
    form: ContactForm = Depends(),
    current: SessionUser = Depends(current_session),
):
    require_csrf(form.csrf, current)
    try:
        text = vcard_module.build(form.fields())
    except (photos.PhotoError, bday.BdayError) as exc:
        return _form(request, current, "new", form.as_contact(), error=_form_error(exc), status_code=400)
    uid = vcard_module.parse(text)["uid"]
    if not UID_RE.match(uid or "") or uid.startswith("."):
        uid = vcard_module.new_uid()
    client = DavClient(current.user.username)
    client.put_contact(href_for(uid), text, create=True)
    return RedirectResponse(f"/contacts/{uid}", status_code=303)


@router.get("/contacts/{uid}", response_class=HTMLResponse)
def view_contact(uid: str, request: Request, current: SessionUser = Depends(current_session)):
    from main import templates
    client = DavClient(current.user.username)
    text, etag = client.get_contact(_href(uid))
    parsed = _decorate(vcard_module.parse(text))
    parsed["etag"] = etag
    return templates.TemplateResponse(request, "contact_detail.html", {
        "user": current.user, "csrf": current.csrf, "contact": parsed, "uid": uid,
        "ok": request.query_params.get("ok"),
    })


@router.get("/contacts/{uid}/photo")
def contact_photo(uid: str, current: SessionUser = Depends(current_session)):
    client = DavClient(current.user.username)
    text, _ = client.get_contact(_href(uid))
    found = vcard_module.photo(text)
    if not found:
        raise HTTPException(status_code=404)
    data, mime = found
    # ссылки на фото содержат etag карточки (?v=…), поэтому кэш можно держать долго
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=2592000"})


@router.get("/contacts/{uid}/edit", response_class=HTMLResponse)
def edit_form(uid: str, request: Request, current: SessionUser = Depends(current_session)):
    client = DavClient(current.user.username)
    text, etag = client.get_contact(_href(uid))
    parsed = vcard_module.parse(text)
    parsed["etag"] = etag
    error = None
    if request.query_params.get("error") == "conflict":
        error = _("Контакт изменился на другом устройстве. Перезагрузите карточку и повторите правку.")
    return _form(request, current, "edit", parsed, uid=uid, error=error)


@router.post("/contacts/{uid}/edit")
def save_contact(
    uid: str,
    request: Request,
    form: ContactForm = Depends(),
    current: SessionUser = Depends(current_session),
):
    require_csrf(form.csrf, current)
    client = DavClient(current.user.username)
    existing, current_etag = client.get_contact(_href(uid))
    if form.etag and current_etag and form.etag != current_etag:
        return RedirectResponse(f"/contacts/{uid}/edit?error=conflict", status_code=303)
    try:
        text = vcard_module.build(form.fields(), existing=existing)
    except (photos.PhotoError, bday.BdayError) as exc:
        contact = form.as_contact(has_photo=bool(vcard_module.photo(existing)))
        contact["etag"] = current_etag
        return _form(request, current, "edit", contact, uid=uid, error=_form_error(exc), status_code=400)
    try:
        client.put_contact(_href(uid), text, etag=current_etag or None)
    except DavError as exc:
        if "conflict" in str(exc):
            return RedirectResponse(f"/contacts/{uid}/edit?error=conflict", status_code=303)
        raise
    return RedirectResponse(f"/contacts/{uid}?ok=1", status_code=303)


@router.post("/contacts/{uid}/delete")
def delete_contact(
    uid: str,
    csrf: str = Form(""),
    etag: str = Form(""),
    current: SessionUser = Depends(current_session),
):
    require_csrf(csrf, current)
    client = DavClient(current.user.username)
    client.delete_contact(_href(uid), etag or None)
    return RedirectResponse("/?ok=deleted", status_code=303)
