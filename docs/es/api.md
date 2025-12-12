# API

## Rol de la API

La API de BunkerWeb es el plano de control para gestionar instancias, servicios, bloqueos, trabajos, plugins y configuraciones. Corre con FastAPI detrás de Gunicorn y debe vivir en una red de confianza. Docs interactivas: `/docs` (o `<API_ROOT_PATH>/docs`), OpenAPI: `/openapi.json`.

!!! warning "Manténla privada"
    No la expongas a Internet. Mantenla interna, restringe IP de origen y exige autenticación.

## Checklist de seguridad

- Red: escucha interna y `API_WHITELIST_IPS` activo o filtrado upstream.
- Auth: define `API_USERNAME`/`API_PASSWORD`; opcional `API_TOKEN` como emergencia.
- Ruta: con reverse proxy, establece y refleja `API_ROOT_PATH`.
- Limitación: déjala activada; `/auth` tiene su propio límite.
- TLS: termina en el proxy o usa `API_SSL_ENABLED=yes` con certificados.

## Ejecución

- Docker/Compose o imagen all-in-one según `docs/api.md` en inglés.
- Paquetes Linux: servicio `bunkerweb-api.service`, logs en `/var/log/bunkerweb/api.log`.

## Autenticación y permisos

- `/auth` entrega Biscuit; acepta Basic, formulario, JSON o Bearer igual a `API_TOKEN`.
- El admin puede usar Basic directo.
- Biscuit incluye usuario, IP cliente, rol/ACL y TTL (`API_BISCUIT_TTL_SECONDS`, `0/off` lo desactiva).

## Limitación de velocidad

Activa por defecto con dos cadenas: `API_RATE_LIMIT` (global, por defecto `100r/m`) y `API_RATE_LIMIT_AUTH` (por defecto `10r/m` u `off`). Admite formato NGINX (`3r/s`, `40r/m`, `200r/h`) o formas verbosas (`100/minute`, `200 per 30 minutes`).

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML en línea o ruta a archivo)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Almacenamiento en memoria o Redis/Valkey si `USE_REDIS=yes` + `REDIS_*` (Sentinel soportado)

Estrategias (provistas por `limits`):

- `fixed-window` (predeterminado): el bucket se reinicia en cada borde de intervalo; barato y suficiente para límites gruesos.
- `moving-window`: ventana rodante real con marcas de tiempo precisas; más suave pero más costosa en operaciones de almacenamiento.
- `sliding-window-counter`: híbrido que suaviza con conteos ponderados de la ventana previa; más liviano que moving y más suave que fixed.

Más detalles y trade-offs: <https://limits.readthedocs.io/en/stable/strategies.html>

??? example "CSV en línea"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "Archivo YAML"
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

## Fuentes de configuración (prioridad)

1. Variables de entorno
2. Secrets en `/run/secrets/<VAR>`
3. YAML `/etc/bunkerweb/api.yml`
4. Archivo env `/etc/bunkerweb/api.env`
5. Valores por defecto

## Ajustes clave (resumen)

- **Docs**: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`
- **Auth**: `API_USERNAME`, `API_PASSWORD`, `API_TOKEN`, `API_ACL_BOOTSTRAP_FILE`
- **Biscuit**: `API_BISCUIT_TTL_SECONDS`, `CHECK_PRIVATE_IP`
- **Lista blanca**: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`
- **Límites**: `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_HEADERS_ENABLED`, `API_RATE_LIMIT_STORAGE_OPTIONS`
- **Redis/Valkey**: `USE_REDIS`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_SSL`, variables Sentinel
- **Red/TLS**: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`
