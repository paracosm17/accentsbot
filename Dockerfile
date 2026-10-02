FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

FROM python:3.13.15-slim-bookworm

ARG VCS_REF=unknown

LABEL org.opencontainers.image.source="https://github.com/paracosm17/accentsbot" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    RELEASE_REVISION=${VCS_REF} \
    WEB_SERVER_HOST=0.0.0.0 \
    PORT=8080

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --create-home app \
    && chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8080
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read()"

CMD ["python", "-m", "bot"]
