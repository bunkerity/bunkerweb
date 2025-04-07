# BunkerWeb with DNSimple DNS Challenge

Please have a look at the [certbot-dns-dnsimple documentation](https://certbot-dns-dnsimple.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [DNSimple](https://dnsimple.com/) if you don't already have one
2. Make sure your domains are managed by DNSimple
3. Generate an OAuth token in your DNSimple account:
   - Log in to your DNSimple account
   - Go to "Account" > "API Access"
   - Create a new OAuth token
4. Edit domains in the compose file
5. Edit DNSimple credentials in the compose file using the OAuth token you generated
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: DNSimple provides DNS hosting services with a focus on simplicity and automation. Ensure your domain's nameservers are properly configured to use DNSimple.
