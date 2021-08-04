# Authelia

Authelia is an open-source authentication and authorization server providing two-factor authentication and single sign-on (SSO) for your applications via a web portal. See [website](https://www.authelia.com/) and [GitHub repo](https://github.com/authelia/authelia) for more information.

## Preamble

We will assume that you already have some basic knownledges about Authelia. If that's not the case, you should read their [documentation](https://www.authelia.com/) first.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/authelia/architecture.png?raw=true" />

## Configuration

First of all, you will need to edit the configuration files inside the authelia folder (e.g. : domains, DB backend, email notifier, ...).

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/authelia/docker-compose.yml).
