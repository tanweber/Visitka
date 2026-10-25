import os
import secrets
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# пароль первого администратора по умолчанию: работает только до первого входа,
# затем приложение требует сменить его
DEFAULT_ADMIN_PASSWORD = "admin"


def _bool(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip() in {"1", "true", "yes", "on"}


def _public_url() -> str:
    """Внешний адрес сервиса: PUBLIC_URL, иначе https://DOMAIN; пусто — берём из запроса."""
    url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if url:
        return url if "://" in url else f"https://{url}"
    domain = os.environ.get("DOMAIN", "").strip()
    if domain and domain not in {"localhost", "127.0.0.1"}:
        return f"https://{domain}"
    return ""


class Settings:
    public_url: str = _public_url()
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin").strip().lower() or "admin"
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "") or DEFAULT_ADMIN_PASSWORD
    secret_key: str = os.environ.get("SECRET_KEY", "").strip()
    radicale_url: str = os.environ.get("RADICALE_URL", "http://radicale:5232").rstrip("/")
    # auto: Secure-cookie, если сервис открыт по https (за TLS-прокси)
    cookie_secure: bool = (public_url.startswith("https://")
                           if os.environ.get("COOKIE_SECURE", "auto").strip() == "auto"
                           else _bool("COOKIE_SECURE"))
    data_dir: Path = Path(os.environ.get("DATA_DIR", "/data"))
    # имя адресной книги на телефонах (задаётся при создании пользователя)
    addressbook_name: str = (os.environ.get("ADDRESSBOOK_NAME", "").strip()
                             or ("Contacts" if os.environ.get("DEFAULT_LANG", "").strip().lower() == "en"
                                 else "Контакты"))
    session_cookie: str = "contacts_session"
    session_max_age: int = 60 * 60 * 24 * 7
    dav_rate_limit: int = 10  # неудачных попыток в минуту на пару IP+логин
    web_rate_limit: int = 10

    @property
    def db_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir / "app.db"


settings = Settings()


def _ensure_secret_key() -> None:
    """SECRET_KEY из .env, иначе — сгенерированный один раз и сохранённый в томе данных."""
    if settings.secret_key:
        return
    path = settings.data_dir / "secret_key"
    if path.exists():
        settings.secret_key = path.read_text().strip()
    if not settings.secret_key:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.secret_key = secrets.token_urlsafe(48)
        path.write_text(settings.secret_key)
        path.chmod(0o600)


_ensure_secret_key()


def public_url(request) -> str:
    """Адрес, который показываем людям (DAVx5, вход): настроенный или тот, по которому открыли."""
    return settings.public_url or str(request.base_url).rstrip("/")


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.environ.get("TZ", "").strip() or "Europe/Moscow")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


# пояс, в котором показываем время (TZ из compose); в базе время — UTC без пояса
timezone = _timezone()
