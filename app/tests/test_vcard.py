import vcard


def test_build_and_parse_roundtrip():
    text = vcard.build({
        "fn": "Иван Петров", "family": "Петров", "given": "Иван",
        "org": "Меридиан", "title": "Директор",
        "tel": ["+7 999 000-00-00"], "email": ["ivan@example.ru"],
        "note": "Позвонить после обеда", "bday": "1970-05-17", "url": "https://example.ru",
    })
    parsed = vcard.parse(text)
    assert parsed["fn"] == "Иван Петров"
    assert parsed["org"] == "Меридиан"
    assert parsed["tel"][0]["value"] == "+7 999 000-00-00"
    assert parsed["email"][0]["value"] == "ivan@example.ru"
    assert parsed["uid"]


def test_unknown_properties_survive_edit():
    original = vcard.build({"fn": "Анна", "tel": ["+7 900 111-22-33"]})
    with_x = original.replace("END:VCARD", "X-DAVX5-FOO:bar\r\nEND:VCARD")
    edited = vcard.build({"fn": "Анна Смирнова", "tel": ["+7 900 111-22-33"]}, existing=with_x)
    assert "X-DAVX5-FOO:bar" in edited
    assert vcard.parse(edited)["fn"] == "Анна Смирнова"


def test_bday_and_note_cleared():
    text = vcard.build({"fn": "Тест", "bday": "1970-05-17", "note": "заметка"})
    cleared = vcard.build({"fn": "Тест", "bday": "", "note": ""}, existing=text)
    parsed = vcard.parse(cleared)
    assert parsed["bday"] == ""
    assert parsed["note"] == ""


def test_javascript_url_is_not_safe():
    import vcard
    text = vcard.build({"fn": "X", "url": "javascript:alert(1)"})
    assert vcard.parse(text)["url_safe"] is False
    text = vcard.build({"fn": "X", "url": "https://example.org"})
    assert vcard.parse(text)["url_safe"] is True


def _jpeg(color=(200, 100, 50), size=(800, 600)):
    from io import BytesIO
    from PIL import Image
    out = BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG")
    return out.getvalue()


def test_photo_normalized_to_square_jpeg():
    from io import BytesIO
    from PIL import Image
    import photos
    data = photos.normalize(_jpeg())
    with Image.open(BytesIO(data)) as im:
        assert im.format == "JPEG" and im.size == (photos.SIZE, photos.SIZE)


def test_photo_rejects_garbage():
    import photos
    import pytest
    with pytest.raises(photos.PhotoError):
        photos.normalize(b"<svg onload=alert(1)>")


def test_photo_roundtrip_vcard3():
    import photos
    import vcard
    jpeg = photos.normalize(_jpeg())
    text = vcard.build({"fn": "Фото", "photo": jpeg})
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))
    assert vcard.parse(text)["has_photo"]
    assert vcard.photo(text) == (jpeg, "image/jpeg")
    # правка других полей сохраняет фото, удаление — убирает
    edited = vcard.build({"fn": "Фото 2"}, existing=text)
    assert vcard.photo(edited) == (jpeg, "image/jpeg")
    removed = vcard.build({"fn": "Фото 2", "photo_remove": True}, existing=edited)
    assert vcard.photo(removed) is None


def test_photo_vcard4_data_uri_survives_edit():
    import base64
    import vcard
    jpeg = _jpeg()
    b64 = base64.b64encode(jpeg).decode()
    src = f"BEGIN:VCARD\r\nVERSION:4.0\r\nUID:x1\r\nFN:Четвёртая\r\nPHOTO:data:image/jpeg;base64,{b64}\r\nEND:VCARD\r\n"
    assert vcard.photo(src) == (jpeg, "image/jpeg")
    edited = vcard.build({"fn": "Четвёртая", "org": "ООО"}, existing=src)
    assert "PHOTO:data:image/jpeg;base64," in vcard._unfold(edited)
    assert vcard.photo(edited) == (jpeg, "image/jpeg")


def test_photo_ignores_non_image_payload():
    import base64
    import vcard
    b64 = base64.b64encode(b"<svg xmlns='http://www.w3.org/2000/svg'/>").decode()
    src = f"BEGIN:VCARD\r\nVERSION:3.0\r\nFN:S\r\nPHOTO;ENCODING=b;TYPE=SVG:{b64}\r\nEND:VCARD\r\n"
    assert vcard.photo(src) is None


def test_split_cards_and_ensure_uid():
    import vcard
    text = ("BEGIN:VCARD\nVERSION:3.0\nFN:One\nUID:u-1\nEND:VCARD\n"
            "junk\r\nBEGIN:VCARD\r\nVERSION:3.0\r\nFN:Two\r\nEND:VCARD\r\n")
    cards = vcard.split_cards(text)
    assert len(cards) == 2 and all("\r\n" in c for c in cards)
    assert vcard.ensure_uid(cards[0]) == (cards[0], "u-1")
    fixed, uid = vcard.ensure_uid(cards[1])
    assert uid and vcard.card_uid(fixed) == uid
    assert vcard.parse(fixed)["fn"] == "Two"
    assert vcard.ensure_uid(cards[1])[1] == uid  # стабилен при повторном импорте
