# Certbot with Cloudflare

Cloudflare supports HTTPS traffic between their servers and the origin one. This examples shows how to automatically valid HTTPS certificates signed by Let's Encrypt using the Cloudflare API.

## Preamble

We will assume that you already have some basic knowledges about Cloudflare. If that's not the case, we have made a dedicated blog post [here](https://www.bunkerity.com/web-security-at-almost-no-cost-cloudflare-free-plan-with-bunkerized-nginx/).

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/certbot-cloudflare/architecture.png?raw=true" />

## Configuration

First of all you will need to edit the **certbot-new.sh** and **cloudflare.ini** files (e.g : domains, CF token, ...).

Then run the **certbot-new.sh** script to get the certificates and add cron job for **certbot-renew.sh** to setup automatic renewal.

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/certbot-cloudflare/docker-compose.yml).
