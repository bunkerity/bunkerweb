FROM python:3.13.0-alpine@sha256:81362dd1ee15848b118895328e56041149e1521310f238ed5b2cdefe674e6dbf

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/greylist_api

COPY main.py .

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "\"*\"" ]
