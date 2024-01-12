FROM python:3.12.1-alpine3.18@sha256:af0d8da43677e3000ebdf4045508d891a87e7bd2d3ec87bc6e40403be97291b8

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/blacklist_api

COPY main.py .

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "\"*\"" ]
