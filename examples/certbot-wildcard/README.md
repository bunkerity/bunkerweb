# Certbot wildcard

Simple example on how to get wildcard Let's Encrypt certificates through DNS challenge and use them with bunkerized-nginx.

## Preamble

We will assume that you already have some basic knowledges about Let's Encrypt DNS challenge. If that's not the case, you should read the [documentation](https://certbot.eff.org/docs/using.html#manual).

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/certbot-wildcard/architecture.png?raw=true" />

## Configuration

First of all you will need to edit the **certbot-wildcard.sh** file with your domain(s).

Then you can run the script to get the certificates. Don't forget that you will need to edit your DNS zone to prove that you own the domain(s).

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/certbot-wildcard/docker-compose.yml).
