FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apk add --no-cache build-base libffi-dev postgresql-dev cargo zlib-dev jpeg-dev

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/ui/requirements.txt /tmp/req/requirements-ui.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements-gen.txt
COPY src/common/db/requirements.txt /tmp/req/requirements-db.txt
COPY src/common/db/requirements.arm.txt /tmp/req/requirements-db.arm.txt
COPY src/common/db/requirements.386.txt /tmp/req/requirements-db.386.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  if [ "$TARGETPLATFORM" = "linux/arm/v7" ] ; then mv /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.txt && rm -f /tmp/req/requirements-db.386.txt ; elif [ "$TARGETPLATFORM" = "linux/386" ] ; then mv /tmp/req/requirements-db.386.txt /tmp/req/requirements-db.txt && rm -f /tmp/req/requirements-db.arm.txt ; else rm -f /tmp/req/requirements-db.arm.txt /tmp/req/requirements-db.386.txt ; fi && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

WORKDIR /usr/share/bunkerweb

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/db db
COPY src/common/core core
COPY src/common/gen gen
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/common/helpers helpers
COPY src/VERSION VERSION
COPY src/ui ui

WORKDIR /tmp

COPY src/deps/package.json package.json
COPY src/deps/package-lock.json package-lock.json

ARG SKIP_MINIFY=no
ARG SKIP_MINIFY_JS=no
ARG SKIP_MINIFY_CSS=no
RUN if [ "$SKIP_MINIFY" != "yes" ] && { [ "$SKIP_MINIFY_JS" != "yes" ] || [ "$SKIP_MINIFY_CSS" != "yes" ]; }; then \
  apk add --no-cache nodejs npm parallel && \
  cd /tmp && \
  npm ci --ignore-scripts; \
  fi

# Minify JS files
RUN if [ "$SKIP_MINIFY" != "yes" ] && [ "$SKIP_MINIFY_JS" != "yes" ]; then \
  find /usr/share/bunkerweb/ui/app/static -type f -name "*.js" ! -name "*.min.js" -print0 \
  | parallel -0 --no-run-if-empty 'npx uglify-js {} --compress --mangle --output {}'; \
  else \
  echo "Skipping JS minification"; \
  fi

# Minify CSS files
RUN if [ "$SKIP_MINIFY" != "yes" ] && [ "$SKIP_MINIFY_CSS" != "yes" ]; then \
  find /usr/share/bunkerweb/ui/app/static -type f -name "*.css" ! -name "*.min.css" -print0 \
  | parallel -0 --no-run-if-empty 'npx postcss {} --use cssnano --no-map -o {}'; \
  else \
  echo "Skipping CSS minification"; \
  fi

FROM python:3.13-alpine@sha256:3527940d79521d5746929cb52e73b477e6acc3f34b35524fbee0dd11b23ff6b4

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

COPY src/deps/requirements.txt /tmp/requirements-deps.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt

# Install runtime dependencies and add ui user
RUN apk add --no-cache bash unzip mariadb-connector-c mariadb-client postgresql-client sqlite tzdata && \
  addgroup -g 101 ui && \
  adduser -h /usr/share/bunkerweb/ui -g ui -s /sbin/nologin -G ui -D -H -u 101 --disabled-password ui

# Fix CVEs
# There are no CVEs for the following packages

# Copy dependencies
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Create data folders and set permissions
RUN echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/default-server-stream configs/modsec configs/modsec-crs") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:ui INTEGRATION /data /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  chmod -R 770 /data /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  find . \( -path './ui' -o -path './db' -o -path './gen' -o -path './utils' -o -path './helpers' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find ui db gen utils helpers deps -type f ! -path 'deps/python/bin/*' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 660 INTEGRATION

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.6.8"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="ui"

VOLUME /data

EXPOSE 7000

WORKDIR /usr/share/bunkerweb/ui

USER ui:ui

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

ENTRYPOINT [ "./entrypoint.sh" ]
