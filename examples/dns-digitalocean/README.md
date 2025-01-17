Please have a look at the [certbot-dns-digitalocean documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit DigitalOcean credentials in the compose file (generate using https://cloud.digitalocean.com/settings/api/tokens)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
