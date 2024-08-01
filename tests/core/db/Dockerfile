FROM python:3.12.4-alpine@sha256:7f15e22f496c65cffbbac5e30e7e98d60f3e3b9cc5ee5d51cf3c55ed604787c8

WORKDIR /tmp

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev libffi-dev && \
  MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

RUN addgroup -g 101 nginx && \
  adduser -h /opt/tests -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx

COPY --chown=nginx:nginx main.py .
ADD ./init/plugins external
ADD ./init/bunkerweb bunkerweb

RUN chown -R nginx:nginx external bunkerweb && \
  chmod -R 777 external bunkerweb

USER nginx:nginx

ENTRYPOINT [ "python3", "main.py" ]
