FROM python:3.10-alpine@sha256:8d21601f9f531162bc0c37ae0ac9e7a070e512a6ae0ffc4090118866902c9caa

# Install python dependencies
RUN apk add --no-cache --virtual .build-deps \
  build-base libffi-dev postgresql-dev cargo

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt

WORKDIR /usr/share/migration

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes -r /tmp/req/requirements-db.txt

# Install dependencies
RUN apk add --no-cache bash sed curl mariadb-connector-c mariadb-client postgresql-client sqlite tzdata

# Cleanup
RUN apk del .build-deps && \
rm -rf /var/cache/apk/*

# Copy files
COPY src/common/db/alembic/alembic.ini alembic.ini
COPY src/common/db/alembic/env.py env.py
COPY src/common/db/alembic/script.py.mako script.py.mako
COPY src/common/db/model.py latest_model.py
COPY misc/migration/entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh

ENTRYPOINT [ "./entrypoint.sh" ]
