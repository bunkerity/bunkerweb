# BunkerWeb with LuaDNS DNS Challenge

Please have a look at the [certbot-dns-luadns documentation](https://certbot-dns-luadns.readthedocs.io/en/stable/) first.

## Procedure:

1. Create an account on [LuaDNS](https://www.luadns.com/) if you don't already have one
2. Make sure your domains are managed by LuaDNS
3. Get your API credentials:
   - Log in to your LuaDNS account
   - Go to "Settings" > "API Access"
   - Create an API token if you don't already have one
   - Note your account email and the API token
4. Edit domains in the compose file
5. Edit LuaDNS credentials in the compose file using your account email and API token
6. Run your services, the scheduler will take care of the rest: `docker-compose up -d`

Note: LuaDNS is a DNS hosting service that allows configuration using Lua scripts. Make sure your domain's nameservers are properly configured to use LuaDNS nameservers.
