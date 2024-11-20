Please have a look at the [certbot-dns-google documentation](https://certbot-dns-google.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit Mandatory Google credentials in the compose file (generate using https://console.cloud.google.com/apis/credentials) (The other optional credentials have the default values: type, auth_uri, token_uri, auth_provider_x509_cert_url)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
