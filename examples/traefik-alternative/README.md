# Traefik alternative

Traefik (pronounced traffic) is a modern HTTP reverse proxy and load balancer that makes deploying microservices easy. Traefik integrates with your existing infrastructure components (Docker, Swarm mode, Kubernetes, Marathon, Consul, Etcd, Rancher, Amazon ECS, ...) and configures itself automatically and dynamically. See [documentation](https://doc.traefik.io/traefik/) and [GitHub repo](https://github.com/traefik/traefik) for more information.

You can easily switch from Traefik to bunkerized-nginx if you are more concerned about security.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/traefik-alternative/architecture.png?raw=true" />

## Autoconf

See [docker-compose-bunkerized.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/traefik-alternative/docker-compose-bunkerized.yml) which is the equivalent of [docker-compose-traefik.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/traefik-alternative/docker-compose-traefik.yml).
