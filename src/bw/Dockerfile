FROM nginx:1.31.5-alpine-slim@sha256:3b171d7224b669faa3cc2137fea0a65301791df1ec1f271ebd2a2b7461f7fade AS builder

# Install temporary requirements for the dependencies
RUN apk add --no-cache bash autoconf libtool automake geoip-dev g++ gcc curl-dev libxml2-dev pcre2-dev make linux-headers musl-dev gd-dev gnupg brotli-dev openssl-dev patch readline-dev yajl yajl-dev yajl-tools py3-pip python3-dev cargo lmdb-dev libfuzzy2-dev pkgconfig ca-certificates coreutils libc-dev

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
  apk add --no-cache "nodejs>=24.18.1-r0" "npm>=11.12.1-r0" parallel && \
  cd /tmp && \
  npm ci --ignore-scripts --engine-strict && \
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

FROM nginx:1.31.5-alpine-slim@sha256:3b171d7224b669faa3cc2137fea0a65301791df1ec1f271ebd2a2b7461f7fade

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install runtime dependencies
RUN apk add --no-cache openssl pcre2 bash python3 yajl geoip libxml2 libgd curl tzdata brotli lmdb libfuzzy2

# Fix CVEs
RUN apk add --no-cache "python3>=3.14.7-r0" "pyc>=3.14.7-r0" # CVE-2026-7210
RUN apk add --no-cache "openssl>=3.5.8-r0" "libssl3>=3.5.8-r0" "libcrypto3>=3.5.8-r0" # CVE-2026-14456 CVE-2026-14457 CVE-2026-18798 CVE-2026-54874 CVE-2026-63072 CVE-2026-63073 CVE-2026-63074 CVE-2026-63075 CVE-2026-63076 CVE-2026-75803
RUN apk add --no-cache "expat>=2.8.4-r0" "libexpat>=2.8.4-r0" # CVE-2026-66046 CVE-2026-76641 CVE-2026-76956 CVE-2026-76957
RUN apk add --no-cache "curl>=8.22.0-r0" "libcurl>=8.22.0-r0" # CVE-2026-13608 CVE-2026-18924 CVE-2026-19931 CVE-2026-80229 CVE-2026-80230 CVE-2026-80231 CVE-2026-80255 CVE-2026-80256 CVE-2026-82208 CVE-2026-82209

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
LABEL version="1.6.15~rc1"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="bunkerweb"
LABEL bunkerweb.INSTANCE="bunkerweb"

EXPOSE 8080/tcp 8443/tcp 8443/udp

USER nginx:nginx

HEALTHCHECK --interval=10s --timeout=10s --start-period=10s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck.sh

ENTRYPOINT [ "./entrypoint.sh" ]
