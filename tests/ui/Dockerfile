FROM python:3.12.4-alpine@sha256:7f15e22f496c65cffbbac5e30e7e98d60f3e3b9cc5ee5d51cf3c55ed604787c8

# Install firefox and geckodriver
RUN apk add --no-cache --virtual .build-deps curl grep zip wget && \
  apk add --no-cache firefox

# Installing geckodriver for firefox...
RUN GECKODRIVER_VERSION=`curl -i https://github.com/mozilla/geckodriver/releases/latest | grep -Po 'v[0-9]+\.[0-9]+\.[0-9]+'` && \
  wget -O geckodriver.tar.gz -w 5 https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
  tar -C /usr/local/bin -xzvf geckodriver.tar.gz && \
  chmod +x /usr/local/bin/geckodriver && \
  rm geckodriver.tar.gz

WORKDIR /opt/tests_ui

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt

RUN touch test.txt && \
  zip test.zip test.txt && \
  rm test.txt

RUN echo '{ \
  "id": "discord", \
  "name": "Discord", \
  "description": "Send alerts to a Discord channel (using webhooks).", \
  "version": "0.1", \
  "stream": "no", \
  "settings": {} \
  }' > plugin.json && \
  zip discord.zip plugin.json && \
  rm plugin.json

# Clean up
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

ARG TEST_FILE=main.py

COPY base.py .
COPY wizard.py .
COPY utils.py .
COPY $TEST_FILE main.py

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]
