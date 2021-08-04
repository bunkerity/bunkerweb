# Swarm wit hredis

Basic examples on how to deploy and use bunkerized-nginx within a Docker Swarm cluster and use redis to distribute the blacklists. See the [Docker Swarm](#TODO) section of the documentation for more information.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/swarm-redis/architecture.png?raw=true" />

## Swarm

This example uses two overlay networks needed by the services :

```shell
$ docker network create -d overlay --attachable net_config
$ docker network create -d overlay --attachable net_services
```

First you need to create the redis service : see [redis.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/redis.yml).

Then, it's time to setup bunkerized-nginx and the autoconf with Swarm mode activated : see [nginx-autoconf.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/nginx-autoconf.yml).

Then you can add and delete your web services and autoconf will automatically generate the configuration based on your labels : see [services.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/services.yml).
