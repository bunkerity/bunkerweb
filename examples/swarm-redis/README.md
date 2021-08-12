# Swarm with redis

Basic examples on how to deploy and use bunkerized-nginx within a Docker Swarm cluster and use redis to distribute the blacklists. See the [Docker Swarm integration section of the documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker-swarm) for more information.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/swarm-redis/architecture.png?raw=true" />

## Swarm

This example uses two overlay networks needed by the services :

```shell
$ docker network create -d overlay --attachable config-net
$ docker network create -d overlay --attachable services-net
```

First you need to create the redis service : see [redis.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/redis.yml).

Then, it's time to setup bunkerized-nginx and the autoconf with Swarm mode activated : see [nginx-autoconf.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/nginx-autoconf.yml).

Then you can add and delete your web services and autoconf will automatically generate the configuration based on your labels : see [services.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm-redis/services.yml).
