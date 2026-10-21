FROM python:3.15-alpine@sha256:2699b90f4d562a22e2dd076c82f964032f64814204bff36d271a54ba4cc2c7e2

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
  pip install --no-cache-dir --require-hashes -r /tmp/req/requirements-db.txt && \
  pip install psycopg2

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
