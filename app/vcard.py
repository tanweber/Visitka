from __future__ import annotations

import base64
import re
import uuid

import vobject

import bday as bday_module

# поля, которые показывает и правит веб-интерфейс
EDITABLE = ("fn", "n", "org", "title", "tel", "email", "note", "bday", "url")
# PHOTO разбираем и пишем сами: vobject экранирует запятую в data:-URI vCard 4.0
# и при пересохранении карточки фото терялось
_PHOTO_LINE = re.compile(r"^(?:[A-Za-z0-9-]+\.)?PHOTO[;:]", re.IGNORECASE)
_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF8", "image/gif"),
)


def new_uid() -> str:
    return str(uuid.uuid4())


def _text(value) -> str:
    """vobject иногда отдаёт список (ORG, CATEGORIES) — приводим к строке.

    Для ORG vobject может вернуть посимвольный список («М», «е», …) — такие
    части склеиваем без разделителя, настоящие компоненты — через пробел.
    """
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(x) for x in value if x]
        if parts and all(len(p) <= 1 for p in parts):
            return "".join(parts)
        return " ".join(parts)
    return str(value)


def parse(vcard_text: str) -> dict:
    """Разбирает vCard в словарь для шаблонов. Неизвестные свойства не теряются."""
    card = vobject.readOne(vcard_text)
    n = getattr(card, "n", None)
    data = {
        "fn": _text(getattr(getattr(card, "fn", None), "value", "")),
        "name": " ".join(x for x in [
            getattr(n.value, "family", "") if n else "",
            getattr(n.value, "given", "") if n else "",
        ] if x) if n else "",
        "org": _text(getattr(getattr(card, "org", None), "value", "")),
        "title": _text(getattr(getattr(card, "title", None), "value", "")),
        "note": _text(getattr(getattr(card, "note", None), "value", "")),
        "url": _text(getattr(getattr(card, "url", None), "value", "")),
        "url_safe": _text(getattr(getattr(card, "url", None), "value", "")).strip().lower().startswith(("http://", "https://")),
        "uid": _text(getattr(getattr(card, "uid", None), "value", "")),
        "tel": [],
        "email": [],
        "family": _text(getattr(n.value, "family", "")) if n else "",
        "given": _text(getattr(n.value, "given", "")) if n else "",
        "raw": vcard_text,
    }
    for child in card.contents.get("tel", []):
        params = {k.upper(): v for k, v in child.params.items()}
        kind = (params.get("TYPE") or [""])[0] if isinstance(params.get("TYPE"), list) else params.get("TYPE", "")
        data["tel"].append({"value": child.value, "type": kind})
    for child in card.contents.get("email", []):
        params = {k.upper(): v for k, v in child.params.items()}
        kind = (params.get("TYPE") or [""])[0] if isinstance(params.get("TYPE"), list) else params.get("TYPE", "")
        data["email"].append({"value": child.value, "type": kind})
    data["has_photo"] = bool(_photo_lines(vcard_text))
    data["bday"], data["bday_text"] = _bday(card)
    return data


def _bday(card) -> tuple[str, str]:
    """Дата рождения: для формы (01.07.1975) и для показа (01 июля 1975)."""
    child = card.contents.get("bday", [None])[0]
    if child is None:
        return "", ""
    raw = _text(child.value).strip()
    omit = {k.upper(): v for k, v in child.params.items()}.get("X-APPLE-OMIT-YEAR")
    parts = bday_module.parse_value(raw, omit[0] if omit else None)
    if not parts:
        return raw, raw
    return bday_module.form_value(parts), bday_module.human(parts)


def _unfold(text: str) -> str:
    return re.sub(r"\r?\n[ \t]", "", text)


def _photo_lines(text: str) -> list[str]:
    return [line for line in _unfold(text).splitlines() if _PHOTO_LINE.match(line)]


def _sniff(data: bytes) -> str | None:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def photo(vcard_text: str) -> tuple[bytes, str] | None:
    """Встроенное фото карточки (vCard 3.0 ENCODING=b или 4.0 data:-URI).

    Тип определяем по сигнатуре, а не по параметрам: отдаём только растровые картинки.
    """
    for line in _photo_lines(vcard_text):
        params, _, value = line.partition(":")
        value = value.strip()
        if value.lower().startswith("data:"):
            head, _, payload = value.partition(",")
            if ";base64" not in head.lower():
                continue
        elif re.search(r"ENCODING=\"?(b|base64)\b", params, re.IGNORECASE):
            payload = value
        else:
            continue  # фото по внешней ссылке не показываем
        try:
            raw = base64.b64decode(payload, validate=False)
        except ValueError:
            continue
        mime = _sniff(raw)
        if mime:
            return raw, mime
    return None


def _fold(line: str) -> list[str]:
    chunks = [line[:75]]
    rest = line[75:]
    while rest:
        chunks.append(" " + rest[:74])
        rest = rest[74:]
    return chunks


