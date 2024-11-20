Please have a look at the [certbot-dns-rfc2136 documentation](https://certbot-dns-rfc2136.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit RFC2136 credentials in the compose file according to the [RFC2136](https://tools.ietf.org/html/rfc2136) standard
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
