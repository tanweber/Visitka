FROM python:3.12.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/app

COPY requirements.txt /srv/app/requirements.txt
RUN pip install --no-cache-dir -r /srv/app/requirements.txt

COPY . /srv/app

RUN useradd --create-home --uid 10002 appuser \
 && mkdir -p /data \
 && chown -R appuser:appuser /data /srv/app

USER appuser
EXPOSE 8000

# доверенные прокси для X-Forwarded-* — подсеть compose (FORWARDED_ALLOW_IPS, читает uvicorn)
ENV FORWARDED_ALLOW_IPS=10.77.0.0/24
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
