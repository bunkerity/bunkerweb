FROM python:3.12.0-alpine@sha256:ae35274f417fc81ba6ee1fc84206e8517f28117566ee6a04a64f004c1409bdac

# Install firefox and geckodriver
RUN apk add --no-cache --virtual .build-deps curl grep zip wget && \
  apk add --no-cache firefox

# Installing geckodriver for firefox...
RUN GECKODRIVER_VERSION=`curl -i https://github.com/mozilla/geckodriver/releases/latest | grep -Po 'v[0-9]+\.[0-9]+\.[0-9]+'` && \
  wget -O geckodriver.tar.gz -w 5 https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
  tar -C /usr/local/bin -xzvf geckodriver.tar.gz && \
  chmod +x /usr/local/bin/geckodriver && \
  rm geckodriver.tar.gz

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
