import security


def test_hash_and_verify():
    digest = security.hash_password("пароль-на-24-символа")
    assert digest.startswith("$argon2")
    assert security.verify_password("пароль-на-24-символа", digest)
    assert not security.verify_password("другой-пароль", digest)


def test_device_secret_is_long_and_unique():
    a = security.new_device_secret()
    b = security.new_device_secret()
    assert len(a) >= 24
    assert a != b
    assert all(ch.isalnum() for ch in a)


def test_session_sign_and_load():
    token = security.sign_session({"user": "alice", "csrf": "x"})
    assert security.load_session(token)["user"] == "alice"
    assert security.load_session(token + "tampered") is None


def test_rate_limit_does_not_create_keys_on_check():
    import security
    before = len(security._failures)
    assert not security.too_many_failures("web", "1.2.3.4", "nobody-here", 3)
    assert len(security._failures) == before
    for _ in range(3):
        security.register_failure("web", "1.2.3.4", "nobody-here")
    assert security.too_many_failures("web", "1.2.3.4", "nobody-here", 3)


def test_templates_render():
    """Все шаблоны собираются (синтаксис Jinja, макросы, фильтры)."""
    from main import templates
    for name in templates.env.list_templates():
        templates.env.get_template(name)


def test_localtime_filter_uses_tz():
    import datetime as dt
    import main
    assert main._local_time(dt.datetime(2026, 10, 23, 12, 5)) == "23.10.2026 15:05"
    assert main._local_time(None) == ""
