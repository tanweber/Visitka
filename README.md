# Visitka — self-hosted CardDAV address book with a clean web UI

**English** · [Русский](README.ru.md)

**Visitka** (Russian for “business card”, a nod to vCard) is a self-hosted, private address book for families and small teams. Phones sync contacts
over **CardDAV** (DAVx5 on Android, built-in Contacts on iOS/macOS), and a fast,
minimal **web interface** lets you browse, search and edit them from any browser.
Everything runs with a single `docker compose up -d`.

Built on [Radicale](https://radicale.org/) (the CardDAV server) plus a small
FastAPI app for users, device passwords and the web UI. No cloud, no tracking,
your vCards stay on your server.

> The web interface is in Russian. Contributions with translations are welcome.

<p align="center">
  <img src="docs/screenshots/list-light.png" alt="Contact list, light theme" width="260">
  <img src="docs/screenshots/card-dark.png" alt="Contact card, dark theme" width="260">
  <img src="docs/screenshots/filters-nord.png" alt="Filters by photo and organization, Nord theme" width="260">
</p>

<p align="center">
  <img src="docs/screenshots/desktop-forest.png" alt="Desktop view, Forest theme" width="800">
</p>

## Features

- **CardDAV sync** with Android (DAVx5), iPhone, iPad and macOS Contacts, Thunderbird.
- **Multi-user**: every user has a private address book; admins manage users.
- **Device passwords**: each phone gets its own revocable password, separate from the web login.
- **Instant search** by name, company, e-mail or phone number in any format (`8 900…` = `+7 900…`).
- **A–Z index** on the side of the list, like on a phone; tap or slide.
- **Filters**: with / without photo, by organization, combined with search.
- **Contact photos** with crop and zoom; stored inside the vCard (vCard 3.0 and 4.0).
- **Birthdays** in one consistent format, shown as “12 April 1990”, with or without the year.
- **Import / export** `.vcf` with progress, duplicate detection by UID, skip or replace.
- **Themes**: system, light, dark, Nord, Forest.
- **Mobile-first** design in the spirit of Apple and claude.ai, works great on phones.
- **Secure by default**: argon2 passwords, CSRF protection, strict CSP, read-only containers,
  dropped capabilities, rate limiting, forced password change on first login.

## Quick start

```bash
git clone https://github.com/<you>/Visitka.git visitka
cd visitka
docker compose up -d --build
```

Open `http://<server>:8080` and sign in with **admin / admin**. The app will ask you
to set a new password right away; nothing else is available until you do.

Then go to **Устройства** (Devices), create a device password and connect your phone.

For production put the service behind a TLS reverse proxy and set `PUBLIC_URL`
(see below). Without `.env` everything uses safe defaults.

## Configuration

Copy `.env.example` to `.env` and change what you need. All settings are optional.

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_URL` | taken from the request | Public address shown in the UI and the phone setup guide, e.g. `https://contacts.example.com` |
| `ADMIN_USERNAME` | `admin` | First administrator, created when the database is empty |
| `ADMIN_PASSWORD` | `admin` | Its password; the default one must be changed at first login |
| `SECRET_KEY` | generated | Session signing key; generated once and kept in the `app_data` volume |
| `CADDY_HTTP_PORT` | `8080` | Host port of the stack |
| `COOKIE_SECURE` | `auto` | Secure cookies; `auto` turns them on when `PUBLIC_URL` is `https://` |
| `TZ` | `Europe/Moscow` | Time zone for the UI and logs (times are stored in UTC) |
| `CONTACTS_SUBNET` | `10.77.0.0/24` | Internal Docker subnet; change if it overlaps with yours |

Apply changes with `docker compose up -d`.

## Connecting phones

The server URL is shown on the **Devices** page with a copy button.

**Android (DAVx5)**: `+` → *Login with URL and user name* → base URL `https://contacts.example.com`,
your user name and a **device password** (not the web password) → enable the “Контакты” address book.

**iPhone / iPad**: Settings → Contacts → Accounts → Add Account → Other → *Add CardDAV Account* →
server `contacts.example.com`, your user name and a device password.

**macOS**: Contacts → Settings → Accounts → `+` → Other Contacts Account → CardDAV.

## Reverse proxy and TLS

The stack listens on plain HTTP (`CADDY_HTTP_PORT`). Terminate TLS in front of it, for example
with Nginx Proxy Manager, Traefik, Caddy or nginx, forward everything to `http://<server>:8080`
and set `PUBLIC_URL=https://your.domain`. CardDAV discovery (`/.well-known/carddav`) is handled
by the stack.

## Architecture

```
phone / browser ──TLS──▶ your reverse proxy ──▶ caddy :8080
                                                 ├─ /carddav/* ─ forward_auth ─▶ app  (checks device password)
                                                 │                └──────────▶ radicale (X-Remote-User)
                                                 └─ /*  ───────────────────────▶ app  (web UI, FastAPI)
```

- **caddy**: routing, `forward_auth` for CardDAV, security headers; strips any client `X-Remote-User`.
- **radicale**: CardDAV storage (`python:3.12-slim` + `radicale==3.8.3`), not reachable from outside.
- **app**: FastAPI + Jinja2 + SQLite: users, device passwords, web UI.

## Backup and maintenance

```bash
scripts/backup.sh          # Radicale volume archive + SQLite backup into ./backups
scripts/smoke.sh           # acceptance checks against the running stack
docker compose run --rm app pytest -q   # tests
```

## Security notes

- Containers run read-only with `no-new-privileges` and all capabilities dropped.
- Web passwords and device passwords are hashed with argon2; failed logins are rate-limited.
- Changing a password ends other sessions; revoking a device password takes effect immediately.
- Only the `app` container receives secrets.

## License

[MIT](LICENSE)

---

**Keywords:** self-hosted contacts, CardDAV server, Radicale web UI, address book, DAVx5,
iPhone contacts sync, vCard, Docker Compose, FastAPI, privacy, Google Contacts alternative.
