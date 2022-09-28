# Migrating from bunkerized

!!! warning "Read this if you were a bunkerized user"

    A lot of things changed since the last bunkerized release. If you want to do an upgrade, which we recommend you do because BunkerWeb is by far, better than bunkerized. Please read carefully this section as well as the whole documentation.

## Volumes

When using container-based integrations like [Docker](/1.4/integrations/#docker), [Docker autoconf](/1.4/integrations/#docker-autoconf), [Swarm](/1.4/integrations/#swarm) or [Kubernetes](/1.4/integrations/#kubernetes), volumes for storing data like certificates, cache or custom configurations have changed. We now have a single "bw-data" volume which contains everything and should be easier to manage than bunkerized.

## Removed features

We decided to drop the following features :

- Blocking "bad" referrers : we may add it again in the future
- ROOT_SITE_SUBFOLDER : we will need to redesign this in the future

## Changed Authelia support

Instead of supporting only Authelia, we decided to support generic auth request settings. See the new [authelia example](https://github.com/bunkerity/bunkerweb/tree/master/examples/authelia) and [auth request documentation](https://docs.bunkerweb.io/1.4/security-tuning/#auth-request) for more information.

## Replaced BLOCK_\*, WHITELIST_\* and BLACKLIST_\* settings

The blocking mechanisms have been completely redesigned. We have detected that a lot of false positives came from the default blacklists hardcoded into bunkerized. That's why we now give users the possibility of choosing their own blacklists (and also whitelists). For IP address, reverse DNS, user-agent, URI and ASN, see the [Blacklisting and whitelisting](/1.4/security-tuning/#blacklisting-and-whitelisting) section of the [security tuning](/1.4/security-tuning).

## Changed WHITELIST_USER_AGENT setting behavior

The new behavior of the WHITELIST_USER_AGENT setting is to **disable completely security checks** if the User-Agent value of a client matches any of the patterns. In bunkerized it was used to ignore specific User-Agent values when `BLOCK_USER_AGENT` was set to `yes` to avoid false positives. You can select the blacklist of your choice to avoid FP (see previous section).

## Changed PROXY_REAL_IP_* settings

To avoid any confusion between reverse proxy and real IP, we decided to rename the `PROXY_REAL_IP_*` settings, you will find more information on the subject [here](/1.4/quickstart-guide/#behind-load-balancer-or-reverse-proxy).

## Default values and new settings

The default value of some settings have changed and we have added many other settings, we recommend you read the [security tuning](/1.4/security-tuning) and [settings](/1.4/settings) sections of the documentation.