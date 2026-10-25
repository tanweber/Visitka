from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import deque

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import config

_hasher = PasswordHasher()
_serializer = URLSafeTimedSerializer(config.settings.secret_key, salt="contacts-session")

# rate limit: (scope, ip, login) -> список отметок времени неудачных попыток
_failures: dict[tuple[str, str, str], deque[float]] = {}
_FAILURE_WINDOW = 60
_FAILURE_KEYS_MAX = 10000

# кэш успешных DAV-входов: argon2 стоит ~0.25 с, а DAVx5 шлёт десятки запросов
# за синхронизацию. Ключ — HMAC от пары логин/пароль, значение — (device_id, срок)
_dav_cache: dict[str, tuple[int, float]] = {}
DAV_CACHE_TTL = 300
_DAV_CACHE_MAX = 1000

# хэш для выравнивания времени ответа, когда пользователя нет
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
    except Exception:
        return False


def burn_time(password: str) -> None:
    """Тратит то же время, что и настоящая проверка: не выдаём, есть ли такой логин."""
    verify_password(password, _DUMMY_HASH)


def password_fingerprint(password_hash: str) -> str:
    """Отпечаток хэша пароля в сессии: смена пароля разлогинивает старые сессии."""
    return hmac.new(config.settings.secret_key.encode(), password_hash.encode(), hashlib.sha256).hexdigest()[:16]


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_device_secret() -> str:
    # 24+ случайных символов, без символов, которые ломают Basic-auth в DAVx5
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(32))


def sign_session(payload: dict) -> str:
    return _serializer.dumps(payload)


def load_session(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=config.settings.session_max_age)
    except (BadSignature, SignatureExpired):
        return None
    except Exception:
        return None


def _prune_failures(now: float) -> None:
    for key in [k for k, b in _failures.items() if not b or now - b[-1] > _FAILURE_WINDOW]:
        del _failures[key]


def too_many_failures(scope: str, ip: str, login: str, limit: int) -> bool:
    bucket = _failures.get((scope, ip, login.lower()))
    if not bucket:
        return False
    now = time.time()
    while bucket and now - bucket[0] > _FAILURE_WINDOW:
        bucket.popleft()
    return len(bucket) >= limit


def register_failure(scope: str, ip: str, login: str) -> None:
    now = time.time()
    if len(_failures) >= _FAILURE_KEYS_MAX:
        _prune_failures(now)
    _failures.setdefault((scope, ip, login.lower()), deque()).append(now)


def clear_failures(scope: str, ip: str, login: str) -> None:
    _failures.pop((scope, ip, login.lower()), None)


def _dav_key(username: str, password: str) -> str:
    msg = f"{username.lower()}\0{password}".encode()
    return hmac.new(config.settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()


def dav_cache_get(username: str, password: str) -> int | None:
    key = _dav_key(username, password)
    hit = _dav_cache.get(key)
    if not hit:
        return None
    device_id, expires = hit
    if expires < time.time():
        _dav_cache.pop(key, None)
        return None
    return device_id


def dav_cache_put(username: str, password: str, device_id: int) -> None:
    now = time.time()
    if len(_dav_cache) >= _DAV_CACHE_MAX:
        for key in [k for k, (_, exp) in _dav_cache.items() if exp < now] or list(_dav_cache):
            del _dav_cache[key]
    _dav_cache[_dav_key(username, password)] = (device_id, now + DAV_CACHE_TTL)
