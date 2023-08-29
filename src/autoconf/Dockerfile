FROM python:3.11.5-alpine AS builder

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/autoconf/requirements.txt deps/requirements.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
    mkdir -p deps/python && \
    pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/autoconf autoconf
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

FROM python:3.11.5-alpine

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
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

WORKDIR /usr/share/bunkerweb/autoconf

USER autoconf:autoconf

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
