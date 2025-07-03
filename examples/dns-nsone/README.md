# BunkerWeb with NS1 (NSONE) DNS Challenge

Please have a look at the [certbot-dns-nsone documentation](https://certbot-dns-nsone.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [NS1](https://ns1.com/) if you don't already have one
2. Make sure your domains are managed by NS1
3. Get your API key:
   - Log in to your NS1 account
   - Go to "Account Settings" > "API Keys"
   - Create a new API key with appropriate permissions (at minimum, DNS zones and records management)
   - Note down the API key
4. Edit domains in the compose file
5. Edit NS1 credentials in the compose file using your API key
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: NS1 is a managed DNS service provider with advanced traffic management features. Make sure your domain's nameservers are properly configured to use NS1's nameservers.
