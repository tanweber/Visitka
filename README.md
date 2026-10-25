# Visitka — self-hosted CardDAV address book with a clean web UI

**English** · [Русский](README.ru.md)

[![CI](https://github.com/tanweber/Visitka/actions/workflows/docker.yml/badge.svg)](https://github.com/tanweber/Visitka/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Docker images: amd64, arm64](https://img.shields.io/badge/docker-amd64%20%7C%20arm64-2496ED?logo=docker&logoColor=white)

**Visitka** (Russian for “business card”, a nod to vCard) is a self-hosted, private address book for families and small teams. Phones sync contacts
over **CardDAV** (DAVx5 on Android, built-in Contacts on iOS/macOS), and a fast,
minimal **web interface** lets you browse, search and edit them from any browser.
Everything runs with a single `docker compose up -d`.

Built on [Radicale](https://radicale.org/) (the CardDAV server) plus a small
FastAPI app for users, device passwords and the web UI. No cloud, no tracking,
your vCards stay on your server.

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
- **English and Russian** interface, picked from the browser language or switched in the menu.
- **Themes**: system, light, dark, Nord, Forest.
- **Mobile-first** design in the spirit of Apple and claude.ai, works great on phones.
- **Secure by default**: argon2 passwords, CSRF protection, strict CSP, read-only containers,
  dropped capabilities, rate limiting, forced password change on first login.

## Quick start

Ready-made images for amd64 and arm64 (Raspberry Pi) are published to GitHub Container Registry,
so you only need one file:

```bash
mkdir visitka && cd visitka
curl -fsSLO https://raw.githubusercontent.com/tanweber/Visitka/main/compose.yaml
docker compose up -d
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
| `DEFAULT_LANG` | `auto` | Interface language: `auto` (from the browser), `en` or `ru`; users can switch in the menu |
| `ADDRESSBOOK_NAME` | `Contacts` / `Контакты` | Name of the address book on phones, set when a user is created |
| `TZ` | `Europe/Moscow` | Time zone for the UI and logs (times are stored in UTC) |
| `CONTACTS_SUBNET` | `10.77.0.0/24` | Internal Docker subnet; change if it overlaps with yours |
| `VISITKA_VERSION` | `latest` | Image tag: `latest`, a release like `1.0`, or `edge` |

Apply changes with `docker compose up -d`. Update with `docker compose pull && docker compose up -d`.

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

- **caddy**: routing, `forward_auth` for CardDAV, security headers; strips any client `X-Remote-User`
  (`caddy:2.11.7` with the bundled Caddyfile).
- **radicale**: CardDAV storage (`python:3.12-slim` + `radicale==3.8.3`), not reachable from outside.
- **app**: FastAPI + Jinja2 + SQLite: users, device passwords, web UI.

## Building from source

```bash
git clone https://github.com/tanweber/Visitka.git visitka && cd visitka
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

To keep building locally, put `COMPOSE_FILE=compose.yaml:compose.build.yaml` into `.env`.

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
