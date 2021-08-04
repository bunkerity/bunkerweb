# Autoconf PHP

Quickly deploy PHP app on Docker containers without restarting bunkerized-nginx.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/autoconf-php/architecture.png?raw=true" />

## Autoconf

First of all, you need to run bunkerized-nginx and bunkerized-nginx-autoconf : see [docker-compose-nginx.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-php/docker-compose-nginx.yml).

Then, you can add and remove PHP apps with special `bunkerized-nginx.*` labels so the configurations are automatically generated : see [docker-compose-php.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/autoconf-php/docker-compose-php.yml).
