# Crowdsec plugin

Crowdsec integration example with bunkerized-nginx. See the [bunkerized-nginx-crowdsec](https://github.com/bunkerity/bunkerized-nginx-crowdsec) repository for more information.

## Preamble

This example uses a bunkerized-nginx plugin, you can have a look at the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/plugins.html) to get more information about plugins.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/crowdsec/architecture.png?raw=true" />

## Configuration

First of all you will need to get a bouncer key, you can use the **bouncer_key.sh** to generate one.

Then you can clone the bunkerized-nginx-crowdsec plugin and edit the **plugin.json** file.

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/crowdsec/docker-compose.yml).
