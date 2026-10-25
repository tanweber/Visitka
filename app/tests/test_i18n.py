import glob
import os
import re

import i18n
from i18n_en import EN

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALL = re.compile(r"""\b_\(\s*(["'])((?:(?!\1).)*)\1""")
JS_CALL = re.compile(r"""\bt\(\s*"([^"]*)\"""")
# подписи, которые попадают в _() через переменную
INDIRECT = ["Все", "С фото", "Без фото", "Как в системе", "Светлая", "Тёмная",
            "мобильный", "домашний", "рабочий", "основной", "факс", "пейджер", "другой"]


def _python_keys():
    keys = set(INDIRECT)
    files = glob.glob(f"{APP}/templates/*.html") + glob.glob(f"{APP}/*.py") + glob.glob(f"{APP}/routes/*.py")
    for path in files:
        keys.update(m.group(2) for m in CALL.finditer(open(path, encoding="utf-8").read()))
    return keys


def test_every_server_string_has_english():
    missing = sorted(k for k in _python_keys() if re.search("[А-Яа-яЁё]", k) and k not in EN)
    assert not missing, f"нет перевода: {missing}"


def test_every_js_string_has_english():
    source = open(f"{APP}/static/app.js", encoding="utf-8").read()
    table = source[source.index("const EN = {"):source.index("};", source.index("const EN = {"))]
    defined = set(re.findall(r'^\s*"([^"]+)":', table, re.MULTILINE))
    used = {k for k in JS_CALL.findall(source) if re.search("[А-Яа-яЁё]", k)}
    assert not sorted(used - defined), f"нет перевода в app.js: {sorted(used - defined)}"


def test_translation_and_placeholders():
    i18n.set_lang("en")
    try:
        assert i18n._("Найдено {n} из {total}", n=3, total=10) == "Found 3 of 10"
        assert i18n.ngettext(1, "контакт", "контакта", "контактов") == "contact"
        assert i18n.ngettext(5, "контакт", "контакта", "контактов") == "contacts"
    finally:
        i18n.set_lang("ru")
    assert i18n._("Найдено {n} из {total}", n=3, total=10) == "Найдено 3 из 10"
    assert [i18n.ngettext(n, "контакт", "контакта", "контактов") for n in (1, 3, 5, 11, 21)] == \
        ["контакт", "контакта", "контактов", "контактов", "контакт"]


def test_placeholders_match_in_translations():
    for ru, en in EN.items():
        assert set(re.findall(r"\{(\w+)\}", ru)) == set(re.findall(r"\{(\w+)\}", en)), ru


def test_detect_language():
    assert i18n.detect("en", "ru-RU") == "en"
    assert i18n.detect(None, "ru-RU,ru;q=0.9,en;q=0.8") == "ru"
    assert i18n.detect(None, "de-DE,de;q=0.9") == "en"
    assert i18n.detect("xx", "uk-UA") == "ru"


def test_birthday_in_english():
    import bday
    i18n.set_lang("en")
    try:
        assert bday.human((1975, 7, 1)) == "1 July 1975"
        assert bday.form_value((1975, 7, 1)) == "1975-07-01"
        assert bday.parse_input("July 1, 1975") == (1975, 7, 1)
        assert bday.parse_input("1 July") == (None, 7, 1)
        assert bday.parse_input(bday.form_value((None, 7, 1))) == (None, 7, 1)
    finally:
        i18n.set_lang("ru")