_CARD = re.compile(r"BEGIN:VCARD\r?\n.*?END:VCARD", re.IGNORECASE | re.DOTALL)
_UID_LINE = re.compile(r"^UID[;:](.*)$", re.IGNORECASE | re.MULTILINE)


def split_cards(text: str) -> list[str]:
    """Режет файл .vcf на отдельные карточки, не трогая их содержимое."""
    cards = []
    for match in _CARD.finditer(text):
        card = match.group(0).replace("\r\n", "\n").replace("\n", "\r\n")
        cards.append(card + "\r\n")
    return cards


def card_uid(card: str) -> str:
    match = _UID_LINE.search(_unfold(card))
    if not match:
        return ""
    return match.group(1).split(":", 1)[-1].strip()


def ensure_uid(card: str) -> tuple[str, str]:
    """Добавляет UID, если его нет (Radicale без него карточку не примет)."""
    uid = card_uid(card)
    if uid:
        return card, uid
    # UID из содержимого: повторный импорт того же файла не плодит дубли
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "contacts-import:" + _unfold(card).strip()))
    end = card.upper().rindex("END:VCARD")
    return card[:end] + f"UID:{uid}\r\n" + card[end:], uid


def _photo_line(jpeg: bytes, version: str) -> str:
    b64 = base64.b64encode(jpeg).decode()
    if version.startswith("4"):
        return f"PHOTO:data:image/jpeg;base64,{b64}"
    return f"PHOTO;ENCODING=b;TYPE=JPEG:{b64}"


def _set_bday(card, value: str, version: str) -> None:
    """BDAY в едином виде; BdayError, если дату не удалось понять."""
    value = (value or "").strip()
    current = card.contents.get("bday", [])
    try:
        parts = bday_module.parse_input(value) if value else None
    except bday_module.BdayError:
        # нераспознанное значение из карточки, которое не меняли, оставляем как было
        if current and value == _bday(card)[0]:
            return
        raise
    for child in list(current):
        card.remove(child)
    if parts:
        text, params = bday_module.to_vcard(parts, version)
        child = card.add("bday")
        child.value = text
        for key, param in params.items():
            child.params[key] = [param]


def build(fields: dict, existing: str | None = None) -> str:
    """Собирает vCard. Если передана исходная карточка — сохраняет всё, чего нет в форме.

    fields["photo"] — новый JPEG, fields["photo_remove"] — убрать фото;
    иначе исходные строки PHOTO переносятся как есть.
    """
    photo_lines = _photo_lines(existing) if existing else []
    if existing:
        card = vobject.readOne(existing)
        for child in list(card.contents.get("photo", [])):
            card.remove(child)
    else:
        card = vobject.vCard()
        card.add("fn").value = ""
        card.add("uid").value = new_uid()
        card.add("n").value = vobject.vcard.Name(family="")

    def set_simple(prop: str, value: str) -> None:
        value = (value or "").strip()
        if value:
            if prop in card.contents:
                card.contents[prop][0].value = value
            else:
                card.add(prop).value = value
        elif prop in card.contents and prop != "uid":
            card.remove(card.contents[prop][0])

    set_simple("fn", fields.get("fn", ""))
    set_simple("org", fields.get("org", ""))
    set_simple("title", fields.get("title", ""))
    set_simple("note", fields.get("note", ""))
    version = card.contents["version"][0].value if "version" in card.contents else "3.0"
    _set_bday(card, fields.get("bday", ""), version)
    set_simple("url", fields.get("url", ""))

    family = (fields.get("family") or "").strip()
    given = (fields.get("given") or "").strip()
    if family or given:
        if "n" in card.contents:
            card.contents["n"][0].value = vobject.vcard.Name(family=family, given=given)
        else:
            card.add("n").value = vobject.vcard.Name(family=family, given=given)

    def set_list(prop: str, values: list[str], default_type: str) -> None:
        values = [v.strip() for v in values if v and v.strip()]
        for child in list(card.contents.get(prop, [])):
            card.remove(child)
        for value in values:
            child = card.add(prop)
            child.value = value
            child.type_param = default_type

    set_list("tel", fields.get("tel", []), "CELL")
    set_list("email", fields.get("email", []), "HOME")

    if "prodid" not in card.contents:
        card.add("prodid").value = "-//Visitka//CardDAV web UI//RU"

    if "uid" not in card.contents:
        card.add("uid").value = new_uid()

    if fields.get("photo"):
        photo_lines = [_photo_line(fields["photo"], version)]
    elif fields.get("photo_remove"):
        photo_lines = []

    text = card.serialize()
    if photo_lines:
        extra = "".join(f"{chunk}\r\n" for line in photo_lines for chunk in _fold(line))
        end = text.rindex("END:VCARD")
        text = text[:end] + extra + text[end:]
    return text
