from __future__ import annotations

import logging
import threading
from xml.sax.saxutils import escape

import httpx

import config
from i18n import _

log = logging.getLogger("dav")

ADDRESSBOOK_XML = """<?xml version="1.0" encoding="utf-8"?>
<D:mkcol xmlns:D="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <D:set>
    <D:prop>
      <D:resourcetype><D:collection/><CR:addressbook/></D:resourcetype>
      <D:displayname>{name}</D:displayname>
    </D:prop>
  </D:set>
</D:mkcol>"""

# Radicale собирает ответ REPORT целиком в памяти: все 300+ карточек с фото разом —
# около 200 МБ, два таких запроса одновременно упирались в лимит и Radicale убивался
MULTIGET_CHUNK = 25
# массовые чтения из приложения — строго по одному, чтобы не множить пики памяти Radicale
_bulk_lock = threading.Lock()

MULTIGET_XML = """<?xml version="1.0" encoding="utf-8"?>
<CR:addressbook-multiget xmlns:D="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <D:prop>
    <D:getetag/>
    <CR:address-data/>
  </D:prop>
  {}
</CR:addressbook-multiget>"""


# один клиент на процесс: keep-alive до Radicale вместо нового соединения на запрос
_http = httpx.Client(timeout=15.0)


class DavError(RuntimeError):
    pass


class DavUnavailable(DavError):
    """Radicale не ответил (перезапуск, сеть) — запрос можно повторить."""


class DavClient:
    """CardDAV-клиент к Radicale. Приложение никогда не читает хранилище напрямую."""

    def __init__(self, username: str):
        self.username = username
        self.base = config.settings.radicale_url
        self.collection = f"{self.base}/{username}/contacts/"
        self.headers = {"X-Remote-User": username}

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = dict(self.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        try:
            response = _http.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("carddav %s %s failed: %s", method, url, exc.__class__.__name__)
            raise DavUnavailable(_("Сервер контактов недоступен. Попробуйте ещё раз через минуту.")) from exc
        if response.status_code >= 500:
            raise DavError(_("Сервер контактов вернул ошибку. Попробуйте позже."))
        return response

    def ensure_addressbook(self) -> None:
        response = self._request("MKCOL", self.collection,
                                 content=ADDRESSBOOK_XML.format(name=escape(config.settings.addressbook_name)).encode(),
                                 headers={"Content-Type": "application/xml; charset=utf-8"})
        if response.status_code in (201, 200, 405, 301):
            return
        response = self._request("PROPFIND", self.collection, headers={"Depth": "0"})
        if response.status_code == 207:
            return
        raise DavError(_("Не удалось создать адресную книгу (HTTP {status})", status=response.status_code))

    def delete_collection(self) -> None:
        self._request("DELETE", f"{self.base}/{self.username}/")

    def list_contacts(self) -> list[dict]:
        """Все карточки с содержимым — порциями (см. MULTIGET_CHUNK)."""
        return self.fetch(list(self.list_etags()))

    def fetch(self, hrefs: list[str]) -> list[dict]:
        items: list[dict] = []
        with _bulk_lock:
            for start in range(0, len(hrefs), MULTIGET_CHUNK):
                items.extend(self.multiget(hrefs[start:start + MULTIGET_CHUNK]))
        return items

    @staticmethod
    def _parse_cards(content: bytes) -> list[dict]:
        import xml.etree.ElementTree as ET

        ns = {"d": "DAV:", "cr": "urn:ietf:params:xml:ns:carddav"}
        items: list[dict] = []
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            raise DavError(_("Сервер вернул некорректный ответ")) from exc
        for resp in root.findall("d:response", ns):
            href = resp.findtext("d:href", default="", namespaces=ns)
            if not href or href.rstrip("/").endswith("/contacts"):
                continue
            etag = resp.findtext("d:propstat/d:prop/d:getetag", default="", namespaces=ns)
            data = resp.findtext("d:propstat/d:prop/cr:address-data", default="", namespaces=ns)
            items.append({"href": href, "etag": etag, "vcard": data})
        return items

    def list_hrefs(self) -> list[str]:
        """Адреса всех карточек без их содержимого (для очистки)."""
        return list(self.list_etags())

    def list_etags(self) -> dict[str, str]:
        """{href: etag} всех карточек — дёшево, без содержимого."""
        body = b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:getetag/></D:prop></D:propfind>'
        response = self._request("PROPFIND", self.collection, content=body,
                                 headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"})
        if response.status_code == 404:
            return []
        if response.status_code != 207:
            raise DavError(_("Не удалось получить список контактов (HTTP {status})", status=response.status_code))
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise DavError(_("Сервер вернул некорректный ответ")) from exc
        result = {}
        for resp in root.findall("{DAV:}response"):
            href = resp.findtext("{DAV:}href", default="")
            if href and not href.rstrip("/").endswith("/contacts"):
                result[href] = resp.findtext("{DAV:}propstat/{DAV:}prop/{DAV:}getetag", default="")
        return result

    def multiget(self, hrefs: list[str]) -> list[dict]:
        """Содержимое только указанных карточек (addressbook-multiget)."""
        body = MULTIGET_XML.format("".join(f"<D:href>{escape(h)}</D:href>" for h in hrefs))
        response = self._request("REPORT", self.collection, content=body.encode(),
                                 headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"})
        if response.status_code not in (207, 200):
            raise DavError(_("Не удалось получить контакты (HTTP {status})", status=response.status_code))
        return self._parse_cards(response.content)

    def get_contact(self, href: str) -> tuple[str, str]:
        response = self._request("GET", self._absolute(href))
        if response.status_code != 200:
            raise DavError(_("Контакт не найден (HTTP {status})", status=response.status_code))
        return response.text, response.headers.get("etag", "")

    def put_contact(self, href: str, vcard: str, etag: str | None = None, create: bool = False) -> str:
        headers = {"Content-Type": "text/vcard; charset=utf-8"}
        if create:
            headers["If-None-Match"] = "*"
        elif etag:
            headers["If-Match"] = etag
        response = self._request("PUT", self._absolute(href), content=vcard.encode(), headers=headers)
        if response.status_code == 412:
            raise DavError("conflict")
        if response.status_code not in (200, 201, 204):
            raise DavError(_("Не удалось сохранить контакт (HTTP {status})", status=response.status_code))
        return response.headers.get("etag", "")

    def delete_contact(self, href: str, etag: str | None) -> None:
        headers = {"If-Match": etag} if etag else {}
        response = self._request("DELETE", self._absolute(href), headers=headers)
        if response.status_code not in (200, 204, 404):
            raise DavError(_("Не удалось удалить контакт (HTTP {status})", status=response.status_code))

    def _absolute(self, href: str) -> str:
        """Приводит href к абсолютному URL внутри адресной книги пользователя."""
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{config.settings.radicale_url}{href}"
        # имя файла без пути — относительно коллекции пользователя
        return self.collection + href.lstrip("/")


def href_for(uid: str) -> str:
    return f"{uid}.vcf"
