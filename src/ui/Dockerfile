FROM python:3.11.5-alpine AS builder

# Install python dependencies
# RUN apk add --no-cache --virtual .build-deps g++ gcc musl-dev jpeg-dev zlib-dev libffi-dev cairo-dev pango-dev gdk-pixbuf-dev openssl-dev cargo postgresql-dev file make

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/ui/requirements.txt deps/requirements.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade pip-tools wheel setuptools && \
    mkdir -p deps/python && \
    pip install --no-cache-dir --require-hashes --target deps/python -r deps/requirements.txt

# Remove build dependencies
# RUN apk del .build-deps && \
#     rm -rf /var/cache/apk/*

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/helpers helpers
COPY src/common/utils utils
COPY src/VERSION VERSION

COPY src/ui ui

FROM python:3.11.5-alpine

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Copy dependencies
COPY --from=builder --chown=0:101 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Add ui user, drop bwcli, install runtime dependencies, create data folders and set permissions
RUN apk add --no-cache bash jq nodejs npm && \
    addgroup -g 101 ui && \
    adduser -h /usr/share/bunkerweb/ui -g ui -s /bin/sh -G ui -D -H -u 101 ui && \
    cp helpers/bwcli /usr/bin/ && \
    echo "Docker" > INTEGRATION && \
    mkdir -p /etc/bunkerweb && \
    mkdir -p /run/secrets && \
    mkdir -p /var/tmp/bunkerweb && \
    mkdir -p /var/run/bunkerweb && \
    mkdir -p /var/log/bunkerweb && \
    touch /etc/bunkerweb/ui.conf /etc/bunkerweb/config.yaml && \
    chown -R root:ui INTEGRATION /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
    chown -R ui:ui ui && \
    chmod 770 /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
    chmod 750 ui/entrypoint.sh ui/*.py /usr/bin/bwcli deps/python/bin/* helpers/*.sh && \
    chmod 660 INTEGRATION && \
    chown root:ui INTEGRATION
# ln -s /proc/1/fd/1 /var/log/bunkerweb/ui-access.log && \ # TODO find a solution
# ln -s /proc/1/fd/2 /var/log/bunkerweb/ui.log

# Fix CVEs
RUN apk add "libcrypto3>=3.1.1-r2" "libssl3>=3.1.1-r2"

USER ui:ui

# Change working directory
WORKDIR /usr/share/bunkerweb/ui/nuxt

# Initialize project
RUN npm install

# Build project
RUN npm run build

# Remove no longer needed files
RUN rm -rf .nuxtignore assets components composables layouts node_modules nuxt.config.ts pages public server tsconfig.json utils

# Change working directory
WORKDIR /usr/share/bunkerweb/ui

EXPOSE 7000

HEALTHCHECK --interval=10s --timeout=10s --start-period=30s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-ui.sh

ENV PYTHONPATH /usr/share/bunkerweb/deps/python

ENTRYPOINT [ "./entrypoint.sh" ]
