# BunkerWeb + Authentik (Forward Auth, Domain Level)

This example protects two demo applications (`app1` and `app2`) behind a single [Authentik](https://goauthentik.io/) instance using the [Forward auth (domain level)](https://goauthentik.io/docs/providers/proxy/forward_auth) mode. [BunkerWeb](https://www.bunkerweb.io) sits in front of everything as the reverse proxy and Web Application Firewall, calls the Authentik outpost on each request via `auth_request`, and redirects unauthenticated users to the Authentik sign-in flow.

The Authentik stack (`server`, `worker`, `postgresql`) tracks the [upstream docker-compose reference](https://docs.goauthentik.io/install-config/install/docker-compose) for `2026.2+` and no longer needs Redis. An Authentik [blueprint](blueprints/bunkerweb.yaml) auto-provisions the forward-auth providers, applications and the embedded outpost binding, so both apps work out of the box without any manual click-through in the Authentik admin UI.

The sign-in redirect URL is domain-agnostic: it uses the NGINX variables `$scheme` and `$host` (`$scheme://$host/outpost.goauthentik.io/start?rd=...`) instead of a hardcoded hostname, so the exact same `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` value can be reused for every protected service. Note that `401` must be removed from `INTERCEPTED_ERROR_CODES` (as done here) so Authentik's `401` reaches the sign-in redirect instead of being handled by BunkerWeb's error pages.

Supported integrations: [`docker-compose.yml`](docker-compose.yml), [`autoconf.yml`](autoconf.yml) and [`kubernetes.yml`](kubernetes.yml).

See the [BunkerWeb documentation](https://docs.bunkerweb.io) for the full configuration reference.
