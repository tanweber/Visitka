import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789abcdef")
os.environ.setdefault("DOMAIN", "localhost")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="contacts-test-"))
os.environ["TZ"] = "Europe/Moscow"
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ.setdefault("RADICALE_URL", "http://radicale:5232")


@pytest.fixture()
def db_session():
    import db as db_module
    db_module.init_db()
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
