# Solución de problemas

!!! info "Panel de BunkerWeb"
    Si no puedes resolver tu problema, puedes [contactarnos directamente a través de nuestro panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc). Esto centraliza todas las solicitudes relacionadas con la solución BunkerWeb.

## Registros

Al solucionar problemas, los registros son tus mejores amigos. Hacemos nuestro mejor esfuerzo para proporcionar registros fáciles de usar para ayudarte a entender lo que está sucediendo.

Ten en cuenta que puedes establecer el `LOG_LEVEL` en `info` (predeterminado: `notice`) para aumentar la verbosidad de BunkerWeb.

Aquí te mostramos cómo puedes acceder a los registros, dependiendo de tu integración:

=== "Docker"

    !!! tip "Listar contenedores"
        Para listar los contenedores en ejecución, puedes usar el siguiente comando:
        ```shell
        docker ps
        ```

    Puedes usar el comando `docker logs` (reemplaza `bunkerweb` con el nombre de tu contenedor):
    ```shell
    docker logs bunkerweb
    ```

    Aquí está el equivalente de docker-compose (reemplaza `bunkerweb` con el nombre de los servicios declarados en el archivo docker-compose.yml):
    ```shell
    docker-compose logs bunkerweb
    ```

=== "Docker autoconf"

    !!! tip "Listar contenedores"
        Para listar los contenedores en ejecución, puedes usar el siguiente comando:
        ```shell
        docker ps
        ```

    Puedes usar el comando `docker logs` (reemplaza `bunkerweb` y `bw-autoconf` con el nombre de tus contenedores):
    ```shell
    docker logs bunkerweb
    docker logs bw-autoconf
    ```

    Aquí está el equivalente de docker-compose (reemplaza `bunkerweb` y `bw-autoconf` con el nombre de los servicios declarados en el archivo docker-compose.yml):
    ```shell
    docker-compose logs bunkerweb
    docker-compose logs bw-autoconf
    ```

=== "Todo en uno"

    !!! tip "Nombre del contenedor"
        El nombre del contenedor predeterminado para la imagen Todo en uno es `bunkerweb-aio`. Si has usado un nombre diferente, por favor ajusta el comando en consecuencia.

    Puedes usar el comando `docker logs`:
    ```shell
    docker logs bunkerweb-aio
    ```

=== "Swarm"

    !!! tip "Listar servicios"
        Para listar los servicios, puedes usar el siguiente comando:
        ```shell
        docker service ls
        ```

    Puedes usar el comando `docker service logs` (reemplaza `bunkerweb` y `bw-autoconf` con el nombre de tus servicios):
    ```shell
    docker service logs bunkerweb
    docker service logs bw-autoconf
    ```

=== "Kubernetes"

    !!! tip "Listar pods"
        Para listar los pods, puedes usar el siguiente comando:
        ```shell
        kubectl get pods
        ```

    Puedes usar el comando `kubectl logs` (reemplaza `bunkerweb` y `bunkerweb-controler` con el nombre de tus pods):
    ```shell
    kubectl logs bunkerweb
    kubectl logs bunkerweb-controler
    ```

=== "Linux"

    Para errores relacionados con los servicios de BunkerWeb (p. ej., que no se inician), puedes usar `journalctl`:
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Los registros comunes se encuentran dentro del directorio `/var/log/bunkerweb`:
    ```shell
    cat /var/log/bunkerweb/error.log
    cat /var/log/bunkerweb/access.log
    ```

## Permisos

