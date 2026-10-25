# Radicale собирается из закреплённой версии на PyPI, а не из стороннего образа
FROM python:3.12.15-slim

RUN pip install --no-cache-dir radicale==3.8.3

RUN useradd --create-home --uid 10001 radicale \
 && mkdir -p /data/collections /etc/radicale \
 && chown -R radicale:radicale /data

COPY config /etc/radicale/config
COPY rights /etc/radicale/rights

USER radicale
EXPOSE 5232

CMD ["python", "-m", "radicale", "--config", "/etc/radicale/config"]
