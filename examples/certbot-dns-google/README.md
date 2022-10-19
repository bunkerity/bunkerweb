Please have a look at the [certbot-dns-google documentation](https://certbot-dns-google.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit Google credentials in google.json file (generate using https://developers.google.com/identity/protocols/oauth2/service-account#creatinganaccount)
- Run certbot only and wait for certificates to be generated : `docker-compose up -d mycertbot`
- When certificates are generated, run your services : `docker-compose up -d`
