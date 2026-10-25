"""Дни рождения: разбор всех встречающихся вариантов BDAY и запись в едином виде.

Храним так, как понимают iOS и Android (DAVx5):
  vCard 3.0 — BDAY:1975-07-01, без года — BDAY;X-APPLE-OMIT-YEAR=1604:1604-07-01
  vCard 4.0 — BDAY:19750701,   без года — BDAY:--0701
"""
from __future__ import annotations

import datetime as dt
import re

# так iOS помечает дату без года
NO_YEAR = 1604
MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря")
_MONTH_STEMS = ("янв", "фев", "мар", "апр", "ма", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")

_ISO = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})(?:T[\d:.]*(?:Z|[+-]\d{2}:?\d{2})?)?$", re.IGNORECASE)
_NO_YEAR = re.compile(r"^--(\d{2})-?(\d{2})$")
_DOTTED = re.compile(r"^(\d{1,2})[./, -](\d{1,2})(?:[./, -](\d{2}|\d{4}))?$")
_WORDS = re.compile(r"^(\d{1,2})\s+([а-яё]+)\.?(?:\s+(\d{4}))?(?:\s*г\.?)?$", re.IGNORECASE)
_LINE = re.compile(r"^((?:[A-Za-z0-9-]+\.)?BDAY)((?:;[^:\r\n]*)?):(.*(?:\r?\n[ \t].*)*)",
                   re.IGNORECASE | re.MULTILINE)
_VERSION = re.compile(r"^VERSION:\s*(\S+)", re.IGNORECASE | re.MULTILINE)

Parts = tuple  # (год или None, месяц, день)


class BdayError(ValueError):
    pass


def _checked(year: int | None, month: int, day: int) -> Parts | None:
    if year == NO_YEAR:
        year = None
    try:
        dt.date(year or 2000, month, day)  # 2000 — високосный, 29 февраля без года допустимо
    except ValueError:
        return None
    return (year, month, day)


def parse_value(value: str, omit_year: str | None = None) -> Parts | None:
    """Значение BDAY из карточки (любой из встречающихся форматов)."""
    value = (value or "").strip()
    if m := _ISO.match(value):
        year = int(m[1])
        if omit_year and omit_year.strip() == m[1]:
            year = None
        return _checked(year, int(m[2]), int(m[3]))
    if m := _NO_YEAR.match(value):
        return _checked(None, int(m[1]), int(m[2]))
    return None


def parse_input(value: str) -> Parts:
    """То, что ввёл человек: 01.07.1975, 1.7, 1975-07-01, 1 июля 1975."""
    value = " ".join((value or "").split())
    parts = parse_value(value)
    if parts:
        return parts
    if m := _DOTTED.match(value):
        year = m[3] and int(m[3])
        if year and year < 100:
            # 75 → 1975, 05 → 2005
            year += 2000 if year <= dt.date.today().year % 100 else 1900
        parts = _checked(year or None, int(m[2]), int(m[1]))
    elif m := _WORDS.match(value):
        word = m[2].lower()
        month = next((i for i, stem in enumerate(_MONTH_STEMS, 1) if word.startswith(stem)), None)
        parts = month and _checked(int(m[3]) if m[3] else None, month, int(m[1]))
    if not parts:
        raise BdayError("Дата рождения: не понял дату. Пример: 01.07.1975 или 01.07 без года.")
    if parts[0] and not 1800 <= parts[0] <= dt.date.today().year:
        raise BdayError("Дата рождения: проверьте год.")
    return parts


def to_vcard(parts: Parts, version: str = "3.0") -> tuple[str, dict[str, str]]:
    """Значение и параметры BDAY в едином виде."""
    year, month, day = parts
    if version.startswith("4"):
        return (f"{year:04d}{month:02d}{day:02d}" if year else f"--{month:02d}{day:02d}"), {}
    if year:
        return f"{year:04d}-{month:02d}-{day:02d}", {}
    return f"{NO_YEAR}-{month:02d}-{day:02d}", {"X-APPLE-OMIT-YEAR": str(NO_YEAR)}


def human(parts: Parts) -> str:
    """01 июля 1975 (или 01 июля, если год неизвестен)."""
    year, month, day = parts
    text = f"{day:02d} {MONTHS[month - 1]}"
    return f"{text} {year}" if year else text


def form_value(parts: Parts) -> str:
    year, month, day = parts
    return f"{day:02d}.{month:02d}.{year}" if year else f"{day:02d}.{month:02d}"


def _omit_year(params: str) -> str | None:
    m = re.search(r"X-APPLE-OMIT-YEAR=\"?(\d+)", params, re.IGNORECASE)
    return m[1] if m else None


def normalize_card(card: str) -> str:
    """Переписывает строки BDAY карточки в единый вид; остальное не трогает.

    Нераспознанные значения (например, VALUE=text в vCard 4.0) оставляем как есть.
    """
    version_match = _VERSION.search(card)
    version = version_match[1] if version_match else "3.0"
    newline = "\r\n" if "\r\n" in card else "\n"

    def fix(m: re.Match) -> str:
        params = m[2]
        if re.search(r"VALUE=\"?text", params, re.IGNORECASE):
            return m[0]
        parts = parse_value(re.sub(r"\r?\n[ \t]", "", m[3]), _omit_year(params))
        if not parts:
            return m[0]
        value, extra = to_vcard(parts, version)
        # VALUE=DATE и прежний X-APPLE-OMIT-YEAR выкидываем, прочие параметры сохраняем
        kept = [p for p in params.split(";")[1:]
                if p and not re.match(r"(VALUE|X-APPLE-OMIT-YEAR)=", p, re.IGNORECASE)]
        kept += [f"{k}={v}" for k, v in extra.items()]
        return m[1] + "".join(f";{p}" for p in kept) + ":" + value

    return _LINE.sub(fix, card).replace("\r\n", "\n").replace("\n", newline)
