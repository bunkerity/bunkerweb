FROM python:3.11.6-alpine3.18@sha256:527e0b0d92686a3ab1af3e65fdef12a47a9359f298dfd9b8d36617808d4029e9

WORKDIR /tmp

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev libffi-dev && \
  MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes -r requirements.txt && \
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
