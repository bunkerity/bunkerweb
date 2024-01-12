Please have a look at the [certbot-dns-route53 documentation](https://certbot-dns-route53.readthedocs.io/en/stable/) first.

Procedure :

- Edit domains in the compose file
- Edit AWS credentials in aws.ini file (generate using https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/access-control-overview.html)
- Run certbot only and wait for certificates to be generated : `docker-compose up -d mycertbot`
- When certificates are generated, run your services : `docker-compose up -d`
