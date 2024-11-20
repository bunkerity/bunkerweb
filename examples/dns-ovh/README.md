Please have a look at the [certbot-dns-ovh documentation](https://certbot-dns-ovh.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit OVH credentials in the compose file (generate using https://eu.api.ovh.com/createToken/)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
