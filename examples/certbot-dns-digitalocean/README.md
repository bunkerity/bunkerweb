Please have a look at the [certbot-dns-digitalocean documentation](https://certbot-dns-digitalocean.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit DigitalOcean credentials in digitalocean.ini file (generate using https://cloud.digitalocean.com/settings/api/tokens)
- Run certbot only and wait for certificates to be generated : `docker-compose up -d mycertbot`
- When certificates are generated, run your services : `docker-compose up -d`
