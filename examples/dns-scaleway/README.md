# BunkerWeb with Scaleway DNS Challenge

Please have a look at the [certbot-dns-scaleway documentation](https://certbot-dns-scaleway.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [Scaleway](https://www.scaleway.com/) if you don't already have one
2. Make sure your domains are managed by Scaleway DNS
3. Get your Application token:
   - Log in to your Scaleway console
   - Go to your profile by clicking on your avatar in the top-right corner
   - Select "Credentials"
   - In the "API Keys" section, create a new API key
   - Make sure to note down the token (it won't be shown again)
4. Edit domains in the compose file
5. Edit Scaleway credentials in the compose file using your API token
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: Scaleway is a cloud provider offering DNS management services. Make sure your domain's nameservers are properly configured to use Scaleway DNS servers.
