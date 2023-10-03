FROM python:3.12.0-alpine@sha256:ae35274f417fc81ba6ee1fc84206e8517f28117566ee6a04a64f004c1409bdac

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
