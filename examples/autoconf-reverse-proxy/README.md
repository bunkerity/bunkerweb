# Autoconf reverse proxy

Quickly deploy web app on Docker containers without restarting bunkerized-nginx.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/autoconf-reverse-proxy/architecture.png?raw=true" />

## Autoconf

First of all, you need to run bunkerized-nginx and bunkerized-nginx-autoconf : see [docker-compose-nginx.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-reverse-proxy/docker-compose-nginx.yml).

Then, you can add and remove web apps with special `bunkerized-nginx.*` labels so the configurations are automatically generated : see [docker-compose-apps.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-reverse-proxy/docker-compose-apps.yml).
