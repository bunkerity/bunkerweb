FROM ubuntu:focal

ARG DEBIAN_FRONTEND=noninteractive
RUN echo "===> Installing system dependencies..." && \
  BUILD_DEPS="curl unzip" && \
  apt-get update && apt-get install --no-install-recommends -y \
  python3 python3-pip wget git zip unzip \
  libappindicator3-1 libasound2 libdbus-glib-1-2 libxtst6 libxt6 firefox firefox-geckodriver \
  $BUILD_DEPS

RUN echo "===> Installing geckodriver for firefox..." && \
  GECKODRIVER_VERSION=`curl -i https://github.com/mozilla/geckodriver/releases/latest | grep -Po 'v[0-9]+.[0-9]+.[0-9]+'` && \
  wget https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz && \
  tar -zxf geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz -C /usr/local/bin && \
  chmod +x /usr/local/bin/geckodriver && \
  rm geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz

RUN echo "===> Remove build dependencies..." && \
  apt-get remove -y $BUILD_DEPS && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONUNBUFFERED=1

ENV APP_HOME /usr/src/app
WORKDIR /$APP_HOME

COPY requirements.txt $APP_HOME/requirements.txt

RUN pip install -r requirements.txt

COPY main.py $APP_HOME/main.py
COPY test.zip $APP_HOME/

RUN wget https://github.com/bunkerity/bunkerweb-plugins/archive/refs/heads/main.zip && \
  unzip main.zip && \
  mv bunkerweb-plugins-main/discord . && \
  zip -r discord.zip discord && \
  rm -rf bunkerweb-plugins-main main.zip

CMD ["python3", "main.py"]
