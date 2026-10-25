import datetime as dt

from sqlalchemy import select

import security
from db import DevicePassword, User
from routes.auth import verify_dav_credentials


def _make_user(session, username="alice", secret="device-secret-0123456789"):
    user = User(username=username, password_hash=security.hash_password("web-password"),
                is_admin=False, created_at=dt.datetime.utcnow())
    session.add(user)
    session.commit()
    session.add(DevicePassword(user_id=user.id, name="Pixel",
                               secret_hash=security.hash_password(secret),
                               created_at=dt.datetime.utcnow()))
    session.commit()
    return user, secret


def test_dav_accepts_device_password(db_session):
    user, secret = _make_user(db_session)
    assert verify_dav_credentials(db_session, "alice", secret) == "alice"


def test_dav_rejects_web_password(db_session):
    _make_user(db_session, username="bob")
    assert verify_dav_credentials(db_session, "bob", "web-password") is None


def test_dav_rejects_revoked_device(db_session):
    user, secret = _make_user(db_session, username="carol")
    device = db_session.scalar(select(DevicePassword).where(DevicePassword.user_id == user.id))
    db_session.delete(device)
    db_session.commit()
    assert verify_dav_credentials(db_session, "carol", secret) is None


def test_dav_cache_respects_revoke(db_session):
    user, secret = _make_user(db_session, username="dave")
    assert verify_dav_credentials(db_session, "dave", secret) == "dave"
    assert security.dav_cache_get("dave", secret) is not None
    # второй вход — из кэша
    assert verify_dav_credentials(db_session, "dave", secret) == "dave"
    device = db_session.scalar(select(DevicePassword).where(DevicePassword.user_id == user.id))
    db_session.delete(device)
    db_session.commit()
    assert verify_dav_credentials(db_session, "dave", secret) is None


def test_dav_cache_does_not_leak_between_users(db_session):
    _, secret = _make_user(db_session, username="erin", secret="shared-secret-0123456789")
    _make_user(db_session, username="frank", secret="other-secret-0123456789")
    assert verify_dav_credentials(db_session, "erin", secret) == "erin"
    assert verify_dav_credentials(db_session, "frank", secret) is None


def test_import_retries_when_radicale_restarts(monkeypatch):
    from dav_client import DavUnavailable
    from routes import transfer

    monkeypatch.setattr(transfer, "RETRY_DELAYS", (0, 0, 0))
    calls = []

    class Flaky:
        def put_contact(self, href, card, create=False):
            calls.append(href)
            if len(calls) < 3:
                raise DavUnavailable("down")

    result = transfer._new_result(1)
    card = "BEGIN:VCARD\r\nVERSION:3.0\r\nUID:r-1\r\nFN:R\r\nEND:VCARD\r\n"
    transfer._import_cards(Flaky(), [card], False, result)
    assert result["added"] == 1 and result["failed"] == 0 and len(calls) == 3


def test_admin_password_must_be_confirmed(db_session, monkeypatch):
    import security
    from db import User
    from routes import admin
    from routes.deps import SessionUser
    monkeypatch.setattr(admin, "DavClient", lambda name: type("C", (), {"ensure_addressbook": lambda self: None})())
    boss = User(username="boss-confirm", password_hash=security.hash_password("x" * 12), is_admin=True)
    db_session.add(boss)
    db_session.commit()
    current = SessionUser(boss, "tok")

    r = admin.create_user(None, "tok", "newbie-confirm", "secret-123", "secret-124", "", db_session, current)
    assert r.headers["location"] == "/admin?error=mismatch"
    assert db_session.query(User).filter_by(username="newbie-confirm").count() == 0
    r = admin.create_user(None, "tok", "newbie-confirm", "secret-123", "secret-123", "", db_session, current)
    assert r.headers["location"] == "/admin?ok=created"

    old_hash = db_session.query(User).filter_by(username="newbie-confirm").one().password_hash
    r = admin.change_password("newbie-confirm", "tok", "another-123", "another-12", db_session, current)
    assert r.headers["location"] == "/admin?error=mismatch"
    assert db_session.query(User).filter_by(username="newbie-confirm").one().password_hash == old_hash
    r = admin.change_password("newbie-confirm", "tok", "another-123", "another-123", db_session, current)
    assert r.headers["location"] == "/admin?ok=password"


def _request(path, cookie=""):
    import config
    from starlette.requests import Request
    headers = [(b"cookie", f"{config.settings.session_cookie}={cookie}".encode())] if cookie else []
    return Request({"type": "http", "method": "GET", "path": path, "headers": headers,
                    "query_string": b"", "scheme": "http", "server": ("files.local", 8080)})


def test_default_admin_must_change_password(db_session):
    import pytest
    from fastapi import HTTPException
    import security
    from db import User
    from routes import auth
    from routes.deps import current_session
    user = User(username="first-admin", password_hash=security.hash_password("admin"),
                is_admin=True, must_change_password=True)
    db_session.add(user)
    db_session.commit()
    cookie = security.sign_session({"user": user.username, "csrf": "tok",
                                    "pwd": security.password_fingerprint(user.password_hash)})

    with pytest.raises(HTTPException) as blocked:
        current_session(_request("/", cookie), db_session)
    assert blocked.value.headers["Location"] == "/account/password"

    current = current_session(_request("/account/password", cookie), db_session)
    bad = auth.password_submit(_request("/account/password"), "tok", "wrong", "new-pass-1", "new-pass-1", db_session, current)
    assert bad.headers["location"] == "/account/password?error=current"
    same = auth.password_submit(_request("/account/password"), "tok", "admin", "admin", "admin", db_session, current)
    assert same.headers["location"] == "/account/password?error=short"
    ok = auth.password_submit(_request("/account/password"), "tok", "admin", "new-pass-1", "new-pass-1", db_session, current)
    assert ok.headers["location"] == "/?ok=password"
    db_session.refresh(user)
    assert not user.must_change_password
    assert security.verify_password("new-pass-1", user.password_hash)
    # старая cookie (с отпечатком прежнего пароля) больше не действует
    with pytest.raises(HTTPException) as old:
        current_session(_request("/", cookie), db_session)
    assert old.value.headers["Location"] == "/login"


def test_public_url_setting_wins_over_request(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "public_url", "https://contacts.example.com")
    assert config.public_url(_request("/")) == "https://contacts.example.com"
    monkeypatch.setattr(config.settings, "public_url", "")
    assert config.public_url(_request("/")) == "http://files.local:8080"
