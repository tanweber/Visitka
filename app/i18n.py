"""Языки интерфейса. Исходные строки — русские; английский — словарь в i18n_en.py.

Язык запроса: cookie lang → DEFAULT_LANG → Accept-Language браузера.
Хранится в contextvar, поэтому _() работает и в шаблонах, и в коде (ошибки, даты).
"""
from __future__ import annotations

import contextvars
import os

from i18n_en import EN, EN_PLURAL

LANGS = ("ru", "en")
LANG_LABELS = (("ru", "Русский"), ("en", "English"))
# auto — по языку браузера; ru или en — всем по умолчанию этот язык
DEFAULT_LANG = os.environ.get("DEFAULT_LANG", "auto").strip().lower()
# языки, для которых по умолчанию показываем русский интерфейс
_RUSSIAN_LIKE = ("ru", "uk", "be", "kk")

_lang: contextvars.ContextVar[str] = contextvars.ContextVar("lang", default="ru")


def detect(cookie: str | None, accept_language: str | None) -> str:
    if cookie in LANGS:
        return cookie
    if DEFAULT_LANG in LANGS:
        return DEFAULT_LANG
    for part in (accept_language or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in _RUSSIAN_LIKE:
            return "ru"
        if code:
            return "en"
    return "en"


def set_lang(lang: str) -> None:
    _lang.set(lang if lang in LANGS else "ru")


def get_lang() -> str:
    return _lang.get()


def _(text: str, **values) -> str:
    """Перевод строки; {name} подставляются из values."""
    if get_lang() == "en":
        text = EN.get(text, text)
    return text.format(**values) if values else text


def ngettext(n: int, one: str, few: str, many: str) -> str:
    """Слово при числе: 1 контакт, 2 контакта, 5 контактов / 1 contact, 2 contacts."""
    if get_lang() == "en":
        singular, plural = EN_PLURAL.get(one, (one, many))
        return singular if n == 1 else plural
    d, h = n % 10, n % 100
    if d == 1 and h != 11:
        return one
    if 2 <= d <= 4 and not 12 <= h <= 14:
        return few
    return many
