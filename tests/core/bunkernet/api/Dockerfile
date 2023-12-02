FROM python:3.12.0-alpine3.18@sha256:f1d0d03700fb2d4480e89fb807e7346c14b88952f7bd58d56de54a24817cc2e8

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/blacklist_api

COPY main.py .

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "\"*\"" ]
