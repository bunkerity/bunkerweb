Please have a look at the [certbot-dns-route53 documentation](https://certbot-dns-route53.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit AWS credentials in the compose file (generate using https://console.aws.amazon.com/iam/home?#/security_credentials)
- Run your services, the scheduler will take care of the rest : `docker-compose up -d`
