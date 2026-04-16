# --- Builder stage ---
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim

LABEL maintainer="primetrade"

RUN groupadd -r trader && useradd -r -g trader -d /app -s /sbin/nologin trader

WORKDIR /app

COPY --from=builder /install /usr/local

COPY bot/ bot/
COPY cli.py .
COPY .env .env

RUN mkdir -p logs && chown -R trader:trader /app

USER trader

ENTRYPOINT ["python", "cli.py"]
