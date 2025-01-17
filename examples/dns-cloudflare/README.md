Please have a look at the [certbot-dns-cloudflare documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit Cloudflare credentials in the compose file (generate using https://dash.cloudflare.com/?to=/:account/profile/api-tokens)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
