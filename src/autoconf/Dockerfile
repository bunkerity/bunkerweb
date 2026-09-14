FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS builder

# Export var for specific actions on linux/arm/v7
ARG TARGETPLATFORM

# Install python dependencies
RUN apt-get update && \
  apt-get install -y --no-install-recommends build-essential libffi-dev cargo && \
  rm -rf /var/lib/apt/lists/*

# Copy python requirements
COPY src/deps/requirements.txt /tmp/requirements-deps.txt
COPY src/autoconf/requirements.txt /tmp/req/requirements-autoconf.txt

WORKDIR /usr/share/bunkerweb

# Install python requirements
RUN export MAKEFLAGS="-j$(nproc)" && \
  pip install --no-cache-dir --require-hashes --break-system-packages -r /tmp/requirements-deps.txt && \
  pip install --no-cache-dir --require-hashes --target deps/python $(for file in $(ls /tmp/req/requirements*.txt) ; do echo "-r ${file}" ; done | xargs)

# Copy files
# can't exclude specific files/dir from . so we are copying everything by hand
COPY src/common/api api
COPY src/common/cli cli
COPY src/common/core core
COPY src/common/helpers helpers
COPY src/common/settings.json settings.json
COPY src/common/utils utils
COPY src/autoconf autoconf
COPY src/VERSION VERSION

FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

# Set default umask to prevent huge recursive chmod increasing the final image size
RUN umask 027

# Install bash and create autoconf user
RUN apt-get update && \
  apt-get install -y --no-install-recommends bash tzdata ca-certificates && \
  rm -rf /var/lib/apt/lists/* && \
  groupadd -g 101 autoconf && \
  useradd -u 101 -g autoconf -d /usr/share/bunkerweb/autoconf -s /usr/sbin/nologin -M autoconf

# Fix CVEs. This image has no other runtime deps re-installing these, so each maps to a finding
# of this image's own pre-fix Trivy scan:
#   util-linux 2.41-5 -> 2.41.5-0+deb13u1: CVE-2025-14104 CVE-2026-13595 CVE-2026-27456
#     CVE-2026-53612 CVE-2026-53613 CVE-2026-53614 CVE-2026-53615
#   openssl 3.5.6-1~deb13u2 -> 3.5.7-1~deb13u2 (drags libssl3t64 + openssl-provider-legacy):
#     CVE-2026-14456 CVE-2026-14457 CVE-2026-18798 CVE-2026-54874 CVE-2026-63072 CVE-2026-63073
#     CVE-2026-63074 CVE-2026-63075 CVE-2026-63076 CVE-2026-75803
#   gzip 1.13-1 -> 1.13-1+deb13u1: CVE-2026-41992 CVE-2026-41991
#   glibc (libc6/libc-bin) 2.41-12+deb13u3 -> +deb13u4: CVE-2026-5450 CVE-2026-5928
#   pcre2 (libpcre2-8-0) 10.46-1~deb13u1 -> ~deb13u2: CVE-2026-86145 CVE-2026-89156 CVE-2026-89157
#     CVE-2026-89158 CVE-2026-89160 CVE-2026-89161 CVE-2026-89162
#   sqlite (libsqlite3-0) 3.46.1-7+deb13u1 -> +deb13u2: CVE-2026-11822 CVE-2026-11824
#   perl-base 5.40.1-6 -> 5.40.1-6+deb13u1: CVE-2026-13221 CVE-2026-42496 CVE-2026-8376
#     CVE-2026-42497 CVE-2026-12087 CVE-2026-48959 CVE-2026-48961 CVE-2026-48962 CVE-2026-57432
#     CVE-2026-57433 CVE-2025-15649 CVE-2026-7010 CVE-2026-7017
RUN apt-get update && apt-get install -y --no-install-recommends bsdutils libblkid1 liblastlog2-2 libmount1 libsmartcols1 libuuid1 login mount openssl util-linux gzip libc-bin libc6 libpcre2-8-0 libsqlite3-0 perl-base && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY --from=builder --chown=0:101 --chmod=550 /usr/share/bunkerweb /usr/share/bunkerweb

WORKDIR /usr/share/bunkerweb

# Drop bwcli, install runtime dependencies, create data folders and set permissions
RUN cp helpers/bwcli /usr/bin/ && \
  echo "Docker" > INTEGRATION && \
  mkdir -p /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /var/www && \
  mkdir -p /data/cache && ln -s /data/cache /var/cache/bunkerweb && \
  mkdir -p /data/lib && ln -s /data/lib /var/lib/bunkerweb && \
  mkdir -p /data/www && ln -s /data/www /var/www/html && \
  for dir in $(echo "pro configs plugins") ; do mkdir -p "/data/${dir}" && ln -s "/data/${dir}" "/etc/bunkerweb/${dir}" ; done && \
  for dir in $(echo "pro/plugins configs/http configs/stream configs/server-http configs/server-stream configs/default-server-http configs/modsec configs/modsec-crs configs/crs-plugins-before configs/crs-plugins-after") ; do mkdir "/data/${dir}" ; done && \
  chown -R root:autoconf INTEGRATION /data /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb /usr/bin/bwcli && \
  chmod -R 770 /data /var/cache/bunkerweb /var/lib/bunkerweb /var/www/html /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb && \
  find . \( -path './autoconf' -o -path './cli' -o -path './core' -o -path './helpers' -o -path './utils' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  find autoconf cli core helpers utils deps -type f ! -path 'deps/python/bin/*' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440 && \
  chmod 660 INTEGRATION

LABEL maintainer="Bunkerity <contact@bunkerity.com>"
LABEL version="1.7.0~beta"
LABEL url="https://www.bunkerweb.io"
LABEL bunkerweb.type="autoconf"

VOLUME /data

WORKDIR /usr/share/bunkerweb/autoconf

USER autoconf:autoconf

HEALTHCHECK --interval=10s --timeout=10s --start-period=60s --retries=6 CMD /usr/share/bunkerweb/helpers/healthcheck-autoconf.sh

ENV PYTHONPATH="/usr/share/bunkerweb/deps/python"

CMD [ "./entrypoint.sh" ]
