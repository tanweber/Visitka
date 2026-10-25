# Caddy со встроенным Caddyfile и базой часовых поясов (для TZ)
FROM caddy:2.11.7

RUN apk add --no-cache tzdata

COPY Caddyfile /etc/caddy/Caddyfile
