FROM python:3.11-alpine@sha256:d174db33fa506083fbd941b265f7bae699e7c338c77c415f85dddff4f176d1de

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
