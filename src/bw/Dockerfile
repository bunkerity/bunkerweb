FROM nginx:1.30.2@sha256:540858b3a92eed95cbcae475698c12f619b4a6afa122485f439e4d7227cbeb38 AS builder

# glibc base (was Alpine): certbot-dns-multi's Go/CGO bridge cannot load on musl, so the image set
# is standardizing on glibc. nginx:1.30.2 is the official Debian image: nginx + the nginx user are
# prebuilt (--with-compat, so the BunkerWeb dynamic modules compiled by install.sh load), no
# separate nginx build needed.

# Install temporary requirements for the dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends bash autoconf libtool automake libgeoip-dev g++ gcc libcurl4-openssl-dev libxml2-dev libpcre2-dev make libgd-dev gnupg libbrotli-dev libssl-dev patch libreadline-dev libyajl2 libyajl-dev yajl-tools python3-pip python3-dev cargo liblmdb-dev libfuzzy-dev pkgconf ca-certificates coreutils && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/bunkerweb/deps

# Copy dependencies sources folder
COPY src/deps/misc misc
COPY src/deps/src src
COPY src/deps/deps.json deps.json
COPY --chmod=644 src/deps/install.sh install.sh

# Compile and install dependencies
RUN bash install.sh

WORKDIR /usr/share/bunkerweb

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/common/gen/requirements.txt deps/requirements-gen.txt

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --break-system-packages --no-cache-dir --require-hashes --ignore-installed -r /tmp/requirements-deps.txt && \
  pip install --break-system-packages --no-cache-dir --require-hashes --target deps/python -r deps/requirements-gen.txt

# Copy files
# can't exclude deps from . so we are copying everything by hand
COPY src/bw/entrypoint.sh entrypoint.sh
COPY src/bw/loading loading
COPY src/bw/lua lua
COPY src/bw/misc misc
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/confs confs
COPY src/common/core core
COPY src/common/gen gen
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/VERSION VERSION
COPY misc/*.ascii misc/

WORKDIR /tmp

COPY src/deps/package.json package.json
COPY src/deps/package-lock.json package-lock.json

# Minify HTML files
ARG SKIP_MINIFY=no
ARG SKIP_MINIFY_HTML=no
RUN if [ "$SKIP_MINIFY" != "yes" ] && [ "$SKIP_MINIFY_HTML" != "yes" ]; then \
  apt-get update && \
  apt-get install -y --no-install-recommends nodejs npm parallel && \
  rm -rf /var/lib/apt/lists/* && \
  cd /tmp && \
  npm ci --ignore-scripts && \
  find /usr/share/bunkerweb/loading /usr/share/bunkerweb/core/antibot/files /usr/share/bunkerweb/core/errors/files /usr/share/bunkerweb/core/misc/files -type f -name "*.html" | \
  parallel 'npx html-minifier-terser \
  --collapse-whitespace \
  --remove-comments \
  --remove-optional-tags \
  --remove-redundant-attributes \
  --remove-script-type-attributes \
  --remove-style-link-type-attributes \
  --minify-css true \
  --minify-js true \
  --output {} {}'; \
  else \
  echo "Skipping HTML minification"; \
  fi

FROM nginx:1.30.2@sha256:540858b3a92eed95cbcae475698c12f619b4a6afa122485f439e4d7227cbeb38

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies (nginx + the nginx user are already in the base)
RUN apt-get update && \
  apt-get install -y --no-install-recommends openssl libpcre2-8-0 bash python3 libyajl2 libgeoip1 libxml2 libgd3 curl ca-certificates tzdata libbrotli1 liblmdb0 libfuzzy2 && \
  rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Move bwcli, create data folders and set permissions
RUN cp helpers/bwcli /usr/bin/ && \
  echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:nginx INTEGRATION /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /etc/nginx /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/log/bunkerweb /var/run/bunkerweb && \
  chmod 2770 /var/tmp/bunkerweb && \
  find . \( -path './cli' -o -path './lua' -o -path './core' -o -path './gen' -o -path './helpers' -o -path './utils' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find cli lua gen helpers utils deps -type f ! -path 'deps/bin/*' ! -path 'deps/python/bin/*' ! -name '*.lua' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find core -type f ! -name '*.lua' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 550 entrypoint.sh && \
  chmod 660 INTEGRATION && \
  rm -f /var/log/bunkerweb/* && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/error.log && \
  ln -s /proc/1/fd/2 /var/log/bunkerweb/modsec_audit.log && \
  ln -s /proc/1/fd/1 /var/log/bunkerweb/access.log

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.7.0~beta"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="bunkerweb"
LABEL bunkerweb.INSTANCE="bunkerweb"

EXPOSE 8080/tcp 8443/tcp 8443/udp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT [ "./entrypoint.sh" ]
