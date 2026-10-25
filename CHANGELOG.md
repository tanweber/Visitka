# Changelog

## v1.0.0 — first public release

Visitka is a self-hosted CardDAV address book with a clean, mobile-first web UI.
Radicale stores the contacts, a small FastAPI app handles users, device passwords
and the interface, Caddy sits in front.

### Install

```bash
mkdir visitka && cd visitka
curl -fsSLO https://raw.githubusercontent.com/tanweber/Visitka/main/compose.yaml
VISITKA_VERSION=1.0.0 docker compose up -d
```

Open `http://<server>:8080`, sign in as **admin / admin** and set a new password.

### Highlights

- CardDAV sync with Android (DAVx5), iPhone / iPad, macOS and Thunderbird
- Multiple users, each with a private address book; revocable per-device passwords
- Instant search by name, company, e-mail or phone in any format; A–Z side index
- Filters by photo and organization, combined with search
- Contact photos with crop and zoom, stored in the vCard (3.0 and 4.0)
- Birthdays in one consistent format, with or without the year
- `.vcf` import with progress and duplicate handling, export of one or all contacts
- English and Russian interface; themes: system, light, dark, Nord, Forest
- Ready-made images for amd64 and arm64: `ghcr.io/tanweber/visitka-{app,radicale,caddy}`
- Secure defaults: argon2, CSRF protection, strict CSP, read-only containers,
  rate limiting, forced password change on first login
