# BunkerWeb with DNS Made Easy DNS Challenge

Please have a look at the [certbot-dns-dnsmadeeasy documentation](https://certbot-dns-dnsmadeeasy.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [DNS Made Easy](https://dnsmadeeasy.com/) if you don't already have one
2. Make sure your domains are managed by DNS Made Easy
3. Get your API credentials:
   - Log in to your DNS Made Easy account
   - Go to "Account" > "API Keys"
   - Create or use an existing API key and note down both the API key and Secret key
4. Edit domains in the compose file
5. Edit DNS Made Easy credentials in the compose file using your API key and Secret key
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: DNS Made Easy is a managed DNS provider focused on performance and reliability. Make sure your domain's nameservers are properly configured to use DNS Made Easy's nameservers.
