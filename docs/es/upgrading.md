# Actualización

!!! warning "Recrear el contenedor de la interfaz sin un `/data` persistente pierde el 2FA"
    `docker compose down` y luego `up` sustituye el sistema de ficheros del contenedor `bw-ui`, y allí viven las claves que descifran cada secreto TOTP almacenado. Sin un volumen montado en `/data`, la inscripción del administrador se descarta y todos los usuarios deben inscribirse de nuevo. Compruebe **antes** de actualizar que su servicio `bw-ui` tiene uno — vea [El 2FA desaparece al recrear el contenedor](web-ui.md).

## Actualización desde 1.6.X

### Cambios importantes {#breaking-changes}

!!! warning "`REDIS_SSL_VERIFY` ahora tiene por defecto `yes`"

    El cliente Redis/Valkey aceptaba **cualquier** certificado cuando `REDIS_SSL` estaba activado: el valor por defecto documentado para `REDIS_SSL_VERIFY` era `yes`, pero el valor por defecto real era `no`, por lo que TLS se negociaba sin verificar nunca el servidor. El código ahora coincide con la documentación.

    Esto solo te afecta si se cumplen **todas** estas condiciones: `REDIS_SSL: "yes"`, el servidor Redis o Valkey presenta un certificado autofirmado o no confiable de otro modo, y nunca has establecido `REDIS_SSL_VERIFY` explícitamente. En ese caso, la conexión falla tras la actualización.

    Confía en la CA del servidor, o restaura explícitamente el comportamiento anterior:

    ```yaml
    REDIS_SSL_VERIFY: "no"
    ```

