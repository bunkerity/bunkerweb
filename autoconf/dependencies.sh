#!/bin/sh

# install dependencies
apk add py3-pip bash certbot curl openssl
pip3 install docker requests jinja2
