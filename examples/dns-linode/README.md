Please have a look at the [certbot-dns-linode](https://certbot-dns-linode.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit Linode credentials in the compose file (generate using https://cloud.linode.com/profile/tokens)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
