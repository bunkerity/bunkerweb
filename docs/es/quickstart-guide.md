# Guía de inicio rápido

!!! info "Requisitos previos"

    Esperamos que ya estés familiarizado con los [conceptos básicos](concepts.md) y que hayas seguido las [instrucciones de integración](integrations.md) para tu entorno.

    Esta guía de inicio rápido asume que BunkerWeb es accesible desde Internet y que has configurado al menos dos dominios: uno para la interfaz de usuario web y otro para tu servicio web.

    **Requisitos del sistema**

    Las especificaciones mínimas recomendadas para BunkerWeb son una máquina con 2 (v)CPUs y 8 GB de RAM. Ten en cuenta que esto debería ser suficiente para entornos de prueba o configuraciones con muy pocos servicios.

    Para entornos de producción con muchos servicios que proteger, recomendamos al menos 4 (v)CPUs y 16 GB de RAM. Los recursos deben ajustarse en función de tu caso de uso, el tráfico de red y los posibles ataques DDoS que puedas enfrentar.

    Se recomienda encarecidamente habilitar la carga global de las reglas CRS (estableciendo el parámetro `USE_MODSECURITY_GLOBAL_CRS` en `yes`) si te encuentras en entornos con RAM limitada o en producción con muchos servicios. Puedes encontrar más detalles en la sección de [usos avanzados](advanced.md#running-many-services-in-production) de la documentación.

Esta guía de inicio rápido te ayudará a instalar rápidamente BunkerWeb y a proteger un servicio web utilizando la interfaz de usuario web.

Proteger las aplicaciones web existentes que ya son accesibles con el protocolo HTTP(S) es el objetivo principal de BunkerWeb: actuará como un [proxy inverso](https://es.wikipedia.org/wiki/Proxy_inverso) clásico con características de seguridad adicionales.

Consulta la [carpeta de ejemplos](https://github.com/bunkerity/bunkerweb/tree/v1.7.0-beta/examples) del repositorio para obtener ejemplos del mundo real.

## Configuración básica

=== "Todo en uno"

    Para desplegar el contenedor todo en uno, ejecuta el siguiente comando:

    ```shell
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.7.0-beta
    ```

    Por defecto, el contenedor expone:

    * 8080/tcp para HTTP
    * 8443/tcp para HTTPS
    * 8443/udp para QUIC
    * 7000/tcp para el acceso a la interfaz de usuario web sin BunkerWeb delante (no recomendado para producción)

    La imagen Todo en Uno viene con varios servicios integrados, que se pueden controlar mediante variables de entorno. Consulta la [sección de la imagen Todo en Uno (AIO)](integrations.md#all-in-one-aio-image) de la página de integraciones para más detalles.

=== "Linux"

    Usa el script de instalación fácil para configurar BunkerWeb en las distribuciones de Linux compatibles. Instala y configura automáticamente NGINX, añade el repositorio de BunkerWeb y configura los servicios necesarios.

    ```bash
    # Download the script and its checksum
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.7.0-beta/install-bunkerweb.sh
    curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.7.0-beta/install-bunkerweb.sh.sha256

    # Verify the checksum
    sha256sum -c install-bunkerweb.sh.sha256

    # Si la comprobación es exitosa, ejecuta el script
    chmod +x install-bunkerweb.sh
    sudo ./install-bunkerweb.sh
    ```

    !!! danger "Aviso de seguridad"
        Verifica siempre la integridad del script con la suma de comprobación proporcionada antes de ejecutarlo.

    #### Aspectos destacados del Easy Install

    - Detecta tu distribución de Linux y la arquitectura de CPU por adelantado y avisa si estás fuera de la matriz soportada antes de aplicar cambios.
    - Las indicaciones interactivas usan una TUI en línea mediante [gum](https://github.com/charmbracelet/gum) — menús con flechas y cursor `❯`, campos de contraseña enmascarados. En la primera ejecución interactiva, el script descarga el binario `gum` oficial desde la [release de GitHub](https://github.com/charmbracelet/gum/releases) (SHA256 fijado, verificación de firma cosign cuando cosign está instalado), lo ejecuta desde un directorio temporal y elimina ese directorio al salir — **no se instala ningún paquete del sistema, no se añade ninguna fuente apt/dnf, no queda ningún binario**. Si gum no puede obtenerse, el instalador usa un `whiptail` ya instalado en el sistema; si ninguno está disponible, usa indicaciones de texto plano.
    - Dos flags controlan la TUI: `--no-tui` (o `BW_INSTALL_TUI=no`) salta todos los niveles de TUI y usa indicaciones de texto plano; `--tui` exige una TUI operativa y aborta si gum no puede descargarse y no hay ningún whiptail existente disponible.
    - Cuando el instalador se ejecuta como tubería (`curl … | bash`) o stdin no es un TTY, sale con un error claro en lugar de aceptar silenciosamente cada valor por defecto. Usa `--yes` junto con los flags `--*` / variables de entorno `*_INPUT` apropiados para instalaciones no interactivas.
    - El flujo interactivo permite elegir el perfil de instalación (Full Stack, Manager, Worker, etc.); el modo Manager vincula el listener de la API interna a `0.0.0.0`, deshabilita el asistente y solicita la IP a incluir en la lista blanca (proporciónala con `--manager-ip` en ejecuciones no interactivas), mientras que el modo Worker exige las IP del Manager para su lista blanca.
    - Las instalaciones de tipo Manager pueden decidir si el servicio Web UI debe iniciarse, aunque el asistente permanezca deshabilitado.
    - El resumen indica si el servicio FastAPI se ejecutará, de modo que puedas activarlo o desactivarlo conscientemente mediante `--api` / `--no-api`.
    - CrowdSec se ofrece de forma interactiva solo en instalaciones Full Stack. En la CLI, `--crowdsec` y `--crowdsec-appsec` son válidos para Full Stack y Manager; los modos Worker, Scheduler-only, UI-only y API-only los rechazan.

    Para métodos de instalación avanzados (gestor de paquetes, tipos de instalación, indicadores no interactivos, integración con CrowdSec, etc.), consulta la [Integración con Linux](integrations.md#linux).

=== "Docker"

    Aquí está el archivo docker compose completo que puedes usar; ten en cuenta que más adelante conectaremos el servicio web a la red `bw-services`:

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for every service
      API_URL: "http://bw-api:8888"
      API_TOKEN: "changeme" # Remember to set a stronger token: every component authenticates to the API with it
      CELERY_BROKER_URL: "redis://bw-jobs-broker:6379/0"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
        volumes:
          - bw-instance-data:/data # Needed to detect a lost credential after enrolling this instance, see Instances in the web UI documentation
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.7.0-beta
        restart: "unless-stopped"
        environment:
          <<: *bw-env
          API_USERNAME: "changeme"
          API_PASSWORD: "Ch@ngeme1234"
        networks:
          - bw-universe
          - bw-db

      bw-worker:
        image: bunkerity/bunkerweb-worker:1.7.0-beta
        restart: "unless-stopped"
        depends_on:
          - bw-api
          - bw-jobs-broker
        volumes:
          # Its own volume: DATABASE_URI points at a real server here, so this /data holds
          # nothing but a scratch tree the worker rebuilds from the database -- no reason to
          # share the scheduler's.
          - bw-worker-storage:/data
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction on purpose: a broker that evicts under memory pressure drops queued
        # jobs on the floor, and nothing upstream would notice.
        # appendonly on purpose: a broker restart must not vaporise queued jobs.
        # AOF, not RDB ("--save" stays empty) -- a 60s RDB loss window on a job queue
        # means silently dropped work, which is what the at-least-once acks exist to stop.
        command:
          [
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "yes",
            "--maxmemory",
            "256mb",
            "--maxmemory-policy",
            "noeviction",
          ]
        volumes:
          - bw-jobs-broker-data:/data
        healthcheck:
          test: ["CMD", "valkey-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 10
          start_period: 5s
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.7.0-beta
        environment:
          <<: *bw-env
        volumes:
          - bw-ui-data:/data # This is used to persist the UI secrets (Flask secret, TOTP encryption keys, Biscuit keys)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis service for the persistence of reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy volatile-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      bw-worker-storage:
      bw-jobs-broker-data:
      redis-data:
      bw-ui-data:
      bw-instance-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

    !!! info "El volumen `bw-ui-data` no es opcional"
        Contiene las claves que descifran los secretos TOTP almacenados. Sin él, el 2FA se pierde en la siguiente recreación del contenedor — vea [El 2FA desaparece al recrear el contenedor](web-ui.md).

=== "Docker autoconf"

    Aquí está el archivo docker compose completo que puedes usar; ten en cuenta que más adelante conectaremos el servicio web a la red `bw-services`:

    ```yaml
    x-ui-env: &bw-ui-env
      # We anchor the environment variables to avoid duplication
      AUTOCONF_MODE: "yes"
      API_URL: "http://bw-api:8888"
      API_TOKEN: "changeme" # Remember to set a stronger token: every component authenticates to the API with it
      CELERY_BROKER_URL: "redis://bw-jobs-broker:6379/0"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.7.0-beta
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        labels:
          - "bunkerweb.INSTANCE=yes" # We set the instance label to allow the autoconf to detect the instance
        environment:
          <<: *bw-ui-env
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-instance-data:/data # Needed to detect a lost credential after enrolling this instance, see Instances in the web UI documentation
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: ""
          SERVER_NAME: ""
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Change it if needed
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.7.0-beta
        depends_on:
          - bw-docker
        environment:
          <<: *bw-ui-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.7.0-beta
        restart: "unless-stopped"
        environment:
          <<: *bw-ui-env
          API_USERNAME: "changeme"
          API_PASSWORD: "Ch@ngeme1234"
        networks:
          - bw-universe
          - bw-db

      bw-worker:
        image: bunkerity/bunkerweb-worker:1.7.0-beta
        restart: "unless-stopped"
        depends_on:
          - bw-api
          - bw-jobs-broker
        volumes:
          # Its own volume: DATABASE_URI points at a real server here, so this /data holds
          # nothing but a scratch tree the worker rebuilds from the database -- no reason to
          # share the scheduler's.
          - bw-worker-storage:/data
        environment:
          <<: *bw-ui-env
        networks:
          - bw-universe
          - bw-db

      bw-jobs-broker:
        image: valkey/valkey:8-alpine
        # noeviction on purpose: a broker that evicts under memory pressure drops queued
        # jobs on the floor, and nothing upstream would notice.
        # appendonly on purpose: a broker restart must not vaporise queued jobs.
        # AOF, not RDB ("--save" stays empty) -- a 60s RDB loss window on a job queue
        # means silently dropped work, which is what the at-least-once acks exist to stop.
        command:
          [
            "valkey-server",
            "--save",
            "",
            "--appendonly",
            "yes",
            "--maxmemory",
            "256mb",
            "--maxmemory-policy",
            "noeviction",
          ]
        volumes:
          - bw-jobs-broker-data:/data
        healthcheck:
          test: ["CMD", "valkey-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 10
          start_period: 5s
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.7.0-beta
        environment:
          <<: *bw-ui-env
          TOTP_ENCRYPTION_KEYS: "mysecret" # Remember to set a stronger secret key (see the Prerequisites section)
        volumes:
          - bw-ui-data:/data # This is used to persist the UI secrets (Flask secret, TOTP encryption keys, Biscuit keys)
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis service for the persistence of reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy volatile-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      bw-worker-storage:
      bw-jobs-broker-data:
      redis-data:
      bw-ui-data:
      bw-instance-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-docker:
        name: bw-docker
      bw-db:
        name: bw-db
    ```

=== "Kubernetes"

    La forma recomendada de instalar Kubernetes es usar el chart de Helm disponible en `https://repo.bunkerweb.io/charts`:

    ```shell
    helm repo add bunkerweb https://repo.bunkerweb.io/charts
    ```

    Luego puedes usar el chart de helm `bunkerweb` de ese repositorio:

    ```shell
    helm install mybw bunkerweb/bunkerweb --namespace bunkerweb --create-namespace
    ```

    Una vez instalado, puedes obtener la dirección IP del `LoadBalancer` para configurar tus dominios:

    ```shell
    kubectl -n bunkerweb get svc mybw-external -o=jsonpath='{.status.loadBalancer.ingress[0].ip}'
    ```

=== "Swarm"

    Docker Swarm vuelve a ser compatible en 1.7. La pila de referencia — con los servicios de API, Worker y el broker de jobs que necesita un despliegue Swarm, además de los requisitos de etiquetado de nodos, `mode: global` y `mode: host` que solo tiene Swarm — vive en la [sección de integración de Swarm](integrations.md#swarm), no aquí: no encaja en el formato breve de esta página de inicio rápido, y duplicarla en dos sitios haría que divergieran. Despliégala con `docker stack deploy`, no con `docker compose up`.

## Completa el asistente de configuración {#complete-the-setup-wizard}

!!! tip "Accediendo al asistente de configuración"

    Puedes acceder al asistente de configuración navegando a la URI `https://tu-fqdn-o-direccion-ip/setup` de tu servidor.

### Crea una cuenta de administrador

Deberías ver una página de configuración como esta:
<figure markdown>
  ![Página de inicio del Asistente de configuración](assets/img/ui-wizard-step1.png){ align=center }
  <figcaption>Página de inicio del Asistente de configuración</figcaption>
</figure>

Una vez en la página de configuración, puedes introducir el **nombre de usuario, correo electrónico y contraseña del administrador** y hacer clic en el botón "Siguiente".

### Configura el Proxy Inverso, HTTPS y otros ajustes avanzados

=== "Configuración básica"

    El siguiente paso te pedirá que introduzcas el **nombre del servidor** (dominio/FQDN) que utilizará la interfaz de usuario web.

    También puedes optar por habilitar [Let's Encrypt](features.md#lets-encrypt)

    <figure markdown>
      ![Asistente de configuración paso 2](assets/img/ui-wizard-step2.png){ align=center }
      <figcaption>Asistente de configuración paso 2</figcaption>
    </figure>

=== "Configuración avanzada"

    El siguiente paso te pedirá que introduzcas el **nombre del servidor** (dominio/FQDN) que utilizará la interfaz de usuario web.

    También puedes optar por habilitar [Let's Encrypt](features.md#lets-encrypt).

    Si expandes la sección `Ajustes avanzados`, también puedes configurar las siguientes opciones:

    * **Proxy Inverso**: Ajusta la configuración del Proxy Inverso para tu interfaz de administrador (p. ej., si quieres usar una ruta).
    * [**IP Real**](features.md#real-ip): Configura los ajustes de IP Real para identificar correctamente la dirección IP del cliente (p. ej., si estás detrás de un balanceador de carga o un CDN).
    * [**Certificado Personalizado**](features.md#custom-ssl-certificate): Sube un certificado TLS personalizado si no quieres usar Let's Encrypt.

    <figure markdown>
      ![Asistente de configuración paso 2](assets/img/ui-wizard-step2-advanced.png){ align=center }
      <figcaption>Asistente de configuración paso 2 (avanzado)</figcaption>
    </figure>

### Activación PRO

Si tienes una licencia PRO, puedes activarla introduciendo tu clave de licencia en la sección `Actualizar a PRO`. Esto habilitará las características PRO de BunkerWeb.

<figure markdown>
  ![Paso PRO del Asistente de configuración](assets/img/ui-wizard-step3.png){ align=center }
  <figcaption>Paso PRO del Asistente de configuración</figcaption>
</figure>

### Resumen de tu configuración

El último paso te dará un resumen de la configuración que has introducido. Puedes hacer clic en el botón "Configurar" para completar la configuración.

<figure markdown>
  ![Paso final del Asistente de configuración](assets/img/ui-wizard-step4.png){ align=center }
  <figcaption>Paso final del Asistente de configuración</figcaption>
</figure>


## Accediendo a la interfaz web

Ahora puedes acceder a la interfaz web navegando al dominio que configuraste en el paso anterior y a la URI si la cambiaste (el valor predeterminado es `https://tu-dominio/`).

<figure markdown>
  ![Página de inicio de sesión de la interfaz web](assets/img/ui-login.png){ align=center }
  <figcaption>Página de inicio de sesión de la interfaz web</figcaption>
</figure>

Ahora puedes iniciar sesión con la cuenta de administrador que creaste durante el asistente de configuración.

<figure markdown>
  ![Inicio de la interfaz web](assets/img/ui-home.png){ align=center }
  <figcaption>Inicio de la interfaz web</figcaption>
</figure>

## Creando un nuevo servicio

=== "Interfaz de usuario web"

    Puedes crear un nuevo servicio navegando a la sección `Servicios` de la interfaz web y haciendo clic en el botón `➕ Crear nuevo servicio`.

    Hay múltiples formas de crear un servicio usando la interfaz web:

    * El **Modo fácil** te guiará a través del proceso de creación de un nuevo servicio.
    * El **Modo avanzado** te permitirá configurar el servicio con más opciones.
    * El **Modo sin formato** te permitirá introducir la configuración directamente como si editaras el archivo `variables.env`.

    !!! tip "Servicio en borrador"

        Puedes crear un servicio en borrador para guardar tu progreso y volver a él más tarde. Simplemente haz clic en el botón `🌐 En línea` para cambiar el servicio al modo borrador.

    !!! info "La entrada fija `Default server`"

        Con `MULTISITE=yes`, la primera fila de la lista no es uno de tus servicios: es el reservado **Default server**, que responde a las solicitudes que no coinciden con ningún servicio configurado. Ábrelo para establecer el certificado, TLS, cabeceras y páginas de error que utiliza. No ofrece eliminar, clonar ni borrador — consulta [Configurar el Default Server](features.md#miscellaneous). Con `MULTISITE=no` esta fila no existe, y la lista comienza con tus propios servicios.

    === "Modo fácil"

        En este modo, puedes elegir entre las plantillas disponibles y rellenar los campos obligatorios.

        <figure markdown>
          ![Creación de servicio en modo fácil en la interfaz web](assets/img/ui-create-service-easy.png){ align=center }
          <figcaption>Creación de servicio en modo fácil en la interfaz web</figcaption>
        </figure>

        * Una vez que hayas seleccionado la plantilla, puedes rellenar los campos obligatorios y seguir las instrucciones para crear el servicio.
        * Una vez que hayas terminado de configurar el servicio, puedes hacer clic en el botón `💾 Guardar` para guardar la configuración.

    === "Modo avanzado"

        En este modo, puedes configurar el servicio con más opciones mientras ves todas las configuraciones disponibles de todos los diferentes plugins.

        <figure markdown>
          ![Creación de servicio en modo avanzado en la interfaz web](assets/img/ui-create-service-advanced.png){ align=center }
          <figcaption>Creación de servicio en modo avanzado en la interfaz web</figcaption>
        </figure>

        * Para navegar entre los diferentes plugins, puedes usar el menú de navegación en el lado izquierdo de la página.
        * Cada configuración tiene una pequeña pieza de información que te ayudará a entender lo que hace.
        * Una vez que hayas terminado de configurar el servicio, puedes hacer clic en el botón `💾 Guardar` para guardar la configuración.

    === "Modo sin formato"

        En este modo, puedes introducir la configuración directamente como si editaras el archivo `variables.env`.

        <figure markdown>
          ![Creación de servicio en modo SIN FORMATO en la interfaz web](assets/img/ui-create-service-raw.png){ align=center }
          <figcaption>Creación de servicio en modo SIN FORMATO en la interfaz web</figcaption>
        </figure>

        * Una vez que hayas terminado de configurar el servicio, puedes hacer clic en el botón `💾 Guardar` para guardar la configuración.

    🚀 Una vez que hayas guardado la configuración, deberías ver tu nuevo servicio en la lista de servicios.

    <figure markdown>
      ![Página de servicios de la interfaz web](assets/img/ui-services.png){ align=center }
      <figcaption>Página de servicios de la interfaz web</figcaption>
    </figure>

    Si deseas editar el servicio, puedes hacer clic en el nombre del servicio o en el botón `📝 Editar`.

=== "Todo en uno"

    Cuando se utiliza la imagen Todo en Uno, los nuevos servicios se configuran añadiendo variables de entorno al comando `docker run` para el contenedor `bunkerweb-aio`. Si el contenedor ya está en ejecución, debes detenerlo y eliminarlo, y luego volver a ejecutarlo con las variables de entorno actualizadas.

    Supongamos que quieres proteger una aplicación `myapp` (que se ejecuta en otro contenedor y es accesible como `http://myapp:8080` desde BunkerWeb) y hacerla disponible en `www.example.com`. Añadirías o modificarías las siguientes variables de entorno en tu comando `docker run`:

    ```shell
    # Primero, detén y elimina el contenedor existente si está en ejecución:
    # docker stop bunkerweb-aio
    # docker rm bunkerweb-aio

    # Luego, vuelve a ejecutar el contenedor bunkerweb-aio con variables de entorno adicionales/actualizadas:
    docker run -d \
      --name bunkerweb-aio \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
      # --- Añade/modifica estas variables de entorno para tu nuevo servicio ---
      -e MULTISITE=yes \
      -e SERVER_NAME="www.example.com" \
      -e "www.example.com_USE_REVERSE_PROXY=yes" \
      -e "www.example.com_REVERSE_PROXY_HOST=http://myapp:8080" \
      -e "www.example.com_REVERSE_PROXY_URL=/" \
      # --- Incluye cualquier otra variable de entorno existente para la UI, Redis, CrowdSec, etc. ---
      bunkerity/bunkerweb-all-in-one:1.7.0-beta
    ```

    Tu contenedor de aplicación (`myapp`) y el contenedor `bunkerweb-aio` deben estar en la misma red de Docker para que BunkerWeb pueda alcanzarlo usando el nombre de host `myapp`.

    **Ejemplo de configuración de red:**
    ```shell
    # 1. Crea una red de Docker personalizada (si aún no lo has hecho):
    docker network create my-app-network

    # 2. Ejecuta tu contenedor de aplicación en esta red:
    docker run -d --name myapp --network my-app-network tu-imagen-de-aplicacion

    # 3. Añade --network my-app-network al comando docker run de bunkerweb-aio:
    docker run -d \
      --name bunkerweb-aio \
      --network my-app-network \
      -v bw-storage:/data \
      -p 80:8080/tcp \
      -p 443:8443/tcp \
      -p 443:8443/udp \
    #   ... (todas las demás variables de entorno relevantes como se muestra en el ejemplo principal anterior) ...
      bunkerity/bunkerweb-all-in-one:1.7.0-beta
    ```

    Asegúrate de reemplazar `myapp` con el nombre o IP real de tu contenedor de aplicación y `http://myapp:8080` con su dirección y puerto correctos.

=== "Archivo variables.env de Linux"

    Asumimos que has seguido la [Configuración básica](#__tabbed_1_2) y que la integración con Linux está funcionando en tu máquina.

    Puedes crear un nuevo servicio editando el archivo `variables.env` ubicado en el directorio `/etc/bunkerweb/`.

    ```shell
    nano /etc/bunkerweb/variables.env
    ```

    Luego puedes añadir la siguiente configuración:

    ```shell
    SERVER_NAME=www.example.com
    MULTISITE=yes
    www.example.com_USE_REVERSE_PROXY=yes
    www.example.com_REVERSE_PROXY_URL=/
    www.example.com_REVERSE_PROXY_HOST=http://myapp:8080
    ```

    Luego puedes recargar el servicio `bunkerweb-scheduler` para aplicar los cambios.

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

=== "Docker"

    Asumimos que has seguido la [Configuración básica](#__tabbed_1_3) y que la integración con Docker está funcionando en tu máquina.

    Debes tener una red llamada `bw-services` para que puedas conectar tu aplicación existente y configurar BunkerWeb:

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Después de eso, puedes añadir manualmente el servicio en el archivo docker compose que creaste en el paso anterior:

    ```yaml
    ...

    services:
      ...
      bw-scheduler:
        ...
        environment:
          ...
          SERVER_NAME: "www.example.com" # Cuando usas la integración con Docker, puedes establecer la configuración directamente en el programador, asegúrate de establecer el nombre de dominio correcto
          MULTISITE: "yes" # Habilita el modo multisitio para que puedas añadir múltiples servicios
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/"
          www.example.com_REVERSE_PROXY_HOST: "http://myapp:8080"
          ...
    ```

    Luego puedes reiniciar el servicio `bw-scheduler` para aplicar los cambios.

    ```shell
    docker compose down bw-scheduler && docker compose up -d bw-scheduler
    ```

=== "Etiquetas de Docker autoconf"

    Asumimos que has seguido la [Configuración básica](#__tabbed_1_4) y que la integración de autoconfiguración de Docker está funcionando en tu máquina.

    Debes tener una red llamada `bw-services` para que puedas conectar tu aplicación existente y configurar BunkerWeb con etiquetas:

    ```yaml
    services:
      myapp:
    	  image: bunkerity/bunkerweb-hello:v1.0
    	  networks:
    	    - bw-services
    	  labels:
    	    - "bunkerweb.SERVER_NAME=www.example.com"
    	    - "bunkerweb.USE_REVERSE_PROXY=yes"
    	    - "bunkerweb.REVERSE_PROXY_URL=/"
    	    - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

    Hacer esto creará automáticamente un nuevo servicio con las etiquetas proporcionadas como configuración.

=== "Anotaciones de Kubernetes"

    Asumimos que has seguido la [Configuración básica](#__tabbed_1_5) y que la pila de Kubernetes está funcionando en tu clúster.

    Supongamos que tienes un Despliegue típico con un Servicio para acceder a la aplicación web desde dentro del clúster:

    ```yaml
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app
      labels:
    	app: app
    spec:
      replicas: 1
      selector:
    	matchLabels:
    	  app: app
      template:
    	metadata:
    	  labels:
    		app: app
    	spec:
    	  containers:
    	  - name: app
    		image: bunkerity/bunkerweb-hello:v1.0
    		ports:
    		- containerPort: 8080
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app
    spec:
      selector:
    	app: app
      ports:
    	- protocol: TCP
    	  port: 80
    	  targetPort: 8080
    ```

    Aquí está la definición de Ingress correspondiente para servir y proteger la aplicación web:

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      annotations:
        bunkerweb.io/DUMMY_SETTING: "value"
    spec:
      rules:
        - host: www.example.com
          http:
            paths:
              - path: /
                pathType: Prefix
                backend:
                  service:
                  name: svc-app
                  port:
                    number: 80
    ```

=== "Etiquetas de Swarm"

    Asumimos que has seguido la [Configuración básica](#__tabbed_1_5) y que la pila de Swarm está funcionando en tu clúster y conectada a una red llamada `bw-services` para que puedas conectar tu aplicación existente y configurar BunkerWeb con etiquetas:

    ```yaml
    services:
      myapp:
        image: bunkerity/bunkerweb-hello:v1.0
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/"
          - "bunkerweb.REVERSE_PROXY_HOST=http://myapp:8080"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## Para saber más

¡Felicidades! Acabas de instalar BunkerWeb y de asegurar tu primer servicio web. Ten en cuenta que BunkerWeb ofrece mucho más, tanto en términos de seguridad como de integraciones con otros sistemas y soluciones. Aquí tienes una lista de recursos y acciones que pueden ayudarte a seguir profundizando en el conocimiento de la solución:

- Únete a la comunidad de Bunker: [Discord](https://discord.com/invite/fTf46FmtyD), [LinkedIn](https://www.linkedin.com/company/bunkerity/), [GitHub](https://github.com/bunkerity), [X (Anteriormente Twitter)](https://x.com/bunkerity)
- Echa un vistazo al [blog oficial](https://www.bunkerweb.io/blog?utm_campaign=self&utm_source=doc)
- Explora [casos de uso avanzados](advanced.md) en la documentación
- [Ponte en contacto con nosotros](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) para discutir las necesidades de tu organización
