# Autoconf PHP

Quickly deploy PHP app on Docker containers without restarting bunkerized-nginx.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-php/architecture.png?raw=true" />

## Autoconf

First of all, you need to setup the [Docker autoconf integration](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker-autoconf).

Then, you can add and remove PHP apps with special `bunkerized-nginx.*` labels so the configurations are automatically generated : see [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-php/docker-compose.yml).