No olvides que BunkerWeb se ejecuta como un usuario sin privilegios por razones de seguridad obvias. Verifica dos veces los permisos de los archivos y carpetas utilizados por BunkerWeb, especialmente si usas configuraciones personalizadas (más información [aquí](advanced.md#custom-configurations)). Necesitarás establecer al menos derechos **_RW_** en los archivos y **_RWX_** en las carpetas.

## Desbloqueo de IP

Puedes desbloquear manualmente una IP, lo cual es útil al realizar pruebas para que puedas contactar la API interna de BunkerWeb (reemplaza `1.2.3.4` con la dirección IP a desbloquear):

=== "Docker / Docker Autoconf"

    Puedes usar el comando `docker exec` (reemplaza `bw-scheduler` con el nombre de tu contenedor):
    ```shell
    docker exec bw-scheduler bwcli unban 1.2.3.4
    ```

    Aquí está el equivalente de docker-compose (reemplaza `bw-scheduler` con el nombre de los servicios declarados en el archivo docker-compose.yml):
    ```shell
    docker-compose exec bw-scheduler bwcli unban 1.2.3.4
    ```

=== "Todo en uno"

    !!! tip "Nombre del contenedor"
        El nombre del contenedor predeterminado para la imagen Todo en uno es `bunkerweb-aio`. Si has usado un nombre diferente, por favor ajusta el comando en consecuencia.

    Puedes usar el comando `docker exec`:
    ```shell
    docker exec bunkerweb-aio bwcli unban 1.2.3.4
    ```

=== "Swarm"

    Puedes usar el comando `docker exec` (reemplaza `bw-scheduler` con el nombre de tu servicio):
    ```shell
    docker exec $(docker ps -q -f name=bw-scheduler) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    Puedes usar el comando `kubectl exec` (reemplaza `bunkerweb-scheduler` con el nombre de tu pod):
    ```shell
    kubectl exec bunkerweb-scheduler bwcli unban 1.2.3.4
    ```

=== "Linux"

    Puedes usar el comando `bwcli` (como root):
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

## Falsos positivos

### Modo de solo detección

Para fines de depuración/prueba, puedes configurar BunkerWeb en [modo de solo detección](features.md#security-modes) para que no bloquee las solicitudes y actúe como un proxy inverso clásico.

### ModSecurity

La configuración predeterminada de ModSecurity de BunkerWeb es cargar el Core Rule Set en modo de puntuación de anomalías con un nivel de paranoia (PL) de 1:

- Cada regla que coincida aumentará una puntuación de anomalía (por lo que muchas reglas pueden coincidir con una sola solicitud)
- PL1 incluye reglas con menos posibilidades de falsos positivos (pero menos seguridad que PL4)
- el umbral predeterminado para la puntuación de anomalía es 5 para las solicitudes y 4 para las respuestas

Tomemos los siguientes registros como ejemplo de una detección de ModSecurity usando la configuración predeterminada (formateado para una mejor legibilidad):

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

Como podemos ver, hay 3 registros diferentes:

1. La regla **930120** coincidió
2. La regla **932160** coincidió
3. Acceso denegado (regla **949110**)

Una cosa importante a entender es que la regla **949110** no es una regla "real": es la que denegará la solicitud porque se alcanza el umbral de anomalía (que es **10** en este ejemplo). ¡Nunca deberías eliminar la regla **949110**!

Si se trata de un falso positivo, deberías centrarte en las reglas **930120** y **932160**. El ajuste de ModSecurity y/o CRS está fuera del alcance de esta documentación, pero no olvides que puedes aplicar configuraciones personalizadas antes y después de que se cargue el CRS (más información [aquí](advanced.md#custom-configurations)).

### Mal comportamiento

Un caso común de falso positivo es cuando el cliente es baneado debido a la característica de "mal comportamiento", lo que significa que se generaron demasiados códigos de estado HTTP sospechosos en un período de tiempo (más información [aquí](features.md#bad-behavior)). Deberías empezar por revisar la configuración y luego editarla de acuerdo a tu(s) aplicación(es) web, como eliminar un código HTTP sospechoso, disminuir el tiempo de conteo, aumentar el umbral, ...

### Lista blanca

Si tienes bots (o administradores) que necesitan acceder a tu sitio web, la forma recomendada de evitar cualquier falso positivo es incluirlos en la lista blanca usando la [característica de lista blanca](features.md#whitelist). No recomendamos usar las configuraciones `WHITELIST_URI*` o `WHITELIST_USER_AGENT*` a menos que se establezcan en valores secretos e impredecibles. Los casos de uso comunes son:

- Bot de comprobación de estado / estado
- Devolución de llamada como IPN o webhook
- Rastreador de redes sociales

## Errores comunes

### El upstream envió una cabecera demasiado grande

Si ves el siguiente error `upstream sent too big header while reading response header from upstream` en los registros, necesitarás ajustar los diversos tamaños de los búferes del proxy usando las siguientes configuraciones:

- `PROXY_BUFFERS`
- `PROXY_BUFFER_SIZE`
- `PROXY_BUSY_BUFFERS_SIZE`

### No se pudo construir el hash de server_names

Si ves el siguiente error `could not build server_names_hash, you should increase server_names_hash_bucket_size` en los registros, necesitarás ajustar la configuración `SERVER_NAMES_HASH_BUCKET_SIZE`.

## Los jobs en segundo plano nunca se ejecutan {#background-jobs}

Desde 1.7, el Scheduler envía los jobs a través de la **API** (`POST /jobs/dispatch`) a un **broker**,
y un **Worker** los recoge y ejecuta (consulta [Programador](concepts.md#scheduler)). El Worker y
el broker son nuevos; la API ya existía, pero ahora participa en esta ruta. Si alguno falta o no
es accesible, nada se bloquea de forma evidente: el Scheduler sigue generando configuración y las
instancias están sanas, pero no se renuevan certificados, no se actualizan listas ni se hacen backups.

Busca una **última ejecución** que deje de avanzar en la página **Jobs** o en la API:

```bash
# Contenedores: nombre del servicio API; Linux: http://127.0.0.1:8888
curl -H "Authorization: Bearer $API_TOKEN" http://bw-api:8888/jobs
```

### El Worker no está ejecutándose

Tras actualizar desde 1.6, la causa más habitual es no haber añadido el Worker: cambiar solo las
etiquetas deja el stack sin `bw-api`, `bw-worker` ni `bw-jobs-broker`. Consulta
[las notas de actualización](upgrading.md#breaking-changes) y despliega desde el stack de referencia.

=== "Docker"

    ```shell
    docker compose ps bw-api bw-worker bw-jobs-broker
    docker compose logs bw-worker
    ```

    Si no existe el servicio, el stack es anterior a 1.7. Añade los tres servicios, `API_URL`,
    `API_TOKEN` y `CELERY_BROKER_URL`, y recréalo.

=== "Linux"

    ```shell
    systemctl is-enabled bunkerweb-worker; systemctl is-active bunkerweb-worker
    journalctl -u bunkerweb-worker --no-pager -n 100
    ```

    `bunkerweb-worker` es una unidad nueva en 1.7 que el paquete instala en todos los hosts: debe
    responder `enabled`/`disabled`, nunca "not found".

    **Compruébalo en el host de `bunkerweb-scheduler`.** Ahí debe estar `enabled` y `active`;
    `systemctl enable --now bunkerweb-worker` lo corrige e inicia por dependencia la unidad del
    broker. Si está activo pero sin trabajo, comprueba el broker.

    **En un nodo que solo ejecuta la instancia BunkerWeb**, una instalación `--worker` en el
    sentido del instalador, `disabled` es correcto: ese host no tiene jobs. No lo habilites ahí.

    !!! warning "Cada actualización del paquete lo vuelve a habilitar en un nodo de solo instancia"
        El paquete determina el perfil a partir de `WORKER_MODE`/`MANAGER_MODE`/`SERVICE_*` en su
        propio entorno y **ninguna actualización los define**, ni `apt install bunkerweb=...` ni
        `install-bunkerweb.sh`, cuya ruta de actualización termina antes de exportarlos. Cada
        actualización trata ese host como autónomo y **habilita e inicia** `bunkerweb-worker` y
        la primera unidad Redis encontrada: `redis-server`, `valkey` o `redis`, porque una
        instalación de solo instancia no aprovisiona `bunkerweb-broker`.

        Normalmente no recibe jobs: su worker usa `redis://127.0.0.1:6379/0`, donde ningún plano de
        control envía trabajo. La excepción es que su `CELERY_BROKER_URL` apunte a un broker
        **accesible por red**, por ejemplo copiada desde una instalación `--broker-url` o definida
        manualmente: entonces sí consume jobs. Una URL del broker dedicado del instalador usa
        `127.0.0.1`; copiada en otro nodo apunta al loopback de ese nodo y solo reintenta una
        conexión rechazada. Para quitar el worker: `systemctl disable --now bunkerweb-worker`,
        después de **cada** actualización. Solo una instalación nueva o una ejecución explícita
        del instalador con `--worker` lo hace automáticamente.

        **No desactives Redis sin confirmar que no es tu almacén WAF.** `USE_REDIS` y `REDIS_HOST`
        son ajustes de la *flota*, configurados en la interfaz → **Global settings** → Redis o
        en `/etc/bunkerweb/variables.env` del host Scheduler. El archivo del propio nodo ignora
        esas claves: buscar ahí no demuestra nada. Tras recibir al menos una configuración, puedes
        consultar localmente los valores que envió el plano de control:

        ```bash
        grep -E '^(USE_REDIS|REDIS_HOST)=' /etc/nginx/variables.env
        ```

        Antes del primer envío solo el plano de control conoce esos valores. Si `REDIS_HOST` es
        una dirección de **este** host — posiblemente una IP LAN, no `127.0.0.1` — este servidor
        guarda los bloqueos compartidos y contadores; desactivarlo los pierde y deja de compartirlos.
        Solo después de comprobarlo: `systemctl disable --now redis-server` (o `valkey` o `redis`).

        Si el almacén local en `127.0.0.1:6379` tiene contraseña, ese worker sobrante registra
        `NOAUTH` continuamente. Es el worker inactivo del nodo hablando con el almacén, no un
        fallo del sistema de jobs. El diagnóstico siguiente corresponde al host **Scheduler**.

### El broker rechaza la conexión (`NOAUTH`)

Si el broker tiene contraseña y `CELERY_BROKER_URL` no contiene credenciales, responde
`NOAUTH Authentication required`. El Worker sigue `active` sin consumir nada y `POST /jobs/dispatch`
devuelve `502`.

```bash
journalctl -u bunkerweb-worker | grep -i 'NOAUTH\|AuthenticationError'   # Linux
docker compose logs bw-worker | grep -i 'NOAUTH\|AuthenticationError'    # Docker
```

Primero verifica que el endpoint sea un broker de jobs dedicado con `maxmemory-policy noeviction`.
Si el puerto `6379` sirve un almacén WAF que expulsa claves, aprovisiona un broker separado mediante
el [instalador de Linux](integrations.md#script-de-instalacion-facil) o configúralo tú mismo y usa
su dirección y puerto reales. Corregir solo `NOAUTH` no protege los jobs ni los bloqueos temporales
contra la expulsión.

Después, asigna al broker sus credenciales. En Linux basta con escribir una vez en
`/etc/bunkerweb/variables.env`: Worker y API lo leen antes de su propio entorno. En contenedores,
configúralo en ambos servicios:

```bash
CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0     # Redis de la distribución dedicado, con noeviction
CELERY_BROKER_URL=redis://:<password>@bw-jobs-broker:6379/0 # Stack de contenedores
```

Comprueba `/etc/bunkerweb/broker.conf` antes de cambiar nada. Si existe, el instalador aprovisionó
un `bunkerweb-broker` dedicado y `CELERY_BROKER_URL` ya apunta a él **con contraseña**: modifica
esa línea y consulta su puerto; `6380` solo es el predeterminado y el instalador lo incrementa si
está ocupado. Si no existe, se usa tu URL o, si no la definiste, `redis://127.0.0.1:6379/0` en Linux,
y corresponde la corrección anterior. El instalador solo aprovisiona el broker en instalaciones
nuevas o actualizaciones con `requirepass` o un `maxmemory` que permita expulsiones. Un host
actualizado con Redis de distribución sin cambios, `--no-broker` o `--broker-url` no tiene ese archivo.

Después reinicia ambos: `systemctl restart bunkerweb-worker bunkerweb-api`, o recrea `bw-worker` y `bw-api`.

!!! warning "El broker no es el almacén WAF"
    El broker debe usar `maxmemory-policy noeviction`: contiene los bloqueos temporales que evitan
    envíos simultáneos de configuración desde dos workers. Son claves **con** TTL y cualquier
    política `volatile-*` puede expulsarlas durante el trabajo. El almacén suele tener límite y
    permitir expulsiones: perder contadores cuesta menos que rechazar escrituras. La política es
    por servidor, no por base de datos; distintos números de base en el mismo servidor **no**
    separan los roles. Consulta [las notas de actualización](upgrading.md#breaking-changes).

## Una instancia registrada no arranca {#lost-instance-credential}

Una instancia que canjea un código de registro guarda su credencial en
`/var/lib/bunkerweb/instance-credential.json` y desde entonces acepta **solo** esa credencial,
sin volver al `API_TOKEN` compartido. Si desaparece el archivo pero queda el marcador de registro,
se niega a arrancar y lo indica:

```
This instance was enrolled but its credential is gone (/var/lib/bunkerweb/instance-credential.json
is missing or contains no usable credential) [...] Refusing to start.
```

El disparador es concreto: existe el marcador pero no una credencial utilizable, porque el archivo
se borró, truncó, restauró sin credencial o quedó vacío. Si existe pero no se puede **leer** (por
ejemplo, pertenece a root tras actualizar), la instancia arranca y rechaza los envíos hasta que
se reparen los permisos. Restaura esos permisos en lugar de volver a registrarla.

Otros dos casos arrancan normalmente pero rechazan los envíos desde el plano de control: recrear
el contenedor **sin** volumen `/data` (se pierden marcador y credencial y vuelve como instancia nueva)
o restaurar una instantánea **anterior** al registro. La instancia solo registra
`can't validate API token from IP …` en cada llamada, sin explicar el registro perdido; el
diagnóstico está en el plano de control.

Dos maneras de resolver el rechazo al arrancar:

- **Mantener el registro**: emite un código nuevo con el botón de llave de **Instances** o
  `POST /instances/{hostname}/enroll` y pásalo como `INSTANCE_ENROLLMENT_CODE` en el siguiente arranque.
- **Volver al token compartido** requiere dos cambios. En la instancia, elimina
  `/var/lib/bunkerweb/instance-enrolled` **y** `instance-credential.json`: un archivo vacío o
  truncado restante hace que rechace cualquier token, incluido el compartido. Así arranca con
  `API_TOKEN`, pero el plano de control todavía conserva la credencial emitida y sigue usándola.
  Bórrala también en su fila:

    ```bash
    curl -X PATCH -H "Authorization: Bearer $API_TOKEN" -H 'Content-Type: application/json' \
      -d '{"credential": ""}' http://bw-api:8888/instances/<hostname>
    ```

    Una `credential` vacía borra la almacenada cualquiera que sea el método de la instancia y
    recupera el `API_TOKEN` compartido. Esta operación solo existe en la API: **Instances** ofrece
    rotar y revocar, no vaciar.

    **No levanta una revocación.** Si revocaste primero, vaciar la credencial no cambia nada: la
    fila sigue revocada y todos los envíos se rechazan. La levantan un código de registro nuevo o,
    para una instancia con token propio declarado (`BUNKERWEB_INSTANCE_API_TOKEN[_n]`, forma
    agrupada `BUNKERWEB_INSTANCE_HOST_n`; la lista simple `BUNKERWEB_INSTANCES` no contiene tokens),
    el siguiente guardado del scheduler, que vuelve a leer la credencial del entorno y levanta
    la revocación. El token declarado debe **diferir del `API_TOKEN` global**: repetir el compartido
    no cuenta y no produce ni cambio ni mensaje. Cuando se levanta, el scheduler lo registra.
    En cualquier otra fila, volver a registrarla es la única recuperación.

    Sin usar la API, una instancia **registrada desde la interfaz o la API** puede eliminarse en
    **Instances** (o `DELETE /instances/{hostname}`) y añadirse de nuevo. Una instancia **declarada
    en el entorno** (`BUNKERWEB_INSTANCES`) puede retirarse de la lista, guardarse una configuración
    del scheduler — elimina su fila, incluida la fijación TLS y el nombre configurados en la
    interfaz — y declararse otra vez. Ambas opciones descartan más datos que el `PATCH`.

    Una instancia **descubierta** por autoconf, Kubernetes o Swarm nunca tiene este problema:
    el plano de control no emite credenciales de registro para filas procedentes de un orquestador.

    **Volver a registrarla es la recuperación admitida; úsala preferentemente.**

!!! tip "Proporciona un `/data` persistente a la instancia"
    Los stacks de referencia montan `bw-instance-data` en `bunkerweb` para esto. Sin él, cada
    `docker compose down` seguido de `up` pierde la credencial y la instancia vuelve sin registro.
    Arranca correctamente y el rechazo solo aparece como envíos que no llegan desde el plano de
    control. Consulta [Registro de instancias](web-ui.md#instance-enrollment).

## Zona horaria

Cuando se utilizan integraciones basadas en contenedores, la zona horaria del contenedor puede no coincidir con la de la máquina anfitriona. Para resolver esto, puedes establecer la variable de entorno `TZ` a la zona horaria de tu elección en tus contenedores (p. ej., `TZ=Europe/Paris`). Encontrarás la lista de identificadores de zona horaria [aquí](https://es.wikipedia.org/wiki/Anexo:Lista_de_zonas_horarias_de_la_base_de_datos_IANA#Lista).

## Limpiar instancias antiguas de la base de datos {#clear-old-instances-db}

BunkerWeb almacena las instancias conocidas en la tabla `bw_instances` (clave primaria: `hostname`).
Si redespliegas con frecuencia, pueden quedar filas antiguas (por ejemplo, instancias que no han hecho check-in en mucho tiempo) y quizá quieras purgarlas.

!!! warning "Haz un backup primero"
    Antes de editar la base de datos manualmente, crea una copia de seguridad (haz un snapshot del volumen de SQLite o usa las herramientas de backup de tu motor de BD).

!!! warning "Detén a quienes escriben"
    Para evitar condiciones de carrera al eliminar, detén (o escala hacia abajo) los componentes que pueden actualizar instancias
    (normalmente el scheduler / autoconf según tu despliegue), ejecuta la limpieza y luego vuelve a iniciarlos.

### Tabla y columnas (referencia)

El modelo de instancia se define así:

- Tabla: `bw_instances`
- Clave primaria: `hostname`
- Marca de tiempo “visto por última vez”: `last_seen`
- También contiene:
  `name`, `port`, `listen_https`, `https_port`,
  `server_name`, `type`, `status`, `method`,
  `creation_date`

### 1 - Conectarse a la base de datos

Usa la sección existente [Acceso a la base de datos](#access-database) para conectarte
(SQLite / MariaDB / PostgreSQL).

### 2 - Dry-run: listar instancias obsoletas

Elige una ventana de retención (ejemplo: 90 días) y revisa qué se eliminaría.

=== "SQLite"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days')
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "MariaDB / MySQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY)
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

=== "PostgreSQL"

    ```sql
    SELECT hostname, name, server_name, method, status, creation_date, last_seen
    FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days'
    ORDER BY last_seen ASC
    LIMIT 50;
    ```

### 3 - Eliminar instancias obsoletas

Una vez verificado, elimina las filas.

=== "SQLite"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < datetime('now', '-90 days');

    COMMIT;
    ```

=== "MariaDB / MySQL"

    ```sql
    START TRANSACTION;

    DELETE FROM bw_instances
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 90 DAY);

    COMMIT;
    ```

=== "PostgreSQL"

    ```sql
    BEGIN;

    DELETE FROM bw_instances
    WHERE last_seen < NOW() - INTERVAL '90 days';

    COMMIT;
    ```

!!! tip "Eliminar por hostname"
    Para eliminar una instancia específica, usa su hostname (la clave primaria).

    ```sql
    DELETE FROM bw_instances WHERE hostname = '<hostname>';
    ```

### 4 - Marcar instancias como cambiadas (opcional)

BunkerWeb registra los cambios de instancias en la tabla `bw_metadata`
(`instances_changed`, `last_instances_change`).

Si la UI no se actualiza como esperas tras una limpieza manual,
puedes forzar una actualización del “marcador de cambios”:

=== "SQLite / PostgreSQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = CURRENT_TIMESTAMP
    WHERE id = 1;
    ```

=== "MariaDB / MySQL"

    ```sql
    UPDATE bw_metadata
    SET instances_changed = 1,
        last_instances_change = NOW()
    WHERE id = 1;
    ```

### 5 - Recuperar espacio (opcional)

=== "SQLite"

    ```sql
    VACUUM;
    ```

=== "PostgreSQL"

    ```sql
    VACUUM (ANALYZE);
    ```

=== "MariaDB / MySQL"

    ```sql
    OPTIMIZE TABLE bw_instances;
    ```

## Interfaz de usuario web {#web-ui}

En caso de que hayas olvidado tus credenciales de la interfaz de usuario o estés experimentando problemas con la 2FA, puedes conectarte a la base de datos para recuperar el acceso.

### Acceder a la base de datos {#access-database}

=== "SQLite"

    === "Linux"

        Instalar SQLite (Debian/Ubuntu):

        ```shell
        sudo apt install sqlite3
        ```

        Instalar SQLite (Fedora/RedHat):

        ```shell
        sudo dnf install sqlite
        ```

    === "Docker"

        Obtén un shell en tu contenedor del programador:

        !!! note "Argumentos de Docker"
            - la opción `-u 0` es para ejecutar el comando como root (obligatorio)
            - las opciones `-it` son para ejecutar el comando interactivamente (obligatorio)
            - `<bunkerweb_scheduler_container>`: el nombre o ID de tu contenedor del programador

        ```shell
        docker exec -u 0 -it <bunkerweb_scheduler_container> bash
        ```

        Instala SQLite:

        ```bash
        apk add sqlite
        ```

    === "Todo en uno"

        Obtén un shell en tu contenedor Todo en uno:

        !!! note "Argumentos de Docker"
            - la opción `-u 0` es para ejecutar el comando como root (obligatorio).
            - las opciones `-it` son para ejecutar el comando interactivamente (obligatorio).
            - `bunkerweb-aio` es el nombre del contenedor predeterminado; ajústalo si has usado un nombre personalizado.

        ```shell
        docker exec -u 0 -it bunkerweb-aio bash
        ```

    Accede a tu base de datos:

    !!! note "Ruta de la base de datos"
        Asumimos que estás utilizando la ruta de la base de datos predeterminada. Si estás utilizando una ruta personalizada, necesitarás adaptar el comando.
        Para Todo en uno, asumimos que la base de datos es `db.sqlite3` ubicada en el volumen persistente `/data` (`/data/db.sqlite3`).

    ```bash
    sqlite3 /var/lib/bunkerweb/db.sqlite3
    ```

    Deberías ver algo como esto:

    ```text
    SQLite version <VER> <DATE>
    Enter ".help" for usage hints.
    sqlite>
    ```

=== "MariaDB / MySQL"

    !!! note "Solo MariaDB / MySQL"
        Los siguientes pasos solo son válidos para bases de datos MariaDB / MySQL. Si estás utilizando otra base de datos, por favor consulta la documentación de tu base de datos.

    !!! note "Credenciales y nombre de la base de datos"
        Necesitarás usar las mismas credenciales y el nombre de la base de datos utilizados en la configuración `DATABASE_URI`.

    === "Linux"

        Accede a tu base de datos local:

        ```bash
        mysql -u <user> -p <database>
        ```

        Luego introduce la contraseña del usuario de la base de datos y deberías poder acceder a tu base de datos.

    === "Docker"

        Accede a tu contenedor de base de datos:

        !!! note "Argumentos de Docker"
            - la opción `-u 0` es para ejecutar el comando como root (obligatorio)
            - las opciones `-it` son para ejecutar el comando interactivamente (obligatorio)
            - `<bunkerweb_db_container>`: el nombre o ID de tu contenedor de base de datos
            - `<user>`: el usuario de la base de datos
            - `<database>`: el nombre de la base de datos

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> mysql -u <user> -p <database>
        ```

        Luego introduce la contraseña del usuario de la base de datos y deberías poder acceder a tu base de datos.

    === "Todo en uno"

        La imagen Todo en uno no incluye un servidor MariaDB/MySQL. Si has configurado la AIO para usar una base de datos externa MariaDB/MySQL (estableciendo la variable de entorno `DATABASE_URI`), deberías conectarte a esa base de datos directamente usando las herramientas de cliente de MySQL estándar.

        El método de conexión sería similar a la pestaña "Linux" (si te conectas desde el host donde se ejecuta la AIO u otra máquina) o ejecutando un cliente de MySQL en un contenedor de Docker separado si se prefiere, apuntando al host y las credenciales de tu base de datos externa.

=== "PostgreSQL"

    !!! note "Solo PostgreSQL"
        Los siguientes pasos solo son válidos para bases de datos PostgreSQL. Si estás utilizando otra base de datos, por favor consulta la documentación de tu base de datos.

    !!! note "Credenciales, host y nombre de la base de datos"
        Necesitarás usar las mismas credenciales (usuario/contraseña), host y nombre de la base de datos utilizados en la configuración `DATABASE_URI`.

    === "Linux"

        Accede a tu base de datos local:

        ```bash
        psql -U <user> -d <database>
        ```

        Si tu base de datos está en otro host, incluye el nombre de host/IP y el puerto:

        ```bash
        psql -h <host> -p 5432 -U <user> -d <database>
        ```

        Luego introduce la contraseña del usuario de la base de datos y deberías poder acceder a tu base de datos.

    === "Docker"

        Accede a tu contenedor de base de datos:

        !!! note "Argumentos de Docker"
            - la opción `-u 0` es para ejecutar el comando como root (obligatorio)
            - las opciones `-it` son para ejecutar el comando interactivamente (obligatorio)
            - `<bunkerweb_db_container>`: el nombre o ID de tu contenedor de base de datos
            - `<user>`: el usuario de la base de datos
            - `<database>`: el nombre de la base de datos

        ```shell
        docker exec -u 0 -it <bunkerweb_db_container> psql -U <user> -d <database>
        ```

        Si la base de datos está alojada en otro lugar, añade las opciones `-h <host>` y `-p 5432` en consecuencia.

    === "Todo en uno"

        La imagen Todo en uno no incluye un servidor PostgreSQL. Si has configurado la AIO para usar una base de datos externa PostgreSQL (estableciendo la variable de entorno `DATABASE_URI`), deberías conectarte a esa base de datos directamente usando las herramientas de cliente de PostgreSQL estándar.

        El método de conexión sería similar a la pestaña "Linux" (si te conectas desde el host donde se ejecuta la AIO u otra máquina) o ejecutando un cliente de PostgreSQL en un contenedor de Docker separado si se prefiere, apuntando al host y las credenciales de tu base de datos externa.

### Acciones de solución de problemas

!!! info "Esquema de las tablas"
    El esquema de la tabla `bw_ui_users` es el siguiente:

    | Campo         | Tipo                                                | Nulo | Clave | Predeterminado | Extra |
    | :------------ | :-------------------------------------------------- | :--- | :---- | :------------- | :---- |
    | username      | varchar(256)                                        | NO   | PRI   | NULL           |       |
    | email         | varchar(256)                                        | YES  | UNI   | NULL           |       |
    | password      | varchar(60)                                         | NO   |       | NULL           |       |
    | method        | enum('ui','scheduler','autoconf','manual','wizard') | NO   |       | NULL           |       |
    | admin         | tinyint(1)                                          | NO   |       | NULL           |       |
    | theme         | enum('light','dark')                                | NO   |       | NULL           |       |
    | language      | varchar(2)                                          | NO   |       | NULL           |       |
    | totp_secret   | varchar(256)                                        | YES  |       | NULL           |       |
    | creation_date | datetime                                            | NO   |       | NULL           |       |
    | update_date   | datetime                                            | NO   |       | NULL           |       |

=== "Recuperar nombre de usuario"

    Ejecuta el siguiente comando para extraer datos de la tabla `bw_ui_users`:

    ```sql
    SELECT * FROM bw_ui_users;
    ```

    Deberías ver algo como esto:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | :------- | :---- | :------- | :----- | :---- | :---- | :---------- | :------------ | :---------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

=== "Actualizar la contraseña del usuario administrador"

    Primero necesitas hashear la nueva contraseña usando el algoritmo bcrypt.

    Instala la librería de Python bcrypt:

    ```shell
    pip install bcrypt
    ```

    Genera tu hash (reemplaza `mypassword` con tu propia contraseña):

    ```shell
    python3 -c 'from bcrypt import hashpw, gensalt ; print(hashpw(b"""mypassword""", gensalt(rounds=10)).decode("utf-8"))'
    ```

    Puedes actualizar tu nombre de usuario / contraseña ejecutando este comando:

    ```sql
    UPDATE bw_ui_users SET password = '<password_hash>' WHERE admin = 1;
    ```

    Si vuelves a comprobar tu tabla `bw_ui_users` después de este comando:

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Deberías ver algo como esto:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | :------- | :---- | :------- | :----- | :---- | :---- | :---------- | :------------ | :---------- |
    | ***      | ***   | ***      | manual | 1     | light | ***         | ***           | ***         |

    Ahora deberías poder usar las nuevas credenciales para iniciar sesión en la interfaz de usuario web.

=== "Desactivar la autenticación 2FA para el usuario administrador"

    Puedes desactivar la 2FA ejecutando este comando:

    ```sql
    UPDATE bw_ui_users SET totp_secret = NULL WHERE admin = 1;
    ```

    Si vuelves a comprobar tu tabla `bw_ui_users` siguiendo este comando:

    ```sql
    SELECT * FROM bw_ui_users WHERE admin = 1;
    ```

    Deberías ver algo como esto:

    | username | email | password | method | admin | theme | totp_secret | creation_date | update_date |
    | :------- | :---- | :------- | :----- | :---- | :---- | :---------- | :------------ | :---------- |
    | ***      | ***   | ***      | manual | 1     | light | NULL        | ***           | ***         |

    Ahora deberías poder iniciar sesión en la interfaz de usuario web solo con tu nombre de usuario y contraseña sin 2FA.

=== "Actualizar los códigos de recuperación 2FA"

    Los códigos de recuperación se pueden actualizar en tu **página de perfil** de la interfaz de usuario web en la pestaña `Seguridad`.

=== "Exportar configuración y registros anonimizados"

    Usa la **página de Soporte** en la Interfaz de Usuario Web para recopilar rápidamente la configuración y los registros para la solución de problemas.

    - Abre la Interfaz de Usuario Web y ve a la página de Soporte.
    - Elige el alcance: exporta los ajustes globales o selecciona un Servicio específico.
    - Haz clic para descargar el archivo de configuración para el alcance elegido.
    - Opcionalmente descarga los registros: los registros exportados se anonimizan automáticamente (todas las direcciones IP y dominios están enmascarados).

### Cargar plugin

Puede que no sea posible cargar un plugin desde la interfaz de usuario en ciertas situaciones:

- Falta de un paquete para gestionar archivos comprimidos en tu integración, en cuyo caso necesitarás añadir los paquetes necesarios
- Navegador Safari: el 'modo seguro' puede impedirte añadir un plugin. Necesitarás hacer los cambios necesarios en tu máquina
