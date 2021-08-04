# Swarm

Basic examples on how to deploy and use bunkerized-nginx within a Docker Swarm cluster. See the [Docker Swarm](#TODO) section of the documentation for more information.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/swarm/architecture.png?raw=true" />

## Swarm

This example uses two overlay networks needed by the services :

```shell
$ docker network create -d overlay --attachable net_config
$ docker network create -d overlay --attachable net_services
```

First you will need to setup bunkerized-nginx and the autoconf with Swarm mode activated : see [nginx-autoconf.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm/nginx-autoconf.yml).

Then you can add and delete your web services and autoconf will automatically generate the configuration based on your labels : see [services.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm/services.yml).
