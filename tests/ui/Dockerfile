FROM python:3.11.3-alpine

# Install firefox and geckodriver
RUN apk add --no-cache --virtual .build-deps curl grep zip && \
  apk add --no-cache firefox

# Installing geckodriver for firefox...
RUN GECKODRIVER_VERSION=`curl -i https://github.com/mozilla/geckodriver/releases/latest | grep -Po 'v[0-9]+.[0-9]+.[0-9]+'` && \
  wget -O geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
  tar -C /usr/local/bin -xzvf geckodriver.tar.gz && \
  chmod +x /usr/local/bin/geckodriver && \
  rm geckodriver.tar.gz

WORKDIR /opt/tests_ui

RUN echo '{ \
  "id": "discord", \
  "order": 999, \
  "name": "Discord", \
  "description": "Send alerts to a Discord channel (using webhooks).", \
  "version": "0.1", \
  "stream": "no", \
  "settings": {} \
  }' > plugin.json && \
  zip -r discord.zip plugin.json && \
  rm plugin.json

# Clean up
RUN apk del .build-deps && \
  rm -rf /var/cache/apk/*

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py .
COPY test.zip .

CMD ["python3", "main.py"]
