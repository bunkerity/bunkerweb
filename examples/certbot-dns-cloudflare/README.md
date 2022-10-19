Please have a look at the [certbot-dns-cloudflare documentation](https://certbot-dns-cloudflare.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit CloudFlare credentials in cloudflare.ini file (generate using https://dash.cloudflare.com/?to=/:account/profile/api-tokens)
- Run certbot only and wait for certificates to be generated : `docker-compose up -d mycertbot`
- When certificates are generated, run your services : `docker-compose up -d`