!!! warning "El broker de jobs ahora es una instancia separada del datastore de la WAF"

    BunkerWeb usa Redis/Valkey para dos tareas no relacionadas, que necesitan configuraciones contradictorias:

    | Rol | Ajuste | Por qué |
    |------|---------|-----|
    | **Broker de jobs** (`CELERY_BROKER_URL`) | `maxmemory-policy noeviction` | Guarda los leases de corrección que evitan que dos workers envíen configuraciones a la vez. Son claves *con* TTL, así que cualquier política `volatile-*` puede descartarlas a mitad de vuelo. |
    | **Datastore de la WAF** (`USE_REDIS` / `REDIS_*`) | `maxmemory-policy volatile-lru` *(recomendado)* | Limita su memoria y permite la expulsión: perder contadores transitorios cuesta menos que rechazar escrituras. No es obligatorio — un Redis sin límite nunca expulsa claves y también sirve —, pero esta es la configuración habitual del almacén y la que el broker no debe tener. |

    `maxmemory-policy` es un ajuste por servidor, nunca por base de datos, así que una sola instancia no
    puede cumplir ambos roles — apuntar los dos roles a distintos números de base de datos del mismo
    servidor no los separa. Los stacks con varios contenedores ejecutan un `bw-jobs-broker` dedicado;
    la imagen AIO supervisa un broker separado en loopback, puerto `6380`, y el instalador de Linux
    puede aprovisionar un servicio `bunkerweb-broker` a partir del puerto `6380`.

    **Si actualizas con el instalador, esto se gestiona por ti.** Aprovisiona el broker, escribe
    `CELERY_BROKER_URL` en `/etc/bunkerweb/variables.env` y deja intacto un Redis de la distro sin
    tocar (sin `maxmemory` establecido, nunca se descarta nada, así que nunca estuvo roto).

    **Si actualizas con `apt`/`dnf` normal y has establecido a mano una contraseña de Redis**, te ves
    afectado y los jobs en segundo plano ya están fallando — en silencio. El worker y la API usan por
    defecto un `redis://127.0.0.1:6379/0` sin autenticar, así que un servidor protegido con contraseña
    responde `NOAUTH`: `POST /jobs/dispatch` devuelve 502 y el worker permanece `active` sin consumir
    nada. En ese estado no hay renovación de certificados, ni actualización de listas de bloqueo, ni
    backup. Compruébalo con:

    ```bash
    journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'
    ```

    El mismo diagnóstico, también para contenedores, aparece en
    [Los jobs en segundo plano nunca se ejecutan](troubleshooting.md#background-jobs).

    **Comprueba que sea un broker de jobs dedicado y sin expulsión de claves antes de corregir la autenticación.**
    Si el puerto `6379` sirve un almacén WAF que expulsa claves, aprovisiona un broker separado con
    el [instalador de Linux](integrations.md#script-de-instalacion-facil) o configúralo tú mismo con
    `maxmemory-policy noeviction`. Usa la dirección y el puerto reales de ese broker. El ejemplo
    con `6379` de abajo solo se aplica a un Redis de la distribución dedicado a los jobs; añadir
    una contraseña a un almacén que expulsa claves no lo convierte en un broker seguro.

    Después, asigna al broker sus propias credenciales en `/etc/bunkerweb/variables.env` — una sola
    escritura cubre ambos componentes, porque el worker y la API leen ese archivo antes que el suyo propio:

    ```bash
    CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0
    ```

    ```bash
    systemctl restart bunkerweb-worker bunkerweb-api
    ```

    TLS se admite con el esquema `rediss://`. **Establece `ssl_cert_reqs` explícitamente** — una URL
    `rediss://` desnuda negocia TLS sin verificar el certificado del servidor:

    ```bash
    CELERY_BROKER_URL=rediss://:<password>@broker.example.com:6379/0?ssl_cert_reqs=required
    ```

!!! warning "El worker de Celery no estaba habilitado en algunas instalaciones"

    `bunkerweb-worker` ejecuta cada job que despacha el scheduler. En instalaciones donde el instalador
    aplazó el arranque de servicios — `--redis`, una base de datos externa, CrowdSec, resolutores DNS
    personalizados, y toda instalación `--manager` — nunca se habilitó, así que el stack arrancaba sano
    y no ejecutaba ningún job en segundo plano. El instalador ahora lo habilita junto al scheduler en
    esos casos. Verifica tras actualizar:

    ```bash
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    ```

    Si no existe o está inactivo, consulta
    [Los jobs en segundo plano nunca se ejecutan](troubleshooting.md#background-jobs).

!!! warning "Los stacks Docker, autoconf y Kubernetes necesitan tres componentes nuevos"

    Un stack 1.6 incluye `bunkerweb` y `bw-scheduler`. 1.7 también necesita una **API**, un **Worker**
    y un **broker de jobs**: `bw-api`, `bw-worker` y `bw-jobs-broker` en Compose, o `bunkerweb-api`,
    `bunkerweb-worker` y `bunkerweb-jobs-broker` en Kubernetes. El Worker ejecuta los jobs que el
    Scheduler ejecutaba en su propio proceso y el broker transporta los envíos entre ambos. Cada
    componente BunkerWeb recibe `API_URL`, `API_TOKEN` y `CELERY_BROKER_URL`, y la instancia
    `bunkerweb` incorpora un volumen `bw-instance-data` en `/data`.

    Cambiar solo las etiquetas de imagen deja un stack que indica estar sano y **no ejecuta ningún
    job en segundo plano**: no renueva certificados, no actualiza listas de bloqueo ni realiza
    backups ([cómo detectarlo](troubleshooting.md#background-jobs)). Vuelve a desplegar desde el
    stack de referencia 1.7 de tu integración: [Docker](integrations.md#docker),
    [Docker autoconf](integrations.md#docker-autoconf), [Kubernetes](integrations.md#kubernetes) o
    [Swarm](integrations.md#swarm). Todos están en
    [`misc/integrations`](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/misc/integrations),
    con un archivo por motor de base de datos.

    **La imagen All-In-One no está afectada**: supervisa la API y el Worker dentro del contenedor
    y transporta sus jobs mediante un Redis integrado dedicado. Basta con sustituir el contenedor
    conservando `/data`, sin añadir componentes.

!!! warning "PostgreSQL: pasa primero por 1.6.x si la base de datos es anterior a 1.6.0"

    Una base de datos **PostgreSQL** creada o migrada por última vez antes de 1.6.0 no puede pasar
    directamente a 1.7. Toda la cadena de migraciones se ejecuta en una sola transacción, y la
    revisión que lleva la base a 1.6.1 abre una *segunda* conexión para eliminar una restricción de
    una tabla sobre la que la primera ya tiene un bloqueo exclusivo. La segunda espera un bloqueo
    que solo se libera al terminar la migración, y esta no puede terminar hasta que lo haga la
    segunda conexión. El detector de interbloqueos de PostgreSQL no lo detecta porque el titular
    espera un socket de cliente, no un bloqueo. No hay tiempo límite ni error: el Scheduler nunca
    termina de arrancar.

    Te afecta si esta instalación nunca ha ejecutado una versión 1.6.x. Puedes leer la revisión con:

    ```bash
    psql -d <database> -c 'SELECT version_num FROM alembic_version;'
    ```

    `f85e36780e55` es la revisión 1.6.0; cualquier revisión anterior en la cadena está afectada.
    Instala primero 1.6.14, deja que el Scheduler arranque y termine la migración y después actualiza
    a 1.7. SQLite, MariaDB y MySQL no están afectados: solo la revisión PostgreSQL abre esa segunda conexión.

!!! danger "Una ubicación con espacios en blanco, `;`, `{` o `}` se rechaza y vuelve a `/`"

    `REVERSE_PROXY_URL`, `GRPC_URL` y `REDIRECT_FROM` aceptaban cualquier valor en 1.6. Ahora rechazan
    los caracteres que permitirían salir del bloque `location` generado. Se sigue aceptando un
    prefijo `~ `, `~* `, `^~ ` o `= ` — el modificador de ubicación de NGINX —, pero ese espacio es
    el único permitido en todo el valor, incluido el final, y nunca se admiten `;`, `{` ni `}`.

    Un valor rechazado no impide generar la configuración. BunkerWeb registra una advertencia
    (`Ignoring variable REVERSE_PROXY_URL_1 : ...`) y conserva el valor predeterminado, `/` en los
    tres casos: la regla pasa a la raíz del sitio en lugar de la ruta configurada. Un caso habitual
    es una ubicación regex con un cuantificador, `^/v[0-9]{1,3}/`.

    Busca estos valores antes de actualizar en tus archivos Compose, `variables.env`, etiquetas
    de contenedor y anotaciones Kubernetes:

    ```bash
    grep -rInE '(REVERSE_PROXY_URL|GRPC_URL|REDIRECT_FROM)[A-Z_0-9]*[:=].*[;{}]' .
    ```

    Esto encuentra `;`, `{` y `}`, los casos habituales en una configuración 1.6. También se rechaza
    un espacio salvo el que separa un modificador inicial `~`, `~*`, `^~` o `=` de la ruta: revisa
    esos pocos casos manualmente.

    La búsqueda solo cubre archivos. Un valor configurado desde la interfaz o la API vive en la base
    de datos y no se revalida al generar la configuración ni al guardar un ajuste distinto: continúa
    funcionando tras la actualización y **nada te avisa**. Al modificar ese servicio hay tres comportamientos:

    - **Un payload JSON de ajustes se valida completo.** `POST`/`PATCH /services` y
      `PATCH /global_settings` comprueban **cada** clave enviada, haya cambiado o no. Por tanto,
      leer, modificar y reenviar un valor almacenado no válido provoca un `400` que indica la clave.
      Estas rutas usan claves sin prefijo: `REVERSE_PROXY_URL_1`, no
      `www.example.com_REVERSE_PROXY_URL_1`. Con `MULTISITE=no`, los tres ajustes son globales y
      la ruta afectada es `PATCH /global_settings`.
    - **Los guardados de la configuración completa comparan con la base de datos y omiten las
      claves sin cambios**: las páginas de servicios y ajustes globales, autoconf, la reconciliación
      del entorno del scheduler y `PUT /global_settings/config`. Abrir un servicio y guardarlo en
      la interfaz **no** revela el problema. Un valor de una *etiqueta* o de `variables.env` es
      distinto: autoconf y Configurator releen su fuente completa en cada ejecución, descartan el
      valor no válido con un mensaje y usan el predeterminado. Por eso importa la búsqueda anterior.
    - **Cuando la interfaz sí valida el campo**, porque lo editaste, no rechaza todo el guardado.
      Restaura ese campo al valor almacenado, muestra `Variable <key> is not valid.`, guarda el resto
      y ahora informa el propio guardado con un mensaje naranja a juego que indica cuántos valores
      se rechazaron, en lugar de un mensaje de éxito incondicional.

    Nada de esto localiza los valores almacenados. Revisa manualmente `REVERSE_PROXY_URL`, `GRPC_URL`
    y `REDIRECT_FROM` en los servicios gestionados desde la interfaz.

!!! warning "`GET /bans` ahora responde desde la base de datos"

    En 1.7 los bloqueos se guardan en la base de datos y sobreviven a los reinicios, por lo que
    `GET /bans` devuelve esa lista persistente. La respuesta anterior — los bloqueos aplicados por
    cada instancia en su memoria compartida — se conserva en `GET /bans/instances`. Una automatización
    1.6 que siga usando `GET /bans` no recibe un error, pero la respuesta significa otra cosa.
    Cambia la ruta de forma deliberada.

!!! info "`HTTP_PORT` y `HTTPS_PORT` ahora son ajustes por servicio"

    Han pasado de contexto `global` a `multisite`, así que `www.example.com_HTTPS_PORT=9443` se
    acepta donde 1.6 respondía "context of ... isn't multisite". Las configuraciones existentes se
    generan igual: un valor global sigue siendo el predeterminado de todos los servicios. Ahora
    cada servicio puede declarar su propia lista, que **sustituye** a la global para ese servicio,
    en lugar de ampliarla.

!!! warning "Swarm: `NAMESPACES` ahora también filtra las configuraciones personalizadas"

    Antes de 1.7, `NAMESPACES` filtraba la ruta de eventos del controlador de Swarm y su
    descubrimiento de servicios, pero **no** el descubrimiento de configuraciones: un objeto
    `docker config` global era recogido por cada autoconf del daemon, sin importar el namespace al
    que perteneciera. 1.7 aplica el filtro también a las configuraciones, que es lo que la
    integración de Docker ha hecho siempre. Si estableces `NAMESPACES` y tus objetos de
    configuración no llevan la etiqueta `bunkerweb.NAMESPACE`, esas configuraciones **dejan de
    aplicarse tras la actualización, sin ningún error** — un snippet personalizado con un bloque de
    permitir/denegar simplemente desaparece de la configuración generada.

    Etiqueta cada objeto de configuración que esperas que se aplique. Las configuraciones de Swarm
    son inmutables — `docker config` no tiene verbo `update` — así que cada una debe recrearse con
    un nuevo nombre y volver a asignarse con `docker service update --config-rm/--config-add`.
    Encuentra los objetos afectados antes de actualizar con:

    ```bash
    docker config ls -q | xargs -r docker config inspect --format '{{.Spec.Name}} {{.Spec.Labels}}'
    ```

!!! info "Docker Swarm vuelve a estar soportado en 1.7"

    La integración de Swarm se marcó como obsoleta en 1.6 y vuelve a estar soportada en 1.7. El
    stack publicado para 1.6 **no** arranca en 1.7: no lleva `bw-api` ni `bw-worker`, así que
    `bw-autoconf` espera indefinidamente una API que nunca se inicia y ningún job en segundo plano
    llega a ejecutarse. Vuelve a desplegar desde el [stack de referencia de 1.7](integrations.md#swarm)
    en lugar de editar el antiguo, y ten en cuenta los tres nuevos requisitos: una etiqueta de nodo
    `bw-state=true` para los servicios propietarios de volúmenes, `mode: global` en el servicio
    `bunkerweb`, y publicación de puertos con `mode: host`.

### Cambiar el broker de jobs de una imagen AIO anterior {#aio-broker-upgrade}

Esto se aplica a un **despliegue AIO 1.7 existente**, no a una instalación 1.6, que no tenía cola
Celery. Las primeras imágenes 1.7 deducían el broker de `REDIS_*`. Ahora el predeterminado es
`redis://127.0.0.1:6380/0`, un Redis separado con `noeviction` y persistencia AOF en `/data/broker`.
El almacén WAF conserva sus ajustes y archivos.

Si ya estableciste `CELERY_BROKER_URL` explícitamente, se conserva. Si usabas `REDIS_HOST`,
`REDIS_PASSWORD` o los ajustes TLS de Redis para seleccionar el broker, ahora solo afectan al
almacén WAF. Para conservar un broker externo, establece su `CELERY_BROKER_URL` completa, incluidas
credenciales y parámetros de verificación TLS. Un valor vacío se rechaza con el Worker habilitado.

Antes de cambiar el broker de un despliegue 1.7 en ejecución:

1. Detén las escrituras directas a la API, incluidas automatizaciones y otros operadores. Usa el
   [procedimiento de pausa para backups](#rolling-back-to-1614) para detener los envíos del scheduler
   y las escrituras de autoconf e interfaz, y esperar a que terminen la cola de jobs, el trabajo en
   curso y las confirmaciones de recarga pendientes. Solo activa la pausa; no ejecutes la reversión.
   La versión de destino es una etiqueta para la pausa, no una petición de migración.
2. Ejecuta esa pausa contra el broker y la API **anteriores**. En imágenes AIO antiguas una nueva
   shell no hereda la URL exportada por el entrypoint: proporciona a esa shell la
   `CELERY_BROKER_URL` real anterior y las credenciales de API. Si la API no detecta la pausa o el
   vaciado agota el tiempo límite, resuélvelo antes de cambiar.
3. Mantén la pausa hasta detener el contenedor antiguo. Recréalo con el mismo volumen `/data` y
   el nuevo valor predeterminado o la URL explícita del broker externo. No se copian claves de cola
   entre brokers ni se eliminan los datos del Redis WAF anterior.
4. Comprueba la salud del contenedor y que un job enviado finaliza en la página Jobs antes de
   reanudar las automatizaciones. Una pausa obsoleta en un broker externo anterior puede liberarse
   con el comando de pausa existente o dejarse caducar.

El nuevo broker arranca antes del Worker y se detiene después. Su AOF sobrevive a los reinicios
si conservas `/data`; la persistencia no traslada los jobs que quedaron en otro broker.

### Después de actualizar {#after-the-upgrade}

Nada de lo siguiente bloquea la actualización ni exige acciones para completarla, pero cambia lo
que verás con 1.7 en ejecución.

!!! info "Un servicio reservado `default-server` aparece en instalaciones multisitio"

    Con `MULTISITE=yes`, el bloque que responde a peticiones sin servicio coincidente — hostname
    desconocido, IP directa o `Host` no servido — es ahora una fila de servicio reservada y
    permanente. Aparece en la interfaz y en `GET /services` con `reserved: true`; no se puede
    eliminar, renombrar ni pasar a borrador y nunca cuenta para la cuota de servicios PRO. Se puede
    configurar con su propio certificado, ajustes TLS, cabeceras y páginas de error. Consulta
    [la API](api.md#api-surface-capability-map) y [la interfaz](web-ui.md#the-default-server-entry).

    Con `MULTISITE=no` no se crea esa fila y el servidor predeterminado se genera igual que en 1.6.

!!! info "El registro de instancias está disponible y es opcional"

    Una instancia puede obtener su propia credencial del plano de control canjeando un código de
    un solo uso y duración limitada, en lugar de compartir `API_TOKEN`. Nada cambia hasta
    registrarla: las instancias no registradas siguen usando `API_TOKEN` como en 1.6. Una vez
    registrada solo acepta su credencial y nunca vuelve a la compartida. Una reversión sin
    restauración destruye las credenciales almacenadas. Devuelve la instancia al `API_TOKEN`
    compartido antes de revertir, o vuelve a registrarla después. Consulta [Registro de instancias](web-ui.md#instance-enrollment) y
    [Una instancia registrada no arranca](troubleshooting.md#lost-instance-credential): si pierde
    su archivo de credencial pero conserva el resto del estado, se niega a arrancar hasta registrarse de nuevo.

!!! info "Novedades de 1.7 que conviene revisar"

    - **Reglas AND compuestas** en las tres listas de acceso: `BLACKLIST_RULE_1`, `GREYLIST_RULE_1`,
      `WHITELIST_RULE_1` y sus variantes solo coinciden si se cumple cada término
      (`country:FR AND NOT ua:GoodBot`).
    - **Un plugin GeoIP dedicado.** No requiere configuración: las bases de países y ASN siguen
      usando DB-IP Lite gratuito. Las novedades son la suscripción MaxMind (`MAXMIND_LICENSE_KEY`,
      `MAXMIND_ACCOUNT_ID`), una base de ciudades (`GEOIP_CITY`) y archivos `.mmdb` propios.
      Consulta [GeoIP](features.md#geoip).
    - **`BACKUP_ROTATION_STRATEGY`** decide *qué* backups conserva la rotación, no cuántos. El
      predeterminado `hanoi` conserva puntos antiguos a costa de reducir la densidad reciente;
      usa `fifo` para mantener la selección 1.6. `BACKUP_ROTATION` no cambia.
    - **Varias plantillas por servicio**: `USE_TEMPLATE` es una lista ordenada separada por espacios;
      una plantilla posterior sobrescribe a una anterior.
    - **Interfaz traducida en el servidor** con selector de idioma. Consulta
      [Traducciones](web-ui.md#translations-i18n).

### Reversión a 1.6.14 {#rolling-back-to-1614}

Una reversión no es lo contrario de una actualización. Existen dos vías, y BunkerWeb te indica
cuál se aplica a tu instalación en lugar de dejarte adivinar.

**Restaurar desde una copia de seguridad** funciona siempre y es la vía admitida. Reproduce una
copia de seguridad tomada *antes* de la actualización sobre una base de datos vaciada, así que se
pierde todo lo escrito desde la actualización. Consulta [Reversión](#rollback) más abajo para el
procedimiento manual por motor de base de datos.

**La reversión sin restauración** solo se ofrece para las combinaciones de versión/motor que se
han medido como no destructivas, y solo hasta la versión inmediatamente anterior. Para 1.7.0 eso
significa 1.6.14, solo en **SQLite y PostgreSQL**. En MariaDB y MySQL la migración de 1.7 no se
puede reproducir hacia atrás — se interrumpe a mitad de camino y deja un esquema que no
corresponde a ninguna de las dos versiones — así que esas instalaciones deben restaurarse desde
una copia de seguridad.

Tres comandos, en este orden:

```bash
# 1. ¿Puede esta instalación revertirse? Solo lectura: no crea ninguna base de datos ni escribe nada.
bwcli plugin backup preflight 1.6.14

# 2. Detén los escritores. Permanece en primer plano hasta que pulses Ctrl-C.
bwcli plugin backup quiesce 1.6.14

# 3. En una segunda shell, mientras el paso 2 sigue reteniendo:
bwcli plugin backup downgrade 1.6.14            # informa; no cambia nada
bwcli plugin backup downgrade 1.6.14 --execute  # pide confirmación y luego migra
```

El paso 3 se rechaza a menos que la retención del paso 2 siga activa para esa misma versión, el
preflight que vuelve a ejecutar por su cuenta salga limpio, y el manifiesto de compatibilidad
marque la combinación como probada. Después toma su propia copia de seguridad justo antes de
migrar y la restaura si algo sale mal.

Antes de empezar, detén o bloquea con firewall todo lo que escriba directamente en la API. La
retención hace que la API *informe* a la flota de que es de solo lectura, que es lo que el
scheduler, el autoconf y la interfaz respetan; no bloquea una escritura hecha directamente a la
API por quien posea un token.

!!! danger "Lo que destruye una reversión sin restauración"
    Todos los certificados almacenados de forma centralizada, todos los recursos adjuntables
    (redirecciones, pools de upstream, workflows, grupos de recursos), todas las métricas de
    peticiones y el mapa de amenazas, todas las passkeys registradas y toda credencial de instancia
    almacenada — las instancias inscritas deberán volver a registrarse contra el `API_TOKEN` global
    después. Las preferencias de interfaz por usuario sobreviven pero pierden su significado:
    1.6.14 las lee todas como disposiciones de columnas por tabla. Los bans son la única pérdida
    leve: el job `sync-bans` los reaprende de las instancias, perdiendo solo su duración restante.

    El preflight cuenta lo que tu instalación realmente contiene y rechaza una reversión sin
    restauración mientras quede algo irremplazable, así que la respuesta que obtienes trata sobre
    tus datos, no sobre la versión en abstracto.

**Fuera de la base de datos.** Las cachés de jobs y los plugins PRO se reconstruyen en la
siguiente ejecución. Las configuraciones personalizadas, el contenido de `www`, el estado de Let's
Encrypt y los archivos de copia de seguridad no cambian entre ambas versiones. Los plugins
externos que necesitan una API de 1.7 no funcionan en 1.6.14 y deben eliminarse o revertirse
también.

### Procedimiento

=== "Docker"

    === "Actualización sencilla con el script de instalación"

        El mismo script que crea instalaciones de Docker también actualiza un stack
        generado por él. Ejecútalo desde el directorio que contiene tu
        `docker-compose.yml` y tu `.env` (o indícalo con `--compose-dir`):

        ```bash
        LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

        # Descarga el script y su suma de verificación
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

        # Verifica la suma de verificación
        sha256sum -c install-bunkerweb.sh.sha256

        # Si la verificación es correcta, ejecuta el script
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh --docker --compose-dir /path/to/your/stack
        ```

        !!! danger "Aviso de seguridad"
            **Verifica siempre la integridad del script de instalación antes de ejecutarlo.**

            Descarga el archivo de suma de verificación y usa una herramienta como `sha256sum` para confirmar que el script no ha sido alterado ni manipulado.

            Si la verificación falla, **no ejecutes el script**: puede no ser seguro.

        !!! warning "Solo para stacks creados por este script"
            La actualización reconoce un stack por la cabecera
            `generated by install-bunkerweb.sh` de su archivo `.env`. Un
            `docker-compose.yml` escrito a mano, un contenedor All-In-One o un
            despliegue en Swarm/Kubernetes no se actualizan con el script: usa la
            pestaña **Manual** para esos casos.

        * **Cómo funciona**:

            1. Detección
                * Lee el tipo de instalación (full, manager, worker, scheduler, ui, api) desde el `.env`, así que nunca tienes que volver a indicar tu topología.
                * Recupera los secretos, los puertos del host, la lista de workers y el nombre de proyecto de Compose desde el `.env`, de modo que una actualización no puede rotar la contraseña de la base de datos, invalidar los secretos 2FA almacenados ni mover tus puertos publicados.
                * Lee la versión que realmente se está ejecutando desde el contenedor en lugar de fiarse de la etiqueta de imagen, así se detectan correctamente tanto una etiqueta móvil (`latest`, `testing`) como una actualización anterior interrumpida.
            2. Decisión de actualización
                * Ya se ejecuta la misma versión: muestra el estado del stack y termina.
                * Versión de destino más antigua: **se rechaza**. El instalador no tiene automatización de reversión propia, y arrancar el scheduler contra un paquete más antiguo con una base de datos ya migrada falla y entra en un bucle de reinicios. Consulta [Reversión a 1.6.14](#rolling-back-to-1614) para restaurar antes la base de datos, y luego vuelve a ejecutar el instalador en la versión anterior.
                * En cualquier otro caso: pide confirmación (o continúa directamente con `-y`).
            3. Copia de seguridad previa
                * Ejecuta `bwcli plugin backup save` dentro del contenedor del scheduler y copia el archivo al host.
                * Destino: `--backup-dir`, o una ruta generada como `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
                * Cancela la actualización si la copia falla, salvo que pases `--no-auto-backup`.
                * Se omite en los stacks `worker`, `ui` y `api`, que no tienen base de datos propia.
            4. Actualización de archivos
                * El `.env` se reescribe con la nueva etiqueta de imagen; se conserva cualquier entrada que hayas añadido a mano.
                * El `docker-compose.yml` solo se regenera si sigue coincidiendo con lo que produjo el script, así que tus ediciones locales sobreviven. Usa `--overwrite-compose` para regenerarlo de todos modos. En ambos casos se guarda una copia `.bak.<marca de tiempo>`.
            5. Aplicación y verificación
                * `docker compose pull` y después `docker compose up -d`: solo se recrean los contenedores cuya imagen ha cambiado, por lo que la interrupción es menor que con un ciclo completo de `down`/`up`.
                * Si la descarga falla no se recrea nada, se restaura la etiqueta anterior en el `.env` y el stack en ejecución queda intacto.
                * Después, el script vuelve a leer la versión del contenedor y comprueba que el scheduler no haya entrado en un bucle de reinicios, que es como se manifiesta un fallo de migración de la base de datos.

        * **Opciones útiles**:

            | Opción                  | Efecto                                                                                  |
            | ----------------------- | --------------------------------------------------------------------------------------- |
            | `--compose-dir PATH`    | Directorio que contiene el stack (por defecto: el directorio actual)                    |
            | `-v, --version VERSION` | Versión de destino; la etiqueta de imagen se deriva de ella                             |
            | `--image-tag TAG`       | Etiqueta de imagen de destino directamente, en lugar de derivarla                       |
            | `--backup-dir PATH`     | Dónde guardar la copia de seguridad previa                                              |
            | `--no-auto-backup`      | Omitir la copia automática (la copia manual pasa a ser responsabilidad tuya)            |
            | `--overwrite-compose`   | Regenerar `docker-compose.yml` aunque se haya editado localmente                        |
            | `--force-type-change`   | Permitir que el stack cambie de topología (destructivo)                                 |
            | `--no-pull`             | No descargar las imágenes antes de recrear el stack                                     |
            | `-y, --yes`             | Ejecución desatendida; sin esta opción, las invocaciones por tubería terminan con error |

    === "Manual"

        1.  **Hacer copia de seguridad de la base de datos**:

            - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
            - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        2.  **Actualizar BunkerWeb**:
            - Actualiza BunkerWeb a la última versión.
                1. **Actualiza el archivo Docker Compose**: cambiar la etiqueta no basta desde
                   1.6. Añade `bw-api`, `bw-worker`, `bw-jobs-broker`, las variables `API_URL`,
                   `API_TOKEN` y `CELERY_BROKER_URL` en cada componente y un volumen
                   `bw-instance-data` en `bunkerweb`; consulta los [cambios importantes](#breaking-changes).
                   Reconstruye `docker-compose.yml` desde el stack de referencia 1.7 de
                   [Docker](integrations.md#docker) o [Docker autoconf](integrations.md#docker-autoconf),
                   conservando tus ajustes, volúmenes y puertos publicados.

                2.  **Reinicia los contenedores**: Reinicia los contenedores para aplicar los cambios.
                    ```bash
                    docker compose down
                    docker compose up -d
                    ```

        3.  **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

            ```bash
            docker compose logs <scheduler_container>
            ```

        4.  **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.

=== "All-In-One (AIO)"

    La [imagen All-In-One](integrations.md#all-in-one-aio-image) agrupa BunkerWeb, el Programador, la interfaz web y, opcionalmente, la API, Redis y CrowdSec en un **único contenedor** llamado `bunkerweb-aio` por defecto. Todo el estado persistente — base de datos SQLite, caché, configuraciones personalizadas, plugins, copias de seguridad y datos de Redis/CrowdSec — vive en el volumen `/data`, por lo que actualizar consiste en reemplazar el contenedor conservando ese volumen.

    1. **Requisitos previos**:

        - Anota el tag de la imagen que estás ejecutando actualmente y el nombre del volumen `/data` (o bind mount) para reutilizar exactamente el mismo después de la actualización.

        !!! warning "Conserva el volumen `/data`"
            **Nunca elimines el volumen `/data` durante una actualización.** Contiene la base de datos, el estado integrado de Redis y CrowdSec, tus configuraciones personalizadas y tus copias de seguridad. Reemplazar el contenedor es seguro; borrar el volumen no lo es.

        !!! tip "Bases de datos externas"
            Si ejecutas el AIO con una base de datos externa (`DATABASE_URI` apuntando a MySQL/MariaDB/PostgreSQL), el archivo SQLite bajo `/data` no se usa; asegúrate de respaldar también esa base de datos externa con tus herramientas habituales.

    2. **Hacer copia de seguridad de la base de datos**:

        - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos. El Programador se ejecuta dentro del contenedor `bunkerweb-aio`, por lo que el comando de copia de seguridad se ejecuta allí directamente.

        ```bash
        docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory bunkerweb-aio bwcli plugin backup save
        ```

        ```bash
        docker cp bunkerweb-aio:/path/to/backup/directory /path/to/backup/directory
        ```

    3. **Actualizar BunkerWeb**:

        === "docker run"

            3. **Detén y elimina el contenedor actual** (se conserva el volumen `/data`):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Descarga la nueva imagen**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

            5. **Vuelve a crear el contenedor** con las mismas opciones, reutilizando el mismo volumen `/data`, puertos y variables de entorno que antes:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:1.7.0-beta
                ```

        === "Docker Compose"

            6. **Actualiza el archivo Docker Compose**: Actualiza el archivo Docker Compose para usar la nueva versión de la imagen All-In-One.
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:1.7.0-beta
                        ...
                ```

            7. **Reinicia el contenedor**: Reinicia el contenedor para aplicar los cambios. El volumen `/data` se vuelve a adjuntar automáticamente.
                ```bash
                docker compose down
                docker compose up -d
                ```

    4. **Revisa los registros**: Revisa los registros del contenedor para asegurarte de que la migración realizada por el Programador integrado fue exitosa.

        ```bash
        docker logs bunkerweb-aio
        ```

    5. **Verifica la actualización**:
        - Confirma que el contenedor está ejecutándose y sano:
            ```bash
            docker ps --filter name=bunkerweb-aio
            ```
            La columna `STATUS` debe mostrar `(healthy)` una vez que pasen las comprobaciones de inicio.
        - Confirma la versión en ejecución:
            ```bash
            docker exec bunkerweb-aio cat /usr/share/bunkerweb/VERSION
            ```
            La versión también se puede revisar desde la interfaz web en *Support*.
        - Verifica en la interfaz web que tus servicios, ajustes y configuraciones personalizadas están intactos, y que tus sitios siguen sirviéndose por HTTP/HTTPS.

=== "Linux"

    === "Actualización fácil usando el script de instalación"

        * **Inicio rápido**:

            Para empezar, descarga el script de instalación y su suma de verificación, luego verifica la integridad del script antes de ejecutarlo.

            ```bash
            LATEST_VERSION=$(curl -s https://api.github.com/repos/bunkerity/bunkerweb/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')

            # Download the script and its checksum
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh
            curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/${LATEST_VERSION}/install-bunkerweb.sh.sha256

            # Verify the checksum
            sha256sum -c install-bunkerweb.sh.sha256

            # Si la verificación es exitosa, ejecuta el script
            chmod +x install-bunkerweb.sh
            sudo ./install-bunkerweb.sh
            ```

            !!! danger "Aviso de seguridad"
                **Siempre verifica la integridad del script de instalación antes de ejecutarlo.**

                Descarga el archivo de suma de verificación y usa una herramienta como `sha256sum` para confirmar que el script no ha sido alterado o manipulado.

                Si la verificación de la suma de verificación falla, **no ejecutes el script**—puede no ser seguro.

        !!! tip "Interfaz de actualización interactiva"
            El flujo de actualización usa la misma TUI que las instalaciones nuevas: indicaciones en línea con [gum](https://github.com/charmbracelet/gum), con respaldo en los diálogos `whiptail` y, finalmente, en indicaciones de texto plano si gum no puede obtenerse. El binario `gum` se descarga desde la [release de GitHub](https://github.com/charmbracelet/gum/releases) oficial (SHA256 fijado, verificación cosign cuando cosign está instalado) y se ejecuta desde un directorio temporal que se elimina al salir — no se instala ningún paquete del sistema y no se añade ninguna fuente apt/dnf. Pasa `--no-tui` (o establece `BW_INSTALL_TUI=no`) para saltar todos los niveles de TUI, o `--tui` para exigir una TUI operativa. Para actualizaciones totalmente desatendidas, pasa `-y` / `--yes` con los flags relevantes — las invocaciones por tubería (`curl … | bash`) salen con un error claro en lugar de aceptar silenciosamente cada valor predeterminado. **Actualizaciones aisladas (air-gapped)**: combina `--no-tui --yes` para que no se haga ninguna llamada de red para la capa de TUI.

        * **Cómo funciona**:

            El mismo script de instalación multipropósito utilizado para instalaciones nuevas también puede realizar una actualización in situ. Cuando detecta una instalación existente y una versión de destino diferente, cambia al modo de actualización y aplica el siguiente flujo de trabajo:

            1. Detección y validación
                * Detecta el SO/versión y confirma la matriz de soporte.
                * Lee la versión de BunkerWeb actualmente instalada desde `/usr/share/bunkerweb/VERSION`.
            2. Decisión del escenario de actualización
                * Si la versión solicitada es igual a la instalada, se aborta (a menos que lo vuelvas a ejecutar explícitamente para ver el estado).
                * Si las versiones difieren, marca una actualización.
            3. (Opcional) Copia de seguridad automática previa a la actualización
                * Si `bwcli` y el programador están disponibles y la copia de seguridad automática está habilitada, crea una copia de seguridad a través del plugin de copia de seguridad incorporado.
                * Destino: ya sea el directorio que proporcionaste con `--backup-dir` o una ruta generada como `/var/tmp/bunkerweb-backup-YYYYmmdd-HHMMSS`.
                * Puedes deshabilitar esto con `--no-auto-backup` (la copia de seguridad manual entonces se convierte en tu responsabilidad).
            4. Detención de servicios
                * Detiene `bunkerweb`, `bunkerweb-ui` y `bunkerweb-scheduler` para garantizar una actualización consistente (coincide con las recomendaciones del procedimiento manual).
            5. Eliminación de bloqueos de paquetes
                * Elimina temporalmente `apt-mark hold` / `dnf versionlock` en `bunkerweb` y `nginx` para que se pueda instalar la versión de destino.
            6. Ejecución de la actualización
                * Instala solo la nueva versión del paquete de BunkerWeb (NGINX no se reinstala en modo de actualización a menos que falte, esto evita tocar un NGINX correctamente anclado).
                * Vuelve a aplicar los bloqueos/versionlocks para congelar las versiones actualizadas.
            7. Finalización y estado
                * Muestra el estado de systemd para los servicios principales y los próximos pasos.
                * Deja tu configuración y base de datos intactas: solo se actualiza el código de la aplicación y los archivos gestionados.

            Comportamientos clave / notas:

            * El script NO modifica tu `/etc/bunkerweb/variables.env` ni el contenido de la base de datos.
            * Si la copia de seguridad automática falló (o se deshabilitó), aún puedes hacer una restauración manual usando la sección de Reversión a continuación.
            * El modo de actualización evita intencionadamente reinstalar o degradar NGINX fuera de la versión anclada compatible ya presente.
            * Los registros para la solución de problemas permanecen en `/var/log/bunkerweb/`.

        * **Comportamiento según el modo**:

            - El instalador reutiliza la misma lógica de selección durante la actualización: el modo manager mantiene el asistente deshabilitado, vincula la API a `0.0.0.0` y sigue exigiendo una IP para la lista blanca (proporciónala con `--manager-ip` en ejecuciones no interactivas), mientras que el modo worker continúa obligando a indicar las IP del manager.
            - Las actualizaciones del manager pueden decidir si se inicia el servicio Web UI, y el resumen indica explícitamente el estado del servicio API para que puedas controlarlo con `--api` / `--no-api`.
            - Las opciones de CrowdSec siguen limitadas a las actualizaciones full stack, y el script continúa validando el sistema operativo y la arquitectura de CPU antes de modificar paquetes; las combinaciones no soportadas siguen requiriendo `--force`.

            Resumen de la reversión:

            * Usa el directorio de copia de seguridad generado (o tu copia de seguridad manual) + los pasos en la sección de Reversión para restaurar la base de datos, luego reinstala la versión anterior de la imagen/paquete y vuelve a bloquear los paquetes.

        *  **Opciones de línea de comandos**:

            Puedes realizar actualizaciones desatendidas con los mismos indicadores utilizados para la instalación. Los más relevantes para las actualizaciones:

            | Opción                  | Propósito                                                                                                                                     |
            | :---------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
            | `-v, --version <X.Y.Z>` | Versión de BunkerWeb de destino a la que actualizar.                                                                                          |
            | `-y, --yes`             | No interactivo (asume la confirmación de la actualización y habilita la copia de seguridad automática a menos que se use `--no-auto-backup`). |
            | `--tui`                 | Fuerza una TUI (gum o whiptail). Aborta si ninguna puede instalarse.                                                                          |
            | `--no-tui`              | Salta todos los niveles de TUI y usa indicaciones de texto plano. Equivale a `BW_INSTALL_TUI=no`.                                             |
            | `--backup-dir <RUTA>`   | Destino para la copia de seguridad automática previa a la actualización. Se crea si no existe.                                                |
            | `--no-auto-backup`      | Omitir la copia de seguridad automática (NO recomendado). Debes tener una copia de seguridad manual.                                          |
            | `-q, --quiet`           | Suprimir la salida (combinar con registro / monitoreo).                                                                                       |
            | `-f, --force`           | Continuar en una versión de SO no compatible.                                                                                                 |
            | `--dry-run`             | Mostrar el entorno detectado, las acciones previstas y luego salir sin cambiar nada.                                                          |

            Ejemplos:

            ```bash
            # Actualizar a 1.7.0~beta interactivamente (pedirá confirmación para la copia de seguridad)
            sudo ./install-bunkerweb.sh --version 1.7.0~beta

            # Actualización no interactiva con copia de seguridad automática a un directorio personalizado
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --backup-dir /var/backups/bw-2025-01 -y

            # Actualización desatendida silenciosa (salida suprimida) – depende de la copia de seguridad automática predeterminada
            sudo ./install-bunkerweb.sh -v 1.7.0~beta -y -q

            # Realizar una ejecución de prueba (plan) sin aplicar cambios
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --dry-run

            # Actualizar omitiendo la copia de seguridad automática (NO recomendado)
            sudo ./install-bunkerweb.sh -v 1.7.0~beta --no-auto-backup -y
            ```

            !!! warning "Omitir copias de seguridad"
                Usar `--no-auto-backup` sin tener una copia de seguridad manual verificada puede resultar en una pérdida de datos irreversible si la actualización encuentra problemas. Siempre mantén al menos una copia de seguridad reciente y probada.

    === "Manual"

        1. **Hacer copia de seguridad de la base de datos**:

            - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
            - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

            ??? warning "Información para usuarios de Red Hat Enterprise Linux (RHEL) 8.10"
                Si estás usando **RHEL 8.10** y planeas usar una **base de datos externa**, necesitarás instalar el paquete `mysql-community-client` para asegurar que el comando `mysqldump` esté disponible. Puedes instalar el paquete ejecutando los siguientes comandos:

                === "MySQL/MariaDB"

                    1. **Instalar el paquete de configuración del repositorio de MySQL**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Habilitar el repositorio de MySQL**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Instalar el cliente de MySQL**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Instalar el paquete de configuración del repositorio de PostgreSQL**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Instalar el cliente de PostgreSQL**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

        1. **Actualizar BunkerWeb**:
            - Actualiza BunkerWeb a la última versión.

                1. **Detener los servicios**:
                    ```bash
                    sudo systemctl stop bunkerweb
                    sudo systemctl stop bunkerweb-ui
                    sudo systemctl stop bunkerweb-scheduler
                    sudo systemctl stop bunkerweb-api
                    sudo systemctl stop bunkerweb-worker
                    ```

                2. **Actualizar BunkerWeb**:

                    === "Debian/Ubuntu"

                        Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                        Puedes imprimir una lista de paquetes mantenidos con `apt-mark showhold`

                        ```shell
                        sudo apt-mark unhold bunkerweb nginx
                        ```

                        Luego, puedes actualizar el paquete de BunkerWeb:

                        ```shell
                        sudo apt update && \
                        sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                        ```

                        Para evitar que el paquete de BunkerWeb se actualice al ejecutar `apt upgrade`, puedes usar el siguiente comando:

                        ```shell
                        sudo apt-mark hold bunkerweb nginx
                        ```

                        Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_1).

                    === "Fedora/RedHat"

                        Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                        Puedes imprimir una lista de paquetes mantenidos con `dnf versionlock list`

                        ```shell
                        sudo dnf versionlock delete package bunkerweb && \
                        sudo dnf versionlock delete package nginx
                        ```

                        Luego, puedes actualizar el paquete de BunkerWeb:

                        ```shell
                        sudo dnf makecache && \
                        sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                        ```

                        Para evitar que el paquete de BunkerWeb se actualice al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

                        ```shell
                        sudo dnf versionlock add bunkerweb && \
                        sudo dnf versionlock add nginx
                        ```

                        Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_3).

                3. **Iniciar los servicios**:
                        ```bash
                        sudo systemctl start bunkerweb
                        sudo systemctl start bunkerweb-api
                        sudo systemctl start bunkerweb-worker
                        sudo systemctl start bunkerweb-scheduler
                        sudo systemctl start bunkerweb-ui
                        ```
                        O reinicia el sistema:
                        ```bash
                        sudo reboot
                        ```


        3. **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

            ```bash
            journalctl -u bunkerweb --no-pager
            ```

        4. **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.
### Reversión {#rollback}

!!! failure "En caso de problemas"

    Si encuentras algún problema durante la actualización, puedes volver a la versión anterior de la base de datos restaurando la copia de seguridad tomada en el [paso 1](#__tabbed_1_1).

    Obtén soporte y más información:

    - [Solicitar soporte profesional](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Crear un issue en GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Unirse al servidor de Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaura la copia de seguridad**.

        === "SQLite"

            1. **Elimina el archivo de la base de datos existente.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrige los permisos.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restaura la copia de seguridad.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

    3. **Retrocede la versión de BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Inicia los contenedores**.

        ```bash
        docker compose up -d
        ```

=== "All-In-One (AIO)"

    El Programador se ejecuta dentro del contenedor `bunkerweb-aio`, por lo que los comandos de restauración se ejecutan allí directamente. El volumen `/data` (base de datos, configuraciones, plugins, copias de seguridad) se conserva durante todo el proceso; solo se revierte la imagen del contenedor.

    !!! tip "Bases de datos externas"
        Si ejecutas el AIO con una base de datos externa (`DATABASE_URI` apuntando a MySQL/MariaDB/PostgreSQL), el archivo SQLite bajo `/data` no se usa. Restaura esa base de datos externa con tus herramientas habituales — o con los comandos MySQL/MariaDB/PostgreSQL mostrados en la pestaña **Docker**, apuntando a tu host de base de datos — y omite los pasos SQLite siguientes.

    1. **Extrae la copia de seguridad si está comprimida**.

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaura la copia de seguridad** (SQLite integrado):

        1. **Elimina el archivo de base de datos existente.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio rm -f /var/lib/bunkerweb/db.sqlite3
            ```

        2. **Restaura la copia de seguridad.**

            ```bash
            docker exec -i bunkerweb-aio sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            ```

        3. **Corrige los permisos.**

            ```bash
            docker exec -u 0 -i bunkerweb-aio chown root:nginx /var/lib/bunkerweb/db.sqlite3
            docker exec -u 0 -i bunkerweb-aio chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

    3. **Revierte la imagen**, reutilizando el mismo volumen `/data`:

        === "docker run"

            3. **Detén y elimina el contenedor actual** (se conserva el volumen `/data`):
                ```bash
                docker stop bunkerweb-aio
                docker rm bunkerweb-aio
                ```

            4. **Descarga la imagen anterior**:
                ```bash
                docker pull bunkerity/bunkerweb-all-in-one:<old_version>
                ```

            5. **Vuelve a crear el contenedor** con las mismas opciones, puertos y el mismo volumen `/data` que antes:
                ```bash
                docker run -d \
                --name bunkerweb-aio \
                -v bw-storage:/data \
                -p 80:8080/tcp \
                -p 443:8443/tcp \
                -p 443:8443/udp \
                bunkerity/bunkerweb-all-in-one:<old_version>
                ```

        === "Docker Compose"

            6. **Actualiza el archivo Docker Compose** para usar la imagen All-In-One anterior:
                ```yaml
                services:
                    bunkerweb-aio:
                        image: bunkerity/bunkerweb-all-in-one:<old_version>
                        ...
                ```

            7. **Reinicia el contenedor**. El volumen `/data` se vuelve a adjuntar automáticamente:
                ```bash
                docker compose down
                docker compose up -d
                ```

=== "Linux"

    4. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Detén los servicios**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6. **Restaura la copia de seguridad**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Inicia los servicios**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8. **Retrocede la versión de BunkerWeb**.
        - Retrocede BunkerWeb a la versión anterior siguiendo los mismos pasos que al actualizar BunkerWeb en la [página de integración con Linux](integrations.md#linux)

## Actualización desde 1.5.X

### ¿Qué ha cambiado?

#### Programador

A diferencia de las versiones 1.5.X, el servicio del Programador **ya no utiliza el *proxy del socket de Docker* para obtener las instancias de BunkerWeb**. En su lugar, utiliza la nueva variable de entorno `BUNKERWEB_INSTANCES`.

!!! info "Sobre la variable de entorno `BUNKERWEB_INSTANCES`"

    Esta nueva variable es una lista de instancias de BunkerWeb separadas por espacios en este formato: `http://bunkerweb:5000 bunkerweb1:5000 bunkerweb2:5000 ...`. El programador utilizará entonces esta lista para obtener la configuración de las instancias y enviarles la configuración.

    * El prefijo `http://` es opcional.
    * El puerto es opcional y por defecto es el valor de la variable de entorno `API_HTTP_PORT`.
    * El valor predeterminado de la variable de entorno `BUNKERWEB_INSTANCES` es `127.0.0.1`.

En otras palabras, el nuevo sistema es totalmente agnóstico y genérico: el programador se encarga de gestionar una lista de instancias de BunkerWeb y no necesita preocuparse por el entorno.

!!! tip "Integraciones Autoconf/Kubernetes/Swarm"

    Si estás utilizando las integraciones `Autoconf`, `Kubernetes` o `Swarm`, puedes establecer la variable de entorno `BUNKERWEB_INSTANCES` en una cadena vacía (para que no intente enviar la configuración a la predeterminada que es `127.0.0.1`).

    **Las instancias serán obtenidas automáticamente por el controlador**. También puedes añadir instancias personalizadas a la lista que pueden no ser recogidas por el controlador.

Desde la versión `1.6`, el Programador también tiene un nuevo [sistema de comprobación de estado integrado](concepts.md), que comprobará la salud de las instancias. Si una instancia deja de estar saludable, el programador dejará de enviarle la configuración. Si la instancia vuelve a estar saludable, el programador comenzará a enviarle la configuración de nuevo.

#### Contenedor de BunkerWeb

Otro cambio importante es que las **configuraciones** que antes se declaraban en el contenedor de BunkerWeb **ahora se declaran en el programador**. Esto significa que tendrás que mover tus configuraciones del contenedor de BunkerWeb al contenedor del Programador.

Aunque las configuraciones se declaran ahora en el contenedor del Programador, **todavía necesitarás declarar las configuraciones obligatorias relacionadas con la API en el contenedor de BunkerWeb**, como la configuración `API_WHITELIST_IP`, que se utiliza para incluir en la lista blanca la dirección IP del Programador, para que pueda enviar la configuración a la instancia. Si usas `API_TOKEN`, también debes establecerlo en el contenedor de BunkerWeb (y reflejarlo en el Programador) para permitir las llamadas a la API autenticadas.

!!! warning "Configuraciones del contenedor de BunkerWeb"

    Cada configuración relacionada con la API que declares en el contenedor de BunkerWeb **tiene que ser reflejada en el contenedor del Programador** para que siga funcionando, ya que la configuración será sobrescrita por la configuración generada por el Programador.

#### Valores predeterminados y nuevas configuraciones

Hicimos nuestro mejor esfuerzo para no cambiar el valor predeterminado, pero hemos añadido muchas otras configuraciones. Se recomienda encarecidamente leer las secciones de [ajuste de seguridad](advanced.md#security-tuning) y [configuraciones](features.md) de la documentación.

#### Plantillas

Hemos añadido una nueva característica llamada **plantillas**. Las plantillas proporcionan un enfoque estructurado y estandarizado para definir configuraciones y configuraciones personalizadas, consulta la sección [conceptos/plantillas](concepts.md#templates) para obtener más información.

#### Espacios de nombres de Autoconf

Hemos añadido una característica de **espacio de nombres** a las integraciones de autoconfiguración. Los espacios de nombres te permiten agrupar tus instancias y aplicarles configuraciones solo a ellas. Consulta las siguientes secciones según tu Integración para obtener más información:

- [Autoconf/espacios de nombres](integrations.md#namespaces)
- [Kubernetes/espacios de nombres](integrations.md#namespaces_1)
- [Swarm/espacios de nombres](integrations.md#namespaces_2)

### Procedimiento

1.  **Hacer copia de seguridad de la base de datos**:
      - Antes de proceder con la actualización de la base de datos, asegúrate de realizar una copia de seguridad completa del estado actual de la base de datos.
      - Utiliza las herramientas adecuadas para hacer una copia de seguridad de toda la base de datos, incluyendo datos, esquemas y configuraciones.

    === "1.5.7 y posteriores"

        === "Docker"

            ```bash
            docker exec -it -e BACKUP_DIRECTORY=/path/to/backup/directory <scheduler_container> bwcli plugin backup save
            ```

            ```bash
            docker cp <scheduler_container>:/path/to/backup/directory /path/to/backup/directory
            ```

        === "Linux"

            ??? warning "Información para usuarios de Red Hat Enterprise Linux (RHEL) 8.10"
                Si estás usando **RHEL 8.10** y planeas usar una **base de datos externa**, necesitarás instalar el paquete `mysql-community-client` para asegurar que el comando `mysqldump` esté disponible. Puedes instalar el paquete ejecutando los siguientes comandos:

                === "MySQL/MariaDB"

                    1. **Instalar el paquete de configuración del repositorio de MySQL**

                        ```bash
                        sudo dnf install https://dev.mysql.com/get/mysql80-community-release-el8-9.noarch.rpm
                        ```

                    2. **Habilitar el repositorio de MySQL**

                        ```bash
                        sudo dnf config-manager --enable mysql80-community
                        ```

                    3. **Instalar el cliente de MySQL**

                        ```bash
                        sudo dnf install mysql-community-client
                        ```

                === "PostgreSQL"

                    4. **Instalar el paquete de configuración del repositorio de PostgreSQL**

                        ```bash
                        dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
                        ```

                    5. **Instalar el cliente de PostgreSQL**

                        ```bash
                        dnf install postgresql<version>
                        ```

            ```bash
            BACKUP_DIRECTORY=/path/to/backup/directory bwcli plugin backup save
            ```

    === "1.5.6 y anteriores"

        === "SQLite"

            === "Docker"

                Primero necesitamos instalar el paquete `sqlite` en el contenedor.

                ```bash
                docker exec -u 0 -it <scheduler_container> apk add sqlite
                ```

                Luego, haz una copia de seguridad de la base de datos.

                ```bash
                docker exec -it <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                sqlite3 /var/lib/bunkerweb/db.sqlite3 ".dump" > /path/to/backup/directory/backup.sql
                ```

        === "MariaDB"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mariadb-dump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "MySQL"

            === "Docker"

                ```bash
                docker exec -it -e MYSQL_PWD=<database_password> <database_container> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                MYSQL_PWD=<database_password> mysqldump -u <username> <database_name> > /path/to/backup/directory/backup.sql
                ```

        === "PostgreSQL"

            === "Docker"

                ```bash
                docker exec -it -e PGPASSWORD=<database_password> <database_container> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

            === "Linux"

                ```bash
                PGPASSWORD=<database_password> pg_dump -U <username> -d <database_name> > /path/to/backup/directory/backup.sql
                ```

2.  **Actualizar BunkerWeb**:
      - Actualiza BunkerWeb a la última versión.

        === "Docker"

            1.  **Actualiza el archivo Docker Compose**: Actualiza el archivo Docker Compose para usar la nueva versión de la imagen de BunkerWeb.
                ```yaml
                services:
                    bunkerweb:
                        image: bunkerity/bunkerweb:1.7.0-beta
                        ...
                    bw-scheduler:
                        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
                        ...
                    bw-autoconf:
                        image: bunkerity/bunkerweb-autoconf:1.7.0-beta
                        ...
                    bw-ui:
                        image: bunkerity/bunkerweb-ui:1.7.0-beta
                        ...
                ```

            2.  **Reinicia los contenedores**: Reinicia los contenedores para aplicar los cambios.
                ```bash
                docker compose down
                docker compose up -d
                ```

        === "Linux"

            3.  **Detén los servicios**:
                ```bash
                sudo systemctl stop bunkerweb
                sudo systemctl stop bunkerweb-ui
                sudo systemctl stop bunkerweb-scheduler
                sudo systemctl stop bunkerweb-api
                sudo systemctl stop bunkerweb-worker
                ```

            4.  **Actualiza BunkerWeb**:

                === "Debian/Ubuntu"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `apt-mark showhold`

                    ```shell
                    sudo apt-mark unhold bunkerweb nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo apt update && \
                    sudo apt install -y --allow-downgrades bunkerweb=1.7.0~beta
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `apt upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo apt-mark hold bunkerweb nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_1).

                === "Fedora/RedHat"

                    Primero, si has mantenido previamente el paquete de BunkerWeb, desmárcalo:

                    Puedes imprimir una lista de paquetes mantenidos con `dnf versionlock list`

                    ```shell
                    sudo dnf versionlock delete package bunkerweb && \
                    sudo dnf versionlock delete package nginx
                    ```

                    Luego, puedes actualizar el paquete de BunkerWeb:

                    ```shell
                    sudo dnf makecache && \
                    sudo dnf install -y --allowerasing bunkerweb-1.7.0~beta
                    ```

                    Para evitar que el paquete de BunkerWeb se actualice al ejecutar `dnf upgrade`, puedes usar el siguiente comando:

                    ```shell
                    sudo dnf versionlock add bunkerweb && \
                    sudo dnf versionlock add nginx
                    ```

                    Más detalles en la [página de integración con Linux](integrations.md#__tabbed_1_3).

            5.  **Inicia los servicios**:
                    ```bash
                    sudo systemctl start bunkerweb
                    sudo systemctl start bunkerweb-api
                    sudo systemctl start bunkerweb-worker
                    sudo systemctl start bunkerweb-scheduler
                    sudo systemctl start bunkerweb-ui
                    ```
                    O reinicia el sistema:
                    ```bash
                    sudo reboot
                    ```


3.  **Revisa los registros**: Revisa los registros del servicio del programador para asegurarte de que la migración fue exitosa.

    === "Docker"

        ```bash
        docker compose logs <scheduler_container>
        ```

    === "Linux"

        ```bash
        journalctl -u bunkerweb --no-pager
        ```

4.  **Verifica la base de datos**: Verifica que la actualización de la base de datos fue exitosa revisando los datos y las configuraciones en el nuevo contenedor de la base de datos.

### Reversión

!!! failure "En caso de problemas"

    Si encuentras algún problema durante la actualización, puedes volver a la versión anterior de la base de datos restaurando la copia de seguridad tomada en el [paso 1](#__tabbed_1_1).

    Obtén soporte y más información:

    - [Solicitar soporte profesional](https://panel.bunkerweb.io/?utm_source=doc&utm_campaign=self)
    - [Crear un issue en GitHub](https://github.com/bunkerity/bunkerweb/issues)
    - [Unirse al servidor de Discord de BunkerWeb](https://discord.bunkerity.com)

=== "Docker"

    1. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    2. **Restaura la copia de seguridad**.

        === "SQLite"

            1. **Elimina el archivo de la base de datos existente.**

                ```bash
                docker exec -u 0 -i <scheduler_container> rm -f /var/lib/bunkerweb/db.sqlite3
                ```

            2. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <scheduler_container> sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
                ```

            3. **Corrige los permisos.**

                ```bash
                docker exec -u 0 -i <scheduler_container> chown root:nginx /var/lib/bunkerweb/db.sqlite3
                docker exec -u 0 -i <scheduler_container> chmod 770 /var/lib/bunkerweb/db.sqlite3
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "MySQL/MariaDB"

            1. **Restaura la copia de seguridad.**

                ```bash
                docker exec -e MYSQL_PWD=<your_password> -i <database_container> mysql -u <username> <database_name> < /path/to/backup/directory/backup.sql
                ```

            2. **Detén la pila.**

                ```bash
                docker compose down
                ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                docker exec -i <database_container> dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                docker exec -i <database_container> createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                docker exec -i <database_container> psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

            4. **Detén la pila.**

                ```bash
                docker compose down
                ```

    3. **Retrocede la versión de BunkerWeb**.

        ```yaml
        services:
            bunkerweb:
                image: bunkerity/bunkerweb:<old_version>
                ...
            bw-scheduler:
                image: bunkerity/bunkerweb-scheduler:<old_version>
                ...
            bw-autoconf:
                image: bunkerity/bunkerweb-autoconf:<old_version>
                ...
            bw-ui:
                image: bunkerity/bunkerweb-ui:<old_version>
                ...
        ```

    4. **Inicia los contenedores**.

        ```bash
        docker compose up -d
        ```

=== "Linux"

    4. **Extrae la copia de seguridad si está comprimida**.

        Primero extrae el archivo zip de la copia de seguridad:

        ```bash
        unzip /path/to/backup/directory/backup.zip -d /path/to/backup/directory/
        ```

    5. **Detén los servicios**.

        ```bash
        sudo systemctl stop bunkerweb bunkerweb-ui bunkerweb-scheduler bunkerweb-api bunkerweb-worker
        ```

    6. **Restaura la copia de seguridad**.

        === "SQLite"

            ```bash
            sudo rm -f /var/lib/bunkerweb/db.sqlite3
            sudo sqlite3 /var/lib/bunkerweb/db.sqlite3 < /path/to/backup/directory/backup.sql
            sudo chown root:nginx /var/lib/bunkerweb/db.sqlite3
            sudo chmod 770 /var/lib/bunkerweb/db.sqlite3
            ```

        === "MySQL/MariaDB"

            ```bash
            mysql -u <username> -p <database_name> < /path/to/backup/directory/backup.sql
            ```

        === "PostgreSQL"

            1. **Elimina la base de datos existente.**

                ```bash
                dropdb -U <username> --force <database_name>
                ```

            2. **Vuelve a crear la base de datos.**

                ```bash
                createdb -U <username> <database_name>
                ```

            3. **Restaura la copia de seguridad.**

                ```bash
                psql -U <username> -d <database_name> < /path/to/backup/directory/backup.sql
                ```

    7. **Inicia los servicios**.

        ```bash
        sudo systemctl start bunkerweb bunkerweb-api bunkerweb-worker bunkerweb-scheduler bunkerweb-ui
        ```

    8. **Retrocede la versión de BunkerWeb**.
        - Retrocede BunkerWeb a la versión anterior siguiendo los mismos pasos que al actualizar BunkerWeb en la [página de integración con Linux](integrations.md#linux)
