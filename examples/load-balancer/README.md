# Load balancer

Simple example on how to load balance requests to multiple backends.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/load-balancer/architecture.png?raw=true" />

## Configuration

Edit the custom `upstream` directive in the **http-confs/upstream.conf** file according to your use case.

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/load-balancer/docker-compose.yml).
