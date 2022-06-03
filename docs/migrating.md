# Migrating from bunkerized

!!! warning "Read this if you were a bunkerized user"

    A lot of things have changed since the last bunkerized release. If you want to an upgrade, which we recommend you to do because BunkerWeb is by far better than bunkerized, please read carefully this section and also the whole documentation.

## Volumes

When using container-based integrations like [Docker](/integrations/#docker), [Docker autoconf](/integrations/#docker-autoconf), [Swarm](/integrations/#swarm) or [Kubernetes](/integrations/#kubernetes), volumes for storing data like certificates, cache or custom configurations has changed. We now have a single "bw-data" volume which contains everything and should be easier to manage than bunkerized.

## Removed features

We decided to drop the following features :

- Authelia : we will make an official [plugin](/plugins) for that
- Blocking "bad" referrers : we may add it again in the future
- ROOT_SITE_SUBFOLDER : we will need to redesign this in the future

## Replaced BLOCK_*, WHITELIST_* and BLACKLIST_* settings

The blocking mechanisms has been completely redesigned. We have detected that a lot of false positives came from the default blacklists hardcoded into bunkerized. That's why we decided to give the users the choice of their blacklists (and also whitelists) for IP address, reverse DNS, user-agent, URI and ASN, see the [Blacklisting and whitelisting](/security-tuning/#blacklisting-and-whitelisting) section of the [security tuning](/security-tuning).

## Changed WHITELIST_USER_AGENT setting behavior

The new behavior of the WHITELIST_USER_AGENT setting is to **disable completely security checks** if the User-Agent value of a client match any of the patterns. In bunkerized it was used to ignore specific User-Agent values when `BLOCK_USER_AGENT` was set to `yes` to avoid false positives. You can choose the blacklist of your choice to avoid FP (see previous section).

## Changed PROXY_REAL_IP_* settings

To avoid any confusion between reverse proxy and real IP, we decided to renamed the `PROXY_REAL_IP_*` settings, you will find more information on the subject [here](/quickstart-guide/#behind-load-balancer-or-reverse-proxy).

## Default values and new settings

The default value of settings may have changed and we have added many other settings, we recommend you to read the [security tuning](/security-tuning) and [settings](/settings) sections of the documentation.