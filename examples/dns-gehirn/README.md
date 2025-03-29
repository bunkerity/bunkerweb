# BunkerWeb with Gehirn DNS Challenge

Please have a look at the [certbot-dns-gehirn documentation](https://certbot-dns-gehirn.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [Gehirn DNS](https://www.gehirn.jp/gis/) if you don't already have one
2. Make sure your domains are managed by Gehirn DNS
3. Get your API credentials:
   - Log in to your Gehirn account
   - Go to the DNS service control panel
   - Create an API token and secret (follow Gehirn's documentation for the exact steps)
4. Edit domains in the compose file
5. Edit Gehirn credentials in the compose file using your API token and secret
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: Gehirn is a Japanese cloud services provider offering DNS hosting services. Make sure your domain's nameservers are properly configured to use Gehirn DNS servers.
