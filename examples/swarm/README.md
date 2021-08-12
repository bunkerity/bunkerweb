# Swarm

Basic examples on how to deploy and use bunkerized-nginx within a Docker Swarm cluster. See the [Docker Swarm integration section of the documentation](https://bunkerized-nginx.readthedocs.io/en/latest/integrations.html#docker-swarm) for more information.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/swarm/architecture.png?raw=true" />

## Swarm

We assume that you've installed bunkerized-nginx and the autoconf on service on your Docker Swarm cluster.

Then you can add and delete your web services and autoconf will automatically generate the configuration based on your labels : see [services.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/swarm/services.yml).
