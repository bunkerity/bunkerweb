# BunkerWeb with DeSEC DNS Challenge

Please have a look at the [certbot-dns-desec documentation](https://certbot-dns-desec.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [DeSEC](https://desec.io) if you don't already have one
2. Make sure your domains are managed by DeSEC
3. Generate an auth token at https://desec.io/tokens
4. Edit domains in the compose file
5. Edit DeSEC credentials in the compose file using the auth token you generated
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: DeSEC is a free and privacy-focused DNS hosting service. Make sure your domain's nameservers are configured to use DeSEC's nameservers.
