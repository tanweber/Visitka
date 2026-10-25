#!/usr/bin/env bash
# Проверки приёмки этапов 1, 3 и 4 против запущенного стека.
set -u

CADDY="${CADDY:-http://localhost:8080}"
DOMAIN="${DOMAIN:-contacts.example.com}"
USERNAME="${USERNAME:-}"
DEVICE_PASSWORD="${DEVICE_PASSWORD:-}"
OTHER_USER="${OTHER_USER:-}"
FAILED=0

check() {
  local title="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    printf '  ok   %s (%s)\n' "$title" "$actual"
  else
    printf '  FAIL %s: ждали %s, получили %s\n' "$title" "$expected" "$actual"
    FAILED=$((FAILED + 1))
  fi
}

echo "== 1. Доступ к CardDAV =="
code=$(curl -s -o /dev/null -w '%{http_code}' -X PROPFIND -H 'Depth: 0' "$CADDY/carddav/")
check "PROPFIND без пароля" "401" "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' -X PROPFIND -H 'X-Remote-User: test' -H 'Depth: 0' "$CADDY/carddav/")
check "подмена X-Remote-User без пароля" "401" "$code"

code=$(curl -s -o /dev/null -w '%{http_code}' "$CADDY/.well-known/carddav")
check ".well-known/carddav → 301" "301" "$code"

if [ -n "$USERNAME" ] && [ -n "$DEVICE_PASSWORD" ]; then
  echo "== 3. Пароль устройства =="
  code=$(curl -s -o /dev/null -w '%{http_code}' -u "$USERNAME:$DEVICE_PASSWORD" -X PROPFIND -H 'Depth: 0' "$CADDY/carddav/")
  check "PROPFIND с паролем устройства" "207" "$code"

  code=$(curl -s -o /dev/null -w '%{http_code}' -u "$USERNAME:web-password" -X PROPFIND -H 'Depth: 0' "$CADDY/carddav/")
  check "PROPFIND с паролем веб-входа" "401" "$code"

  echo "== 4. Адресная книга =="
  code=$(curl -s -o /dev/null -w '%{http_code}' -u "$USERNAME:$DEVICE_PASSWORD" -X PROPFIND -H 'Depth: 1' "$CADDY/carddav/$USERNAME/contacts/")
  check "адресная книга владельца" "207" "$code"

  if [ -n "$OTHER_USER" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' -u "$OTHER_USER:$DEVICE_PASSWORD" -X PROPFIND -H 'Depth: 0' "$CADDY/carddav/$USERNAME/")
    check "чужая адресная книга закрыта" "403" "$code"
  fi
else
  echo "== 3,4 пропущены: не заданы USERNAME/DEVICE_PASSWORD =="
fi

echo
if [ "$FAILED" -eq 0 ]; then
  echo "Все проверки пройдены."
else
  echo "Провалено проверок: $FAILED"
fi
exit "$FAILED"
