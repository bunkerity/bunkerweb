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

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

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

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

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

### Acceder a la base de datos

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
