Please have a look at the [certbot-dns-ovh documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit OVH credentials in ovh.ini file (generate using https://eu.api.ovh.com/createToken/)
- Run certbot only and wait for certificate to be generated : `docker-compose up -d mycertbot`
- When certificates are generated, run your services : `docker-compose up -d`
