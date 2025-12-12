# API

## Rôle de l’API

L’API BunkerWeb est la couche de contrôle pour gérer instances, services, bans, jobs, plugins et configurations. Elle tourne sous FastAPI derrière Gunicorn et doit rester sur un réseau de confiance. Docs interactives : `/docs` (ou `<API_ROOT_PATH>/docs`), schéma OpenAPI : `/openapi.json`.

!!! warning "Gardez-la privée"
    Ne l’exposez pas à Internet. Restez sur un réseau interne, restreignez les IP sources et imposez l’authentification.

## Checklist sécurité

- Réseau : écoute interne, `API_WHITELIST_IPS` actif ou filtrage amont.
- Auth : définir `API_USERNAME`/`API_PASSWORD`, éventuellement `API_TOKEN` en secours.
- Chemin : avec un reverse proxy, définir `API_ROOT_PATH` et le refléter.
- Ratelimiting : laisser activé, `/auth` a son plafond dédié.
- TLS : terminer au proxy ou `API_SSL_ENABLED=yes` avec certificats.

## Exécution

- Docker/Compose ou image tout-en-un, cf. `docs/api.md` anglaise.
- Paquets Linux : service `bunkerweb-api.service`, logs sous `/var/log/bunkerweb/api.log`.

## Authentification & permissions

- `/auth` émet des Biscuit ; Basic, formulaire, JSON ou Bearer égal à `API_TOKEN`.
- Admin peut aussi passer en Basic direct.
- Biscuit embarque utilisateur, IP cliente, rôle/ACL, TTL (`API_BISCUIT_TTL_SECONDS`, `0/off` désactive).

## Limitation de débit

Activée par défaut avec deux chaînes : `API_RATE_LIMIT` (global, défaut `100r/m`) et `API_RATE_LIMIT_AUTH` (défaut `10r/m` ou `off`). Formats acceptés : style NGINX (`3r/s`, `40r/m`, `200r/h`) ou formes verboses (`100/minute`, `200 per 30 minutes`).

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML en ligne ou chemin de fichier)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Stockage mémoire ou Redis/Valkey si `USE_REDIS=yes` + `REDIS_*` (Sentinel supporté)

Stratégies (propulsées par `limits`) :

- `fixed-window` (défaut) : le seau redémarre à chaque borne d’intervalle ; léger et suffisant pour des plafonds grossiers.
- `moving-window` : vraie fenêtre glissante avec horodatages précis ; plus douce mais plus coûteuse en opérations de stockage.
- `sliding-window-counter` : hybride qui lisse avec des comptes pondérés de la fenêtre précédente ; plus léger que moving et plus doux que fixed.

Plus de détails et compromis : <https://limits.readthedocs.io/en/stable/strategies.html>

??? example "CSV en ligne"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "Fichier YAML"
    ```yaml
    API_RATE_LIMIT: 200r/m
    API_RATE_LIMIT_AUTH: 15r/m
    API_RATE_LIMIT_RULES:
      - path: "/auth"
        methods: "POST"
        rate: "10r/m"
      - path: "/instances*"
        methods: "GET|POST"
        rate: "100r/m"
    ```

## Sources de configuration (priorité)

1. Variables d’environnement
2. Secrets sous `/run/secrets/<VAR>`
3. YAML `/etc/bunkerweb/api.yml`
4. Fichier env `/etc/bunkerweb/api.env`
5. Valeurs par défaut

## Paramètres clés (extrait)

- **Docs** : `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`
- **Auth** : `API_USERNAME`, `API_PASSWORD`, `API_TOKEN`, `API_ACL_BOOTSTRAP_FILE`
- **Biscuit** : `API_BISCUIT_TTL_SECONDS`, `CHECK_PRIVATE_IP`
- **Liste blanche** : `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`
- **Limitation** : `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_HEADERS_ENABLED`, `API_RATE_LIMIT_STORAGE_OPTIONS`
- **Redis/Valkey** : `USE_REDIS`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_SSL`, variables Sentinel
- **Réseau/TLS** : `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`
