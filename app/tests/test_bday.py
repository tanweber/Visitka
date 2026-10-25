import pytest

import bday
import photos
import vcard


@pytest.mark.parametrize("raw, omit, expected", [
    ("19930102", None, (1993, 1, 2)),
    ("1993-01-02", None, (1993, 1, 2)),
    ("1993-01-02T00:00:00Z", None, (1993, 1, 2)),
    ("1604-07-05", "1604", (None, 7, 5)),
    ("--0705", None, (None, 7, 5)),
    ("--07-05", None, (None, 7, 5)),
    ("1993-02-30", None, None),
    ("когда-то летом", None, None),
])
def test_parse_value(raw, omit, expected):
    assert bday.parse_value(raw, omit) == expected


@pytest.mark.parametrize("raw, expected", [
    ("01.07.1975", (1975, 7, 1)),
    ("1.7.75", (1975, 7, 1)),
    ("01.07", (None, 7, 1)),
    ("1 июля 1975", (1975, 7, 1)),
    ("01 июль 1975 г.", (1975, 7, 1)),
    ("5 мая", (None, 5, 5)),
    ("29.02", (None, 2, 29)),
])
def test_parse_input(raw, expected):
    assert bday.parse_input(raw) == expected


@pytest.mark.parametrize("raw", ["32.01.1990", "01.13.1990", "01.07.2999", "вчера"])
def test_parse_input_rejects(raw):
    with pytest.raises(bday.BdayError):
        bday.parse_input(raw)


def test_human():
    assert bday.human((1975, 7, 1)) == "01 июля 1975"
    assert bday.human((None, 12, 31)) == "31 декабря"


def test_normalize_card_v3():
    card = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:A\r\nBDAY;VALUE=DATE:19930102\r\nEND:VCARD\r\n")
    assert "BDAY:1993-01-02\r\n" in bday.normalize_card(card)
    card = ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:A\r\nBDAY;VALUE=DATE;X-APPLE-OMIT-YEAR=1604:16040705\r\nEND:VCARD\r\n")
    assert "BDAY;X-APPLE-OMIT-YEAR=1604:1604-07-05\r\n" in bday.normalize_card(card)


def test_normalize_card_v4_and_text_kept():
    card = "BEGIN:VCARD\r\nVERSION:4.0\r\nFN:A\r\nBDAY:1993-01-02\r\nEND:VCARD\r\n"
    assert "BDAY:19930102\r\n" in bday.normalize_card(card)
    card = "BEGIN:VCARD\r\nVERSION:4.0\r\nFN:A\r\nBDAY;VALUE=text:весной\r\nEND:VCARD\r\n"
    assert bday.normalize_card(card) == card


def test_build_writes_unified_bday():
    text = vcard.build({"fn": "Тест", "bday": "1 июля 1975"})
    assert "BDAY:1975-07-01" in text
    parsed = vcard.parse(text)
    assert parsed["bday"] == "01.07.1975"
    assert parsed["bday_text"] == "01 июля 1975"
    no_year = vcard.build({"fn": "Тест", "bday": "05.07"}, existing=text)
    assert "BDAY;X-APPLE-OMIT-YEAR=1604:1604-07-05" in no_year
    assert vcard.parse(no_year)["bday_text"] == "05 июля"


def test_build_rejects_bad_bday_but_keeps_untouched_unknown():
    with pytest.raises(bday.BdayError):
        vcard.build({"fn": "Тест", "bday": "32.13"})
    odd = "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:x\r\nFN:A\r\nBDAY:около 1980\r\nEND:VCARD\r\n"
    kept = vcard.build({"fn": "A", "bday": vcard.parse(odd)["bday"]}, existing=odd)
    assert "BDAY:около 1980" in kept


def _two_halves():
    from io import BytesIO
    from PIL import Image
    im = Image.new("RGB", (800, 400), (255, 0, 0))
    im.paste((0, 0, 255), (400, 0, 800, 400))
    out = BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def test_photo_crop_takes_selected_square():
    from io import BytesIO
    from PIL import Image
    right = Image.open(BytesIO(photos.normalize(_two_halves(), photos.parse_crop("0.5,0,1"))))
    r, g, b = right.convert("RGB").getpixel((256, 256))
    assert b > 200 and r < 60
    left = Image.open(BytesIO(photos.normalize(_two_halves(), photos.parse_crop("0,0,1"))))
    r, g, b = left.convert("RGB").getpixel((256, 256))
    assert r > 200 and b < 60


@pytest.mark.parametrize("raw", ["", "1,2", "a,b,c", "0,0,0", "0,0,2", "nan,0,1", "-1,0,1"])
def test_parse_crop_rejects(raw):
    assert photos.parse_crop(raw) is None


def test_search_words_and_phone_variants():
    from routes import contacts
    items = [contacts._list_item({"href": f"/a/{i}.vcf", "etag": "1", "vcard": vcard.build(f)})
             for i, f in enumerate([
                 {"fn": "Ирина Смирнова", "tel": ["+7 900 123-45-67"]},
                 {"fn": "Пётр Иванов", "org": "Меридиан", "email": ["petr@example.ru"]},
             ])]
    names = lambda q: [i["fn"] for i in contacts._search(items, q)]
    assert names("ири смир") == ["Ирина Смирнова"]
    assert names("8 900 123") == ["Ирина Смирнова"]
    assert names("9001234567") == ["Ирина Смирнова"]
    assert names("петр") == ["Пётр Иванов"]
    assert names("меридиан petr@") == ["Пётр Иванов"]
    assert names("ксения иванов") == []


def test_sort_cyrillic_then_latin_then_other():
    from routes import contacts
    names = ["Smith John", "Ёлкин Иван", "Абрамов", "123", "Яковлева", "Alex", "Елена"]
    items = [contacts._list_item({"href": f"/a/{i}.vcf", "etag": "1", "vcard": vcard.build({"fn": n})})
             for i, n in enumerate(names)]
    items.sort(key=contacts._sort_key)
    assert [i["fn"] for i in items] == ["Абрамов", "Елена", "Ёлкин Иван", "Яковлева", "Alex", "Smith John", "123"]


def test_filters_photo_and_org():
    from routes import contacts
    cards = [{"fn": "А", "org": "Ромашка"}, {"fn": "Б", "org": " ромашка "}, {"fn": "В", "org": "Acme"}, {"fn": "Г"}]
    items = [contacts._list_item({"href": f"/a/{i}.vcf", "etag": "1", "vcard": vcard.build(f)})
             for i, f in enumerate(cards)]
    items[0]["has_photo"] = True
    names = lambda **kw: [i["fn"] for i in contacts._filter(items, kw.get("q", ""), kw.get("photo", ""), kw.get("org", ""))]
    assert names(org="ромашка") == ["А", "Б"]
    assert names(org=contacts.NO_ORG) == ["Г"]
    assert names(photo="with") == ["А"]
    assert names(photo="without", org="ромашка") == ["Б"]
    assert contacts._orgs(items) == [("acme", "Acme", 1), ("ромашка", "Ромашка", 2)]
