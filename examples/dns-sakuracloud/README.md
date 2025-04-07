# BunkerWeb with SakuraCloud DNS Challenge

Please have a look at the [certbot-dns-sakuracloud documentation](https://certbot-dns-sakuracloud.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [SakuraCloud](https://cloud.sakura.ad.jp/) if you don't already have one
2. Make sure your domains are managed by SakuraCloud DNS
3. Get your API credentials:
   - Log in to your SakuraCloud control panel
   - Navigate to the API settings section
   - Create a new API key pair and note down the API token and API secret
4. Edit domains in the compose file
5. Edit SakuraCloud credentials in the compose file using your API token and API secret
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: SakuraCloud is a Japanese IaaS provider offering DNS hosting services. Make sure your domain's nameservers are properly configured to use SakuraCloud DNS servers.
