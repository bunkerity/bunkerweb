# Migrating from 1.4.X

!!! warning "Read this if you were a 1.4.X user"

    A lot of things changed since the 1.4.X releases. Container-based integrations stacks contain more services but, trust us, fundamental principles of BunkerWeb are still there. You will find ready to use boilerplates for various integrations in the [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.5.0/misc/integrations) folder of the repository.

## Scheduler

Back to the 1.4.X releases, jobs (like Let's Encrypt certificate generation/renewal or blacklists download) **were executed in the same container as BunkerWeb**. For the purpose of [separation of concerns](https://en.wikipedia.org/wiki/Separation_of_concerns), we decided to create a **separate service** which is now responsible for managing jobs.

Called **Scheduler**, this service also generates the final configuration used by BunkerWeb and acts as an intermediary between autoconf and BunkerWeb. In other words, the scheduler is the **brain of the BunkerWeb 1.5.X stack**.

You will find more information about the scheduler [here](concepts.md#scheduler).

## Database

BunkerWeb configuration is **no more stored in a plain file** (located at `/etc/nginx/variables.env` if you didn't know it). That's it, we now support a **fully-featured database as a backend** to store settings, cache, custom configs, ... 🥳

Using a real database offers many advantages :

- Backup of the current configuration
- Usage with multiple services (scheduler, web UI, ...)
- Upgrade to a new BunkerWeb version

Please note that we actually support, **SQLite**, **MySQL**, **MariaDB** and **PostgreSQL** as backends.

You will find more information about the database [here](concepts.md#database).

## Redis

When BunkerWeb 1.4.X was used in cluster mode (Swarm or Kubernetes integrations), **data were not shared among the nodes**. For example, if an attacker was banned via the "bad behavior" feature on a specific node, **he could still connect to the other nodes**.

Security is not the only reason to have a shared data store for clustered integrations, **caching** is also another one. We can now **store results** of time-consuming operations like (reverse) dns lookups so they are **available for other nodes**.

We actually support **Redis** as a backend for the shared data store.

See the list of [redis settings](settings.md#redis) and the corresponding documentation of your integration for more information.

## Default values and new settings

The default value of some settings have changed and we have added many other settings, we recommend you read the [security tuning](security-tuning.md) and [settings](settings.md) sections of the documentation.