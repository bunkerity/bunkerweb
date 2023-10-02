FROM python:3.11.5-alpine@sha256:cd311c6a0164f34a7edbf364e05258b07d66d3f7bc155139dcb9bef88a186ded AS builder

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/common/gen/requirements.txt /tmp/req/requirements.txt
COPY src/common/db/requirements.txt /tmp/req/requirements.txt.1

WORKDIR /usr/share/bunkerweb

RUN mkdir -p deps/python && \
  cat /tmp/req/requirements.txt* > deps/requirements.txt && \
  rm -rf /tmp/req

# Install python dependencies
RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --ignore-installed --require-hashes -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Remove build dependencies
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/autoconf autoconf
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

FROM python:3.11.5-alpine@sha256:cd311c6a0164f34a7edbf364e05258b07d66d3f7bc155139dcb9bef88a186ded

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add autoconf user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash && \
  addgroup -g 101 autoconf && \
  adduser -h /usr/share/bunkerweb/autoconf -g autoconf -s /bin/sh -G autoconf -D -H -u 101 autoconf && \
  cp helpers/bwcli /usr/bin/ && \
  mkdir -p /etc/bunkerweb && \
  mkdir -p /run/secrets && \
  mkdir -p /var/tmp/bunkerweb && \
  mkdir -p /var/run/bunkerweb && \
  touch /etc/bunkerweb/ui.conf /etc/bunkerweb/config.yaml && \
  chown -R root:autoconf /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb && \
  chmod 750 autoconf/entrypoint.sh cli/main.py helpers/*.sh /usr/bin/bwcli autoconf/*.py deps/python/bin/*

# Fix CVEs
# There are no CVE to fix for the moment

WORKDIR /usr/share/bunkerweb/autoconf

USER autoconf:autoconf

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
