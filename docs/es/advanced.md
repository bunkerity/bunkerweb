# Usos avanzados

Muchos ejemplos de casos de uso del mundo real están disponibles en la carpeta [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/examples) del repositorio de GitHub.

También proporcionamos numerosos boilerplates, como archivos YAML para diversas integraciones y tipos de bases de datos. Estos están disponibles en la carpeta [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.8/misc/integrations).

Esta sección solo se enfoca en usos avanzados y ajustes de seguridad, consulta la [sección de características](features.md) de la documentación para ver todas las configuraciones disponibles.

!!! tip "Pruebas"
    Para realizar pruebas rápidas cuando el modo multisitio está habilitado (y si no tienes las entradas DNS adecuadas configuradas para los dominios) puedes usar curl con la cabecera HTTP Host de tu elección:
    ```shell
    curl -H "Host: app1.example.com" http://ip-o-fqdn-del-servidor
    ```

    Si estás usando HTTPS, necesitarás jugar con SNI:
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-del-servidor https://example.com
    ```

## Detrás de un balanceador de carga o proxy inverso {#behind-load-balancer-or-reverse-proxy}

!!! info "IP real"

    Cuando BunkerWeb está a su vez detrás de un balanceador de carga o un proxy inverso, necesitas configurarlo para que pueda obtener la dirección IP real de los clientes. **Si no lo haces, las características de seguridad bloquearán la dirección IP del balanceador de carga o del proxy inverso en lugar de la del cliente**.

BunkerWeb admite dos métodos para recuperar la dirección IP real del cliente:

- Usando el `protocolo PROXY`
- Usando una cabecera HTTP como `X-Forwarded-For`

Se pueden usar las siguientes configuraciones:

- `USE_REAL_IP`: habilitar/deshabilitar la recuperación de la IP real
- `USE_PROXY_PROTOCOL`: habilitar/deshabilitar el soporte del protocolo PROXY.
- `REAL_IP_FROM`: lista de direcciones IP/red de confianza permitidas para enviarnos la "IP real"
- `REAL_IP_HEADER`: la cabecera HTTP que contiene la IP real o el valor especial `proxy_protocol` cuando se usa el protocolo PROXY

Encontrarás más configuraciones sobre la IP real en la [sección de características](features.md#real-ip) de la documentación.

=== "Cabecera HTTP"

    Asumiremos lo siguiente con respecto a los balanceadores de carga o proxies inversos (necesitarás actualizar la configuración dependiendo de tu configuración):

    - Usan la cabecera `X-Forwarded-For` para establecer la IP real
    - Tienen IPs en las redes `1.2.3.0/24` y `100.64.0.0/10`

    === "Interfaz de usuario web"

        Navega a la página de **Configuración Global**, selecciona el plugin **Real IP** y completa las siguientes configuraciones:

        <figure markdown>![Configuración de IP real (cabecera) usando la interfaz de usuario web](assets/img/advanced-proxy1.png){ align=center }<figcaption>Configuración de IP real (cabecera) usando la interfaz de usuario web</figcaption></figure>

        Ten en cuenta que se recomienda reiniciar BunkerWeb cuando cambies la configuración relacionada con la IP real.

    === "Linux"

        Necesitarás agregar la configuración al archivo `/etc/bunkerweb/variables.env`:

        ```conf
        ...
        USE_REAL_IP=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=X-Forwarded-For
        ...
        ```

        Ten en cuenta que se recomienda emitir un reinicio en lugar de una recarga al configurar ajustes relacionados con la IP real:

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Todo en uno"

        Necesitarás agregar la configuración a las variables de entorno al ejecutar el contenedor Todo en uno:

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker autoconf"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Kubernetes"

        Necesitarás agregar la configuración a las variables de entorno de los pods de BunkerWeb y del programador.

        Aquí está la parte correspondiente de tu archivo `values.yaml` que puedes usar:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "X-Forwarded-For"
        ```

    === "Swarm"

        !!! warning "Obsoleto"
            La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

            **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

        Necesitarás agregar la configuración a las variables de entorno de los servicios de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        ```

        Ten en cuenta que si tu servicio ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

=== "Protocolo Proxy"

    !!! warning "Lee con atención"

        Solo usa el protocolo PROXY si estás seguro de que tu balanceador de carga o proxy inverso lo está enviando. **Si lo habilitas y no se está usando, obtendrás errores**.

    Asumiremos lo siguiente con respecto a los balanceadores de carga o proxies inversos (necesitarás actualizar la configuración dependiendo de tu configuración):

    - Usan el `protocolo PROXY` v1 o v2 para establecer la IP real
    - Tienen IPs en las redes `1.2.3.0/24` y `100.64.0.0/10`

    === "Interfaz de usuario web"

        Navega a la página de **Configuración Global**, selecciona el plugin **Real IP** y completa las siguientes configuraciones:

        <figure markdown>![Configuración de IP real (protocolo PROXY) usando la interfaz de usuario web](assets/img/advanced-proxy2.png){ align=center }<figcaption>Configuración de IP real (protocolo PROXY) usando la interfaz de usuario web</figcaption></figure>

        Ten en cuenta que se recomienda reiniciar BunkerWeb cuando cambies la configuración relacionada con la IP real.

    === "Linux"

        Necesitarás agregar la configuración al archivo `/etc/bunkerweb/variables.env`:

        ```conf
        ...
        USE_REAL_IP=yes
        USE_PROXY_PROTOCOL=yes
        REAL_IP_FROM=1.2.3.0/24 100.64.0.0/16
        REAL_IP_HEADER=proxy_protocol
        ...
        ```

        Ten en cuenta que se recomienda emitir un reinicio en lugar de una recarga al configurar ajustes relacionados con los protocolos proxy:

        ```shell
        sudo systemctl restart bunkerweb && \
        sudo systemctl restart bunkerweb-scheduler
        ```

    === "Todo en uno"

        Necesitarás agregar la configuración a las variables de entorno al ejecutar el contenedor Todo en uno:

        ```bash
        docker run -d \
            --name bunkerweb-aio \
            -v bw-storage:/data \
            -e USE_REAL_IP="yes" \
            -e USE_PROXY_PROTOCOL="yes" \
            -e REAL_IP_FROM="1.2.3.0/24 100.64.0.0/10" \
            -e REAL_IP_HEADER="X-Forwarded-For" \
            -p 80:8080/tcp \
            -p 443:8443/tcp \
            -p 443:8443/udp \
            bunkerity/bunkerweb-all-in-one:1.6.8
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker autoconf"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Kubernetes"

        Necesitarás agregar la configuración a las variables de entorno de los pods de BunkerWeb y del programador.

        Aquí está la parte correspondiente de tu archivo `values.yaml` que puedes usar:

        ```yaml
        bunkerweb:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        scheduler:
          extraEnvs:
            - name: USE_REAL_IP
              value: "yes"
            - name: USE_PROXY_PROTOCOL
              value: "yes"
            - name: REAL_IP_FROM
              value: "1.2.3.0/24 100.64.0.0/10"
            - name: REAL_IP_HEADER
              value: "proxy_protocol"
        ```

    === "Swarm"

        !!! warning "Obsoleto"
            La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

            **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

        Necesitarás agregar la configuración a las variables de entorno de los servicios de BunkerWeb y del programador.

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.8
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Ten en cuenta que si tu servicio ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

## Alta disponibilidad y balanceo de carga

Para que tus aplicaciones sigan disponibles incluso si un servidor falla, puedes desplegar BunkerWeb en un clúster de **Alta Disponibilidad (HA)**. Esta arquitectura incluye un **Manager** (Scheduler) que orquesta la configuración y varios **Workers** (instancias BunkerWeb) que manejan el tráfico.

```mermaid
flowchart LR

  %% ================ Styles =================
  classDef manager     fill:#eef2ff,stroke:#4c1d95,stroke-width:1px,rx:6px,ry:6px;
  classDef component     fill:#f9fafb,stroke:#6b7280,stroke-width:1px,rx:4px,ry:4px;
  classDef lb            fill:#e0f2fe,stroke:#0369a1,stroke-width:1px,rx:6px,ry:6px;
  classDef database fill:#d1fae5,stroke:#059669,stroke-width:1px,rx:4px,ry:4px;
  classDef datastore     fill:#fee2e2,stroke:#b91c1c,stroke-width:1px,rx:4px,ry:4px;
  classDef backend       fill:#ede9fe,stroke:#7c3aed,stroke-width:1px,rx:4px,ry:4px;
  classDef client        fill:#e5e7eb,stroke:#4b5563,stroke-width:1px,rx:4px,ry:4px;

  %% Container styles
  style CLUSTER fill:#f3f4f6,stroke:#d1d5db,stroke-width:1px,stroke-dasharray:6 3;
  style WORKERS fill:none,stroke:#9ca3af,stroke-width:1px,stroke-dasharray:4 2;

  %% ============== Outside left =============
  Client["Cliente"]:::client
  LB["Load Balancer"]:::lb

  %% ============== Cluster ==================
  subgraph CLUSTER[" "]
    direction TB

    %% ---- Top row: Manager + Redis ----
    subgraph TOP["Manager & Data Stores"]
      direction LR
      Manager["Manager<br/>(Scheduler)"]:::manager
      BDD["BDD"]:::database
      Redis["Redis/Valkey"]:::datastore
      UI["Interfaz Web"]:::manager
    end

    %% ---- Middle: Workers ----
    subgraph WORKERS["Workers (BunkerWeb)"]
      direction TB
      Worker1["Worker 1"]:::component
      WorkerN["Worker N"]:::component
    end

    %% ---- Bottom: App ----
    App["App"]:::backend
  end

  %% ============ Outside right ============
  Admin["Admin"]:::client

  %% ============ Traffic & control ===========
  %% Manager / control plane
  Manager -->|API 5000| Worker1
  Manager -->|API 5000| WorkerN
  Manager -->|bwcli| Redis
  Manager -->|Config| BDD

  %% User interface (UI)
  UI -->|Config| BDD
  UI -->|Reports / Bans| Redis
  BDD --- UI
  Redis --- UI
  linkStyle 6 stroke-width:0px;
  linkStyle 7 stroke-width:0px;

  %% Workers <-> Redis
  Worker1 -->|Caché compartida| Redis
  WorkerN -->|Caché compartida| Redis

  %% Workers -> App
  Worker1 -->|Tráfico legítimo| App
  WorkerN -->|Tráfico legítimo| App

  %% Client (right side) -> Load balancer -> Workers -> App
  Client -->|Petición| LB
  LB -->|HTTP/TCP| Worker1
  LB -->|HTTP/TCP| WorkerN

  %% Admin -> UI
  UI --- Admin
  Admin -->|HTTP| UI
  linkStyle 15 stroke-width:0px;
```

!!! info "Cómo funcionan las API de BunkerWeb"
    BunkerWeb maneja dos conceptos distintos de API:

    - Una **API interna** que conecta automáticamente managers y workers para la orquestación. Siempre está habilitada y no requiere configuración manual.
    - Un **servicio API** opcional (`bunkerweb-api`) que expone una interfaz REST pública para herramientas de automatización (bwcli, CI/CD, etc.). Está deshabilitada por defecto en instalaciones Linux y es independiente de las comunicaciones internas manager↔worker.

### Requisitos previos

Antes de configurar un clúster, asegúrate de contar con:

- **2 o más hosts Linux** con acceso root/sudo.
- **Conectividad de red** entre los hosts (especialmente en el puerto TCP 5000 para la API interna).
- **IP o hostname** de la aplicación a proteger.
- *(Opcional)* **Load Balancer** (p. ej. HAProxy) para repartir el tráfico entre los workers.

### 1. Instalar el Manager

El Manager es el cerebro del clúster. Ejecuta el Scheduler, la base de datos y, opcionalmente, la interfaz web.

!!! warning "Seguridad de la interfaz web"
    La interfaz web escucha en un puerto dedicado (7000 por defecto) y solo debería ser accesible por administradores. Si piensas exponerla a internet, **recomendamos encarecidamente** protegerla con una instancia de BunkerWeb delante.

=== "Linux"

    1. **Descarga y ejecuta el instalador** en el host del manager:

        ```bash
        # Descargar script y checksum
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8/install-bunkerweb.sh
        curl -fsSL -O https://github.com/bunkerity/bunkerweb/releases/download/v1.6.8/install-bunkerweb.sh.sha256

        # Verificar checksum
        sha256sum -c install-bunkerweb.sh.sha256

        # Ejecutar instalador
        chmod +x install-bunkerweb.sh
        sudo ./install-bunkerweb.sh
        ```

        !!! danger "Aviso de seguridad"
            Comprueba siempre la integridad del script con el checksum proporcionado antes de ejecutarlo.

    2. **Selecciona la opción 2) Manager** y sigue las indicaciones:

        | Pregunta                      | Acción                                                                                                  |
        | :---------------------------- | :------------------------------------------------------------------------------------------------------ |
        | **Instancias BunkerWeb**      | Introduce las IP de tus nodos worker separadas por espacios (ej.: `192.168.10.11 192.168.10.12`).       |
        | **Whitelist IP**              | Acepta la IP detectada o introduce un subnet (ej.: `192.168.10.0/24`) para permitir el acceso a la API. |
        | **Resolutores DNS**           | Pulsa `N` para usar el valor por defecto o indica los tuyos.                                            |
        | **HTTPS para la API interna** | **Recomendado:** `Y` para generar certificados y asegurar la comunicación manager-worker.               |
        | **Servicio Web UI**           | `Y` para activar la interfaz web (muy recomendado).                                                     |
        | **Servicio API**              | `N` salvo que necesites la API REST pública para herramientas externas.                                 |

    #### Asegurar y exponer la UI

    Si activaste la interfaz web, debes asegurarla. Puedes alojarla en el Manager o en una máquina separada.

    === "Alojada en el Manager"

        1. Edita `/etc/bunkerweb/ui.env` y define credenciales fuertes:

        ```ini
        # OVERRIDE_ADMIN_CREDS=no
        ADMIN_USERNAME=admin
        ADMIN_PASSWORD=changeme
        # FLASK_SECRET=changeme
        # TOTP_ENCRYPTION_KEYS=changeme
        LISTEN_ADDR=0.0.0.0
        # LISTEN_PORT=7000
        FORWARDED_ALLOW_IPS=127.0.0.1,::1
        # ENABLE_HEALTHCHECK=no
        ```

        !!! warning "Cambia las credenciales por defecto"
            Sustituye `admin` y `changeme` por credenciales robustas antes de arrancar el servicio UI en producción.

        2. Reinicia la UI:

        ```bash
        sudo systemctl restart bunkerweb-ui
        ```

    === "Host externo"

        Para más aislamiento, instala la UI en un nodo independiente.

        1. Ejecuta el instalador y elige **Opción 5) Web UI Only**.
        2. Edita `/etc/bunkerweb/ui.env` para apuntar a la base de datos del Manager:

            ```ini
            # Configuración de base de datos (debe coincidir con la del Manager)
            DATABASE_URI=mariadb+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb
            # Para PostgreSQL: postgresql://bunkerweb:changeme@db-host:5432/bunkerweb
            # Para MySQL: mysql+pymysql://bunkerweb:changeme@db-host:3306/bunkerweb

            # Configuración de Redis (si usas Redis/Valkey para persistencia)
            # Si no se proporciona, se toma automáticamente de la base de datos
            # REDIS_HOST=redis-host

            # Credenciales de seguridad
            ADMIN_USERNAME=admin
            ADMIN_PASSWORD=changeme

            # Ajustes de red
            LISTEN_ADDR=0.0.0.0
            # LISTEN_PORT=7000
            ```

        3. Reinicia el servicio:

            ```bash
            sudo systemctl restart bunkerweb-ui
            ```

        !!! tip "Configuración de firewall"
            Asegúrate de que el host de la UI pueda llegar a los puertos de base de datos y Redis. Puede que debas ajustar las reglas de firewall tanto en el host de la UI como en los hosts de la base/Redis.

=== "Docker"

    Crea un archivo `docker-compose.yml` en el host del manager:

    ```yaml title="docker-compose.yml"
    x-ui-env: &bw-ui-env
      # Anclamos las variables de entorno para evitar duplicaciones
      DATABASE_URI: \"mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db\" # Usa una contraseña más fuerte

    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-ui-env
          BUNKERWEB_INSTANCES: \"192.168.1.11 192.168.1.12\" # Sustituye por las IP de tus workers
          API_WHITELIST_IP: \"127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16\" # Permitir redes locales
          # API_LISTEN_HTTPS: \"yes\" # Recomendado para asegurar la API interna
          # API_TOKEN: \"my_secure_token\" # Opcional: token adicional
          SERVER_NAME: \"\"
          MULTISITE: \"yes\"
          USE_REDIS: \"yes\"
          REDIS_HOST: \"redis\"
        volumes:
          - bw-storage:/data # Persistencia del caché y backups
        restart: \"unless-stopped\"
        networks:
          - bw-db
          - bw-redis

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8
        ports:
          - \"7000:7000\" # Exponer el puerto de la UI
        environment:
          <<: *bw-ui-env
          ADMIN_USERNAME: \"changeme\"
          ADMIN_PASSWORD: \"changeme\" # Usa una contraseña más fuerte
          TOTP_ENCRYPTION_KEYS: \"mysecret\" # Usa una clave más fuerte (ver requisitos previos)
        restart: \"unless-stopped\"
        networks:
          - bw-db
          - bw-redis

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: \"yes\"
          MYSQL_DATABASE: \"db\"
          MYSQL_USER: \"bunkerweb\"
          MYSQL_PASSWORD: \"changeme\" # Usa una contraseña más fuerte
        volumes:
          - bw-data:/var/lib/mysql
        restart: \"unless-stopped\"
        networks:
          - bw-db

      redis: # Redis para la persistencia de informes/prohibiciones/estadísticas
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: \"unless-stopped\"
        networks:
          - bw-redis

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-db:
        name: bw-db
      bw-redis:
        name: bw-redis
    ```

    Arranca el stack del manager:

    ```bash
    docker compose up -d
    ```

### 2. Instalar los Workers

Los workers son los nodos que procesan el tráfico entrante.

=== "Linux"

    1. **Ejecuta el instalador** en cada nodo worker (mismos comandos que para el Manager).
    2. **Selecciona la opción 3) Worker** y configura:

        | Pregunta                      | Acción                                                |
        | :---------------------------- | :---------------------------------------------------- |
        | **IP del Manager**            | Introduce la IP de tu Manager (ej.: `192.168.10.10`). |
        | **HTTPS para la API interna** | Debe coincidir con el ajuste del Manager (`Y` o `N`). |

    El worker se registrará automáticamente en el Manager.

=== "Docker"

    Crea un archivo `docker-compose.yml` en cada worker:

    ```yaml title="docker-compose.yml"
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - \"80:8080/tcp\"
          - \"443:8443/tcp\"
          - \"443:8443/udp\" # Compatibilidad QUIC / HTTP3
          - \"5000:5000/tcp\" # Puerto de la API interna
        environment:
          API_WHITELIST_IP: \"127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16\"
          # API_LISTEN_HTTPS: \"yes\" # Recomendado para asegurar la API interna (debe coincidir con el Manager)
          # API_TOKEN: \"my_secure_token\" # Opcional: token adicional (debe coincidir con el Manager)
        restart: \"unless-stopped\"
    ```

    Inicia el worker:

    ```bash
    docker compose up -d
    ```

### 3. Gestionar los Workers

Puedes añadir más workers más adelante usando la interfaz web o la CLI.

=== "Vía interfaz web"

    1. **Ve a la pestaña Instances**.
    2. **Haz clic en Add instance**.
    3. **Introduce la IP/hostname del worker** y guarda.

    <div class=\"grid grid-2\" markdown style=\"display:grid; align-items:center;\">
    <figure markdown style=\"display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;\">
      ![BunkerWeb UI - Crear instancia](assets/img/ui-ha-create-instance.webp){ width=\"100%\" }
      <figcaption>BunkerWeb UI - Crear instancia</figcaption>
    </figure>
    <figure markdown style=\"display:flex; flex-direction:column; justify-content:center; align-items:center; height:100%;\">
      ![BunkerWeb UI - Formulario de instancia](assets/img/ui-ha-create-instance-form.webp){ width=\"100%\" }
      <figcaption>BunkerWeb UI - Formulario de instancia</figcaption>
    </figure>
    </div>

=== \"Vía configuración\"

    === \"Linux\"

        1. **Edita** `/etc/bunkerweb/variables.env` en el Manager:

            ```bash
            BUNKERWEB_INSTANCES=192.168.10.11 192.168.10.12 192.168.10.13
            ```

        2. **Reinicia el Scheduler**:

            ```bash
            sudo systemctl restart bunkerweb-scheduler
            ```

    === \"Docker\"

        1. **Edita** el archivo `docker-compose.yml` en el Manager para actualizar `BUNKERWEB_INSTANCES`.

        2. **Recrea el contenedor del Scheduler**:

            ```bash
            docker compose up -d bw-scheduler
            ```

### 4. Verificar la instalación

=== "Linux"

    1. **Comprobar estado**: accede a la UI (`http://<ip-manager>:7000`) y abre la pestaña **Instances**. Todos los workers deben aparecer **Up**.
    2. **Probar conmutación**: detén BunkerWeb en un worker (`sudo systemctl stop bunkerweb`) y verifica que el tráfico sigue fluyendo.

=== "Docker"

    1. **Comprobar estado**: accede a la UI (`http://<ip-manager>:7000`) y abre la pestaña **Instances**. Todos los workers deben aparecer **Up**.
    2. **Probar conmutación**: detén BunkerWeb en un worker (`docker compose stop bunkerweb`) y verifica que el tráfico sigue fluyendo.

### 5. Balanceo de carga

Para repartir el tráfico entre tus workers, utiliza un Load Balancer. Recomendamos uno de capa 4 (TCP) que soporte **PROXY protocol** para preservar la IP del cliente.

=== "HAProxy - Capa 4 (TCP)"

    Ejemplo de configuración **HAProxy** que pasa el tráfico (modo TCP) manteniendo la IP cliente mediante **PROXY protocol**.

    ```cfg title=\"haproxy.cfg\"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode tcp
        bind *:80
        default_backend http_back

    frontend https_front
        mode tcp
        bind *:443
        default_backend https_back

    backend http_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:80 check send-proxy-v2
        server worker02 192.168.10.12:80 check send-proxy-v2

    backend https_back
        mode tcp
        balance roundrobin
        server worker01 192.168.10.11:443 check send-proxy-v2
        server worker02 192.168.10.12:443 check send-proxy-v2
    ```

=== "HAProxy - Capa 7 (HTTP)"

    Ejemplo de configuración **HAProxy** para balanceo en capa 7 (HTTP). Añade la cabecera `X-Forwarded-For` para que BunkerWeb obtenga la IP del cliente.

    ```cfg title=\"haproxy.cfg\"
    defaults
        timeout connect 5s
        timeout client 5s
        timeout server 5s

    frontend http_front
        mode http
        bind *:80
        default_backend http_back

    frontend https_front
        mode http
        bind *:443
        default_backend https_back

    backend http_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:80 check
        server worker02 192.168.10.12:80 check

    backend https_back
        mode http
        balance roundrobin
        option forwardfor
        server worker01 192.168.10.11:443 check
        server worker02 192.168.10.12:443 check
    ```

Reinicia HAProxy una vez guardada la configuración:

```bash
sudo systemctl restart haproxy
```

Para más información, consulta la [documentación oficial de HAProxy](http://docs.haproxy.org/).

!!! tip "Configurar IP real"
    No olvides configurar BunkerWeb para recibir la IP real del cliente (usando PROXY protocol o la cabecera X-Forwarded-For).

    Consulta la sección [Detrás de un balanceador de carga o proxy inverso](#behind-load-balancer-or-reverse-proxy) para asegurarte de que recibes la IP correcta del cliente.

    Revisa `/var/log/bunkerweb/access.log` en cada worker para confirmar que las solicitudes llegan desde la red del PROXY protocol y que los dos workers comparten la carga. Tu clúster BunkerWeb ya está listo para proteger cargas de producción con alta disponibilidad.

## Usando mecanismos de resolución DNS personalizados

La configuración de NGINX de BunkerWeb se puede personalizar para usar diferentes resolutores de DNS según tus necesidades. Esto puede ser particularmente útil en varios escenarios:

1. Para respetar las entradas en tu archivo local `/etc/hosts`
2. Cuando necesitas usar servidores DNS personalizados para ciertos dominios
3. Para integrarse con soluciones locales de caché de DNS

### Usando systemd-resolved

Muchos sistemas Linux modernos usan `systemd-resolved` para la resolución de DNS. Si quieres que BunkerWeb respete el contenido de tu archivo `/etc/hosts` y use el mecanismo de resolución de DNS del sistema, puedes configurarlo para que use el servicio DNS local de systemd-resolved.

Para verificar que systemd-resolved se está ejecutando en tu sistema, puedes usar:

```bash
systemctl status systemd-resolved
```

Para habilitar systemd-resolved como tu resolutor de DNS en BunkerWeb, establece la configuración `DNS_RESOLVERS` a `127.0.0.53`, que es la dirección de escucha predeterminada para systemd-resolved:

=== "Interfaz de usuario web"

    Navega a la página de **Configuración Global** y establece los resolutores de DNS en `127.0.0.53`

    <figure markdown>![Configuración de resolutores de DNS usando la interfaz de usuario web](assets/img/advanced-dns-resolvers.png){ align=center }<figcaption>Configuración de resolutores de DNS usando la interfaz de usuario web</figcaption></figure>

=== "Linux"

    Necesitarás modificar el archivo `/etc/bunkerweb/variables.env`:

    ```conf
    ...
    DNS_RESOLVERS=127.0.0.53
    ...
    ```

    Después de hacer este cambio, recarga el Programador para aplicar la configuración:

    ```shell
    sudo systemctl reload bunkerweb-scheduler
    ```

### Usando dnsmasq

[dnsmasq](http://www.thekelleys.org.uk/dnsmasq/doc.html) es un servidor ligero de DNS, DHCP y TFTP que se usa comúnmente para el almacenamiento en caché y la personalización de DNS local. Es particularmente útil cuando necesitas más control sobre tu resolución de DNS del que proporciona systemd-resolved.

=== "Linux"

    Primero, instala y configura dnsmasq en tu sistema Linux:

    === "Debian/Ubuntu"

        ```bash
        # Instalar dnsmasq
        sudo apt-get update && sudo apt-get install dnsmasq

        # Configurar dnsmasq para escuchar solo en localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Agregar entradas DNS personalizadas si es necesario
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Reiniciar dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    === "RHEL/Fedora"

        ```bash
        # Instalar dnsmasq
        sudo dnf install dnsmasq

        # Configurar dnsmasq para escuchar solo en localhost
        echo "listen-address=127.0.0.1" | sudo tee -a /etc/dnsmasq.conf
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf

        # Agregar entradas DNS personalizadas si es necesario
        echo "address=/custom.example.com/192.168.1.10" | sudo tee -a /etc/dnsmasq.conf

        # Reiniciar dnsmasq
        sudo systemctl restart dnsmasq
        sudo systemctl enable dnsmasq
        ```

    Luego configura BunkerWeb para que use dnsmasq estableciendo `DNS_RESOLVERS` en `127.0.0.1`:

    === "Interfaz de usuario web"

        Navega a la página de **Configuración Global**, selecciona el plugin **NGINX** y establece los resolutores de DNS en `127.0.0.1`.

        <figure markdown>![Configuración de resolutores de DNS usando la interfaz de usuario web](assets/img/advanced-dns-resolvers2.png){ align=center }<figcaption>Configuración de resolutores de DNS usando la interfaz de usuario web</figcaption></figure>

    === "Linux"

        Necesitarás modificar el archivo `/etc/bunkerweb/variables.env`:

        ```conf
        ...
        DNS_RESOLVERS=127.0.0.1
        ...
        ```

        Después de hacer este cambio, recarga el Programador:

        ```shell
        sudo systemctl reload bunkerweb-scheduler
        ```

=== "Todo en uno"

    Cuando uses el contenedor Todo en uno, ejecuta dnsmasq en un contenedor separado y configura BunkerWeb para usarlo:

    ```bash
    # Crear una red personalizada para la comunicación DNS
    docker network create bw-dns

    # Ejecutar el contenedor dnsmasq usando dockurr/dnsmasq con Quad9 DNS
    # Quad9 proporciona resolución de DNS centrada en la seguridad con bloqueo de malware
    docker run -d \
        --name dnsmasq \
        --network bw-dns \
        -e DNS1="9.9.9.9" \
        -e DNS2="149.112.112.112" \
        -p 53:53/udp \
        -p 53:53/tcp \
        --cap-add=NET_ADMIN \
        --restart=always \
        dockurr/dnsmasq

    # Ejecutar BunkerWeb Todo en uno con el resolutor de DNS dnsmasq
    docker run -d \
        --name bunkerweb-aio \
        --network bw-dns \
        -v bw-storage:/data \
        -e DNS_RESOLVERS="dnsmasq" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

=== "Docker"

    Agrega un servicio dnsmasq a tu archivo docker-compose y configura BunkerWeb para usarlo:

    ```yaml
    services:
      dnsmasq:
        image: dockurr/dnsmasq
        container_name: dnsmasq
        environment:
          # Usando los servidores DNS de Quad9 para mayor seguridad y privacidad
          # Primario: 9.9.9.9 (Quad9 con bloqueo de malware)
          # Secundario: 149.112.112.112 (Servidor de respaldo de Quad9)
          DNS1: "9.9.9.9"
          DNS2: "149.112.112.112"
        ports:
          - 53:53/udp
          - 53:53/tcp
        cap_add:
          - NET_ADMIN
        restart: always
        networks:
          - bw-dns

      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-dns

    networks:
      # ...redes existentes...
      bw-dns:
        name: bw-dns
    ```

## Configuraciones personalizadas {#custom-configurations}

Para personalizar y añadir configuraciones personalizadas a BunkerWeb, puedes aprovechar su base NGINX. Las configuraciones personalizadas de NGINX se pueden añadir en diferentes contextos de NGINX, incluidas las configuraciones para el Firewall de Aplicaciones Web (WAF) ModSecurity, que es un componente central de BunkerWeb. Se pueden encontrar más detalles sobre las configuraciones de ModSecurity [aquí](features.md#custom-configurations).

Estos son los tipos de configuraciones personalizadas disponibles:

- **http**: Configuraciones a nivel HTTP de NGINX.
- **server-http**: Configuraciones a nivel HTTP/Servidor de NGINX.
- **default-server-http**: Configuraciones a nivel de Servidor de NGINX, específicamente para el "servidor predeterminado" cuando el nombre del cliente proporcionado no coincide con ningún nombre de servidor en `SERVER_NAME`.
- **modsec-crs**: Configuraciones aplicadas antes de que se cargue el Core Rule Set de OWASP.
- **modsec**: Configuraciones aplicadas después de que se cargue el Core Rule Set de OWASP, o se utilizan cuando el Core Rule Set no está cargado.
- **crs-plugins-before**: Configuraciones para los plugins CRS, aplicadas antes de que se carguen los plugins CRS.
- **crs-plugins-after**: Configuraciones para los plugins CRS, aplicadas después de que se carguen los plugins CRS.
- **stream**: Configuraciones a nivel de Stream de NGINX.
- **server-stream**: Configuraciones a nivel de Stream/Servidor de NGINX.

Las configuraciones personalizadas se pueden aplicar globalmente o específicamente para un servidor en particular, dependiendo del contexto aplicable y de si el [modo multisitio](features.md#multisite-mode) está habilitado.

El método para aplicar configuraciones personalizadas depende de la integración que se esté utilizando. Sin embargo, el proceso subyacente implica añadir archivos con el sufijo `.conf` a carpetas específicas. Para aplicar una configuración personalizada para un servidor específico, el archivo debe colocarse en una subcarpeta con el nombre del servidor principal.

Algunas integraciones proporcionan formas más convenientes de aplicar configuraciones, como el uso de [Configs](https://docs.docker.com/engine/swarm/configs/) en Docker Swarm o [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/) en Kubernetes. Estas opciones ofrecen enfoques más sencillos para gestionar y aplicar configuraciones.

=== "Interfaz de usuario web"

    Navega a la página de **Configuraciones**, haz clic en **Crear nueva configuración personalizada**, luego puedes elegir si es global o específica para un servicio, el tipo de configuración y el nombre de la configuración:

    <figure markdown>![Configuraciones personalizadas usando la interfaz de usuario web](assets/img/advanced-config.png){ align=center }<figcaption>Configuraciones personalizadas usando la interfaz de usuario web</figcaption></figure>

    No olvides hacer clic en el botón `💾 Guardar`.

=== "Linux"

    Cuando se utiliza la [integración de Linux](integrations.md#linux), las configuraciones personalizadas deben escribirse en la carpeta `/etc/bunkerweb/configs`.

    Aquí hay un ejemplo para server-http/hello-world.conf:

    ```nginx
    location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }
    ```

    Debido a que BunkerWeb se ejecuta como un usuario sin privilegios (nginx:nginx), necesitarás editar los permisos:

    ```shell
    chown -R root:nginx /etc/bunkerweb/configs && \
    chmod -R 770 /etc/bunkerweb/configs
    ```

    Ahora verifiquemos el estado del Programador:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Si ya se está ejecutando, podemos recargarlo:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    De lo contrario, tendremos que iniciarlo:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Todo en uno"

    Cuando se utiliza la [imagen Todo en uno](integrations.md#all-in-one-aio-image), tienes dos opciones para añadir configuraciones personalizadas:

    - Usar configuraciones específicas `*_CUSTOM_CONF_*` como variables de entorno al ejecutar el contenedor (recomendado).
    - Escribir archivos `.conf` en el directorio `/data/configs/` dentro del volumen montado en `/data`.

    **Usando configuraciones (Variables de Entorno)**

    Las configuraciones a usar deben seguir el patrón `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>` : Nombre del servidor principal opcional si el modo multisitio está habilitado y la configuración debe aplicarse a un servicio específico.
    - `<TYPE>` : El tipo de configuración, los valores aceptados son `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` y `SERVER_STREAM`.
    - `<NAME>` : El nombre de la configuración sin el sufijo `.conf`.

    Aquí hay un ejemplo de prueba al ejecutar el contenedor Todo en uno:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e "CUSTOM_CONF_SERVER_HTTP_hello-world=location /hello { \
            default_type 'text/plain'; \
            content_by_lua_block { \
              ngx.say('world'); \
            } \
          }" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

    Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se apliquen las nuevas variables de entorno.

    **Usando archivos**

    Lo primero que hay que hacer es crear las carpetas:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Ahora puedes escribir tus configuraciones:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Debido a que el programador se ejecuta como un usuario sin privilegios con UID y GID 101, necesitarás editar los permisos:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Al iniciar el contenedor del programador, necesitarás montar la carpeta en /data:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v ./bw-data:/data \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

=== "Docker"

    Cuando se utiliza la [integración de Docker](integrations.md#docker), tienes dos opciones para añadir configuraciones personalizadas:

    - Usar configuraciones específicas `*_CUSTOM_CONF_*` como variables de entorno (recomendado)
    - Escribir archivos .conf en el volumen montado en /data del programador

    **Usando configuraciones**

    Las configuraciones a usar deben seguir el patrón `<SITE>_CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<SITE>`: nombre del servidor principal opcional si el modo multisitio está habilitado y la configuración debe aplicarse a un servicio específico
    - `<TYPE>`: el tipo de configuración, los valores aceptados son `HTTP`, `DEFAULT_SERVER_HTTP`, `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER`, `STREAM` y `SERVER_STREAM`
    - `<NAME>`: el nombre de la configuración sin el sufijo .conf

    Aquí hay un ejemplo de prueba usando un archivo docker-compose:

    ```yaml
    ...
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      environment:
        - |
          CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
              ngx.say('world')
            }
          }
      ...
    ```

    **Usando archivos**

    Lo primero que hay que hacer es crear las carpetas:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Ahora puedes escribir tus configuraciones:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Debido a que el programador se ejecuta como un usuario sin privilegios con UID y GID 101, necesitarás editar los permisos:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Al iniciar el contenedor del programador, necesitarás montar la carpeta en /data:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Docker autoconf"

    Cuando se utiliza la [integración de autoconfiguración de Docker](integrations.md#docker-autoconf), tienes dos opciones para añadir configuraciones personalizadas:

    - Usar configuraciones específicas `*_CUSTOM_CONF_*` como etiquetas (más fácil)
    - Escribir archivos .conf en el volumen montado en /data del programador

    **Usando etiquetas**

    !!! warning "Limitaciones al usar etiquetas"
        Cuando usas etiquetas con la integración de autoconfiguración de Docker, solo puedes aplicar configuraciones personalizadas para el servicio web correspondiente. No es posible aplicar configuraciones **http**, **default-server-http**, **stream** o cualquier ajuste global (como **server-http** o **server-stream** para todos los servicios): necesitarás montar archivos para ese propósito.

    Las etiquetas a usar deben seguir el patrón `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<TYPE>`: el tipo de configuración, los valores aceptados son `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` y `SERVER_STREAM`
    - `<NAME>`: el nombre de la configuración sin el sufijo .conf

    Aquí hay un ejemplo de prueba usando un archivo docker-compose:

    ```yaml
    myapp:
      image: bunkerity/bunkerweb-hello:v1.0
      labels:
        - |
          bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello-world=
          location /hello {
            default_type 'text/plain';
            content_by_lua_block {
                ngx.say('world')
            }
          }
      ...
    ```

    **Usando archivos**

    Lo primero que hay que hacer es crear las carpetas:

    ```shell
    mkdir -p ./bw-data/configs/server-http
    ```

    Ahora puedes escribir tus configuraciones:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" > ./bw-data/configs/server-http/hello-world.conf
    ```

    Debido a que el programador se ejecuta como un usuario sin privilegios con UID y GID 101, necesitarás editar los permisos:

    ```shell
    chown -R root:101 bw-data && \
    chmod -R 770 bw-data
    ```

    Al iniciar el contenedor del programador, necesitarás montar la carpeta en /data:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    Cuando se utiliza la [integración de Kubernetes](integrations.md#kubernetes),
    las configuraciones personalizadas se gestionan mediante [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    No es necesario montar la ConfigMap en un Pod (por ejemplo, como variable de entorno o volumen).
    El pod de autoconfiguración escucha los eventos de ConfigMap y aplica los cambios en cuanto se detectan.

    Anota cada ConfigMap que deba gestionar el controlador de Ingress:

    - `bunkerweb.io/CONFIG_TYPE`: obligatorio. Elige uno de los tipos compatibles (`http`, `server-http`, `default-server-http`, `modsec`,
      `modsec-crs`, `crs-plugins-before`, `crs-plugins-after`, `stream`, `server-stream` o `settings`).
    - `bunkerweb.io/CONFIG_SITE`: opcional. Establece el nombre del servidor principal (tal como se publica a través del `Ingress`)
      para limitar la configuración a ese servicio; déjalo vacío para aplicarla globalmente.

    Aquí está el ejemplo:

    ```yaml
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: cfg-bunkerweb-all-server-http
      annotations:
        bunkerweb.io/CONFIG_TYPE: "server-http"
    data:
      myconf: |
      location /hello {
        default_type 'text/plain';
        content_by_lua_block {
          ngx.say('world')
        }
      }
    ```

    !!! info "Cómo funciona la reconciliación"
        - El controlador de Ingress vigila continuamente las ConfigMap anotadas.
        - Si la variable de entorno `NAMESPACES` está definida, solo se tienen en cuenta las ConfigMap de esos espacios de nombres.
        - Crear o actualizar una ConfigMap gestionada provoca la recarga inmediata de la configuración.
        - Eliminar la ConfigMap, o quitar la anotación `bunkerweb.io/CONFIG_TYPE`, elimina la configuración personalizada asociada.
        - Si defines `bunkerweb.io/CONFIG_SITE`, el servicio referenciado debe existir previamente;
          de lo contrario, la ConfigMap se ignora hasta que aparezca el servicio.

    !!! tip "Configuración extra personalizada"
        Desde la versión `1.6.0`, puedes añadir o sobrescribir parámetros anotando una ConfigMap con `bunkerweb.io/CONFIG_TYPE=settings`.
        El controlador de Ingress de autoconf lee cada entrada de `data` y la aplica como si fuera una variable de entorno:

        - Sin `bunkerweb.io/CONFIG_SITE`, todas las claves se aplican globalmente.
        - Cuando `bunkerweb.io/CONFIG_SITE` está definido, el controlador añade automáticamente el prefijo `<nombre-del-servidor>_` (cada `/` se sustituye por `_`) a las claves que aún no están acotadas. Añade el prefijo manualmente si necesitas mezclar claves globales y específicas en la misma ConfigMap.
        - Los nombres o valores no válidos se omiten y el controlador autoconf registra una advertencia.

        Aquí hay un ejemplo:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # configuración multisitio que se aplicará a todos los servicios que no la sobrescriban
          USE_REDIS: "yes" # ajuste global que se aplicará globalmente
          ...
        ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

    Cuando se utiliza la [integración de Swarm](integrations.md#swarm), las configuraciones personalizadas se gestionan mediante [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    Para mantenerlo simple, ni siquiera necesitas adjuntar la Configuración a un servicio: el servicio de autoconfiguración está escuchando los eventos de Configuración y actualizará las configuraciones personalizadas cuando sea necesario.

    Al crear una Configuración, necesitarás añadir etiquetas especiales:

    *   **bunkerweb.CONFIG_TYPE**: debe establecerse a un tipo de configuración personalizada válido (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream, server-stream o settings)
    *   **bunkerweb.CONFIG_SITE**: establece un nombre de servidor para aplicar la configuración a ese servidor específico (opcional, se aplicará globalmente si no se establece)

    Aquí está el ejemplo:

    ```nginx
    echo "location /hello {
      default_type 'text/plain';
      content_by_lua_block {
        ngx.say('world')
      }
    }" | docker config create -l bunkerweb.CONFIG_TYPE=server-http my-config -
    ```

    No hay mecanismo de actualización: la alternativa es eliminar una configuración existente usando `docker config rm` y luego recrearla.

## Ejecutando muchos servicios en producción {#running-many-services-in-production}

### CRS Global

!!! warning "Plugins CRS"
    Cuando el CRS se carga globalmente, **los plugins CRS no son compatibles**. Si necesitas usarlos, tendrás que cargar el CRS por servicio.

Si usas BunkerWeb en producción con un gran número de servicios y habilitas la **característica de ModSecurity globalmente** con las reglas CRS, el tiempo requerido para cargar las configuraciones de BunkerWeb puede volverse demasiado largo, resultando potencialmente en un tiempo de espera agotado.

La solución es cargar las reglas CRS globalmente en lugar de por servicio. Este comportamiento no está habilitado por defecto por razones de compatibilidad con versiones anteriores y porque tiene un inconveniente: si habilitas la carga global de reglas CRS, **ya no será posible definir reglas modsec-crs** (ejecutadas antes de las reglas CRS) por servicio. Sin embargo, esta limitación puede ser superada escribiendo reglas de exclusión globales `modsec-crs` como esta:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Puedes habilitar la carga global de CRS estableciendo `USE_MODSECURITY_GLOBAL_CRS` en `yes`.

### Ajustar max_allowed_packet para MariaDB/MySQL

Parece que el valor predeterminado para el parámetro `max_allowed_packet` en los servidores de bases de datos MariaDB y MySQL no es suficiente cuando se utiliza BunkerWeb con un gran número de servicios.

Si encuentras errores como este, especialmente en el programador:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Necesitarás aumentar el `max_allowed_packet` en tu servidor de base de datos.

## Persistencia de bloqueos e informes {#persistence-of-bans-and-reports}

Por defecto, BunkerWeb almacena los bloqueos e informes en un almacén de datos Lua local. Aunque es simple y eficiente, esta configuración significa que los datos se pierden cuando se reinicia la instancia. Para asegurar que los bloqueos e informes persistan a través de los reinicios, puedes configurar BunkerWeb para que utilice un servidor remoto [Redis](https://redis.io/) o [Valkey](https://valkey.io/).

**¿Por qué usar Redis/Valkey?**

Redis y Valkey son potentes almacenes de datos en memoria comúnmente utilizados como bases de datos, cachés y agentes de mensajes. Son altamente escalables y soportan una variedad de estructuras de datos, incluyendo:

- **Strings**: Pares básicos de clave-valor.
- **Hashes**: Pares de campo-valor dentro de una sola clave.
- **Lists**: Colecciones ordenadas de cadenas.
- **Sets**: Colecciones no ordenadas de cadenas únicas.
- **Sorted Sets**: Colecciones ordenadas con puntuaciones.

Al aprovechar Redis o Valkey, BunkerWeb puede almacenar persistentemente bloqueos, informes y datos de caché, asegurando durabilidad y escalabilidad.

**Habilitando el soporte de Redis/Valkey**

Para habilitar el soporte de Redis o Valkey, configura los siguientes ajustes en tu archivo de configuración de BunkerWeb:

```conf
# Habilitar el soporte de Redis/Valkey
USE_REDIS=yes

# Nombre de host o dirección IP del servidor Redis/Valkey
REDIS_HOST=<hostname>

# Número de puerto del servidor Redis/Valkey (predeterminado: 6379)
REDIS_PORT=6379

# Número de base de datos de Redis/Valkey (predeterminado: 0)
REDIS_DATABASE=0
```

- **`USE_REDIS`**: Establécelo en `yes` para habilitar la integración con Redis/Valkey.
- **`REDIS_HOST`**: Especifica el nombre de host o la dirección IP del servidor Redis/Valkey.
- **`REDIS_PORT`**: Especifica el número de puerto para el servidor Redis/Valkey. El valor predeterminado es `6379`.
- **`REDIS_DATABASE`**: Especifica el número de la base de datos de Redis/Valkey a utilizar. El valor predeterminado es `0`.

Si necesitas configuraciones más avanzadas, como autenticación, soporte SSL/TLS o modo Sentinel, consulta la [documentación de configuración del plugin de Redis](features.md#redis) para obtener una guía detallada.

## Proteger aplicaciones UDP/TCP

!!! example "Característica experimental"

	  Esta característica no está lista para producción. Siéntete libre de probarla y reportarnos cualquier error usando los [issues](https://github.com/bunkerity/bunkerweb/issues) en el repositorio de GitHub.

BunkerWeb ofrece la capacidad de funcionar como un **proxy inverso genérico UDP/TCP**, permitiéndote proteger cualquier aplicación basada en red que opere al menos en la capa 4 del modelo OSI. En lugar de utilizar el módulo HTTP "clásico", BunkerWeb aprovecha el [módulo stream](https://nginx.org/en/docs/stream/ngx_stream_core_module.html) de NGINX.

Es importante tener en cuenta que **no todas las configuraciones y características de seguridad están disponibles cuando se utiliza el módulo stream**. Puedes encontrar información adicional sobre esto en las secciones de [características](features.md) de la documentación.

Configurar un proxy inverso básico es bastante similar a la configuración HTTP, ya que implica usar las mismas configuraciones: `USE_REVERSE_PROXY=yes` y `REVERSE_PROXY_HOST=myapp:9000`. Incluso cuando BunkerWeb está posicionado detrás de un Balanceador de Carga, las configuraciones siguen siendo las mismas (siendo el **protocolo PROXY** la opción soportada por razones evidentes).

Además de eso, se utilizan las siguientes configuraciones específicas:

- `SERVER_TYPE=stream`: activa el modo `stream` (UDP/TCP genérico) en lugar del `http` (que es el predeterminado)
- `LISTEN_STREAM_PORT=4242`: el puerto de escucha "plano" (sin SSL/TLS) en el que BunkerWeb escuchará
- `LISTEN_STREAM_PORT_SSL=4343`: el puerto de escucha "ssl/tls" en el que BunkerWeb escuchará
- `USE_UDP=no`: escucha y reenvía paquetes UDP en lugar de TCP

Para obtener una lista completa de las configuraciones relacionadas con el modo `stream`, consulta la sección de [características](features.md) de la documentación.

!!! tip "múltiples puertos de escucha"

    Desde la versión `1.6.0`, BunkerWeb soporta múltiples puertos de escucha para el modo `stream`. Puedes especificarlos usando las configuraciones `LISTEN_STREAM_PORT` y `LISTEN_STREAM_PORT_SSL`.

    Aquí hay un ejemplo:

    ```conf
    ...
    LISTEN_STREAM_PORT=4242
    LISTEN_STREAM_PORT_SSL=4343
    LISTEN_STREAM_PORT_1=4244
    LISTEN_STREAM_PORT_SSL_1=4344
    ...
    ```

=== "Todo en uno"

    Necesitarás agregar la configuración a las variables de entorno al ejecutar el contenedor Todo en uno. También necesitarás exponer los puertos de stream.

    Este ejemplo configura BunkerWeb para hacer proxy de dos aplicaciones basadas en stream, `app1.example.com` y `app2.example.com`.

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -e SERVICE_UI="no" \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e USE_REVERSE_PROXY="yes" \
        -e SERVER_TYPE="stream" \
        -e app1.example.com_REVERSE_PROXY_HOST="myapp1:9000" \
        -e app1.example.com_LISTEN_STREAM_PORT="10000" \
        -e app2.example.com_REVERSE_PROXY_HOST="myapp2:9000" \
        -e app2.example.com_LISTEN_STREAM_PORT="20000" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        -p 10000:10000/tcp \
        -p 20000:20000/tcp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

    Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se apliquen las nuevas variables de entorno.

    Tus aplicaciones (`myapp1`, `myapp2`) deberían estar ejecutándose en contenedores separados (o ser accesibles de otra manera) y sus nombres de host/IPs (p. ej., `myapp1`, `myapp2` usados en `_REVERSE_PROXY_HOST`) deben ser resolvibles y alcanzables desde el contenedor `bunkerweb-aio`. Esto típicamente implica conectarlos a una red Docker compartida.

    !!! note "Desactivar el servicio de la interfaz de usuario"
        Se recomienda desactivar el servicio de la interfaz de usuario (p. ej., estableciendo `SERVICE_UI=no` como una variable de entorno) ya que la interfaz de usuario web no es compatible con `SERVER_TYPE=stream`.

=== "Docker"

    Cuando se utiliza la integración con Docker, la forma más fácil de proteger las aplicaciones de red existentes es agregar los servicios a la red `bw-services`:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Usamos un ancla para evitar repetir la misma configuración para todos los servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
      # Token de API opcional para llamadas de API autenticadas
      API_TOKEN: ""

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - "80:8080" # Mantenlo si quieres usar la automatización de Let's Encrypt al usar el tipo de desafío http
          - "10000:10000" # app1
          - "20000:20000" # app2
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Esta configuración es obligatoria para especificar la instancia de BunkerWeb
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          USE_REVERSE_PROXY: "yes" # Se aplicará a todos los servicios
          SERVER_TYPE: "stream" # Se aplicará a todos los servicios
          app1.example.com_REVERSE_PROXY_HOST: "myapp1:9000"
          app1.example.com_LISTEN_STREAM_PORT: "10000"
          app2.example.com_REVERSE_PROXY_HOST: "myapp2:9000"
          app2.example.com_LISTEN_STREAM_PORT: "20000"
        volumes:
          - bw-storage:/data # Esto se usa para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services

    volumes:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
    ```

=== "Docker autoconf"

    Antes de ejecutar el stack de [integración Docker autoconf](integrations.md#docker-autoconf) en tu máquina, necesitarás editar los puertos:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - "80:8080" # Mantenlo si quieres usar la automatización de Let's Encrypt cuando usas el tipo de desafío http
          - "10000:10000" # app1
          - "20000:20000" # app2
    ...
    ```

    Una vez que el stack esté en ejecución, puedes conectar tus aplicaciones existentes a la red `bw-services` y configurar BunkerWeb con etiquetas:

    ```yaml
    services:
      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app1.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        labels:
          - "bunkerweb.SERVER_NAME=app2.example.com"
          - "bunkerweb.SERVER_TYPE=stream"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
          - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! example "Característica experimental"

        Por el momento, los [Ingresses](https://kubernetes.io/docs/concepts/services-networking/ingress/) no soportan el modo `stream`. **Lo que estamos haciendo aquí es una solución alternativa para que funcione.**

        Siéntete libre de probarlo y reportarnos cualquier error usando los [issues](https://github.com/bunkerity/bunkerweb/issues) en el repositorio de GitHub.

    Antes de ejecutar el stack de la [integración de Kubernetes](integrations.md#kubernetes) en tu máquina, necesitarás abrir los puertos en tu balanceador de carga:

    ```yaml
    apiVersion: v1
    kind: Service
    metadata:
      name: lb
    spec:
      type: LoadBalancer
      ports:
        - name: http # Mantenlo si quieres usar la automatización de Let's Encrypt cuando usas el tipo de desafío http
          port: 80
          targetPort: 8080
        - name: app1
          port: 10000
          targetPort: 10000
        - name: app2
          port: 20000
          targetPort: 20000
      selector:
        app: bunkerweb
    ```

    Una vez que el stack esté en ejecución, puedes crear tus recursos de ingress:

    ```yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: ingress
      namespace: services
      annotations:
        bunkerweb.io/SERVER_TYPE: "stream" # Se aplicará a todos los servicios
        bunkerweb.io/app1.example.com_LISTEN_STREAM_PORT: "10000"
        bunkerweb.io/app2.example.com_LISTEN_STREAM_PORT: "20000"
    spec:
      rules:
        - host: app1.example.com
          http:
            paths:
              - path: / # Esto no se usa en modo stream pero es obligatorio
                pathType: Prefix
                backend:
                  service:
                    name: svc-app1
                    port:
                      number: 9000
        - host: app2.example.com
          http:
            paths:
              - path: / # Esto no se usa en modo stream pero es obligatorio
                pathType: Prefix
                backend:
                  service:
                    name: svc-app2
                    port:
                      number: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app1
      namespace: services
      labels:
        app: app1
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app1
      template:
        metadata:
          labels:
            app: app1
        spec:
          containers:
            - name: app1
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app1"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app1
      namespace: services
    spec:
      selector:
        app: app1
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ---
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: app2
      namespace: services
      labels:
        app: app2
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: app2
      template:
        metadata:
          labels:
            app: app2
        spec:
          containers:
            - name: app2
              image: istio/tcp-echo-server:1.3
              args: ["9000", "app2"]
              ports:
                - containerPort: 9000
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: svc-app2
      namespace: services
    spec:
      selector:
        app: app2
      ports:
        - protocol: TCP
          port: 9000
          targetPort: 9000
    ```

=== "Linux"

    Necesitarás agregar la configuración al archivo `/etc/bunkerweb/variables.env`:

    ```conf
    ...
    SERVER_NAME=app1.example.com app2.example.com
    MULTISITE=yes
    USE_REVERSE_PROXY=yes
    SERVER_TYPE=stream
    app1.example.com_REVERSE_PROXY_HOST=myapp1.domain.or.ip:9000
    app1.example.com_LISTEN_STREAM_PORT=10000
    app2.example.com_REVERSE_PROXY_HOST=myapp2.domain.or.ip:9000
    app2.example.com_LISTEN_STREAM_PORT=20000
    ...
    ```

    Ahora verifiquemos el estado del Programador:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Si ya se está ejecutando, podemos recargarlo:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    De lo contrario, tendremos que iniciarlo:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

    Antes de ejecutar el stack de [integración de Swarm](integrations.md#swarm) en tu máquina, necesitarás editar los puertos:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ports:
          # Mantenlo si quieres usar la automatización de Let's Encrypt cuando usas el tipo de desafío http
          - published: 80
            target: 8080
            mode: host
            protocol: tcp
          # app1
          - published: 10000
            target: 10000
            mode: host
            protocol: tcp
          # app2
          - published: 20000
            target: 20000
            mode: host
            protocol: tcp
    ...
    ```

    Una vez que el stack esté en ejecución, puedes conectar tus aplicaciones existentes a la red `bw-services` y configurar BunkerWeb con etiquetas:

    ```yaml
    services:

      myapp1:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app1" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp1:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=10000"

      myapp2:
        image: istio/tcp-echo-server:1.3
        command: [ "9000", "app2" ]
        networks:
          - bw-services
        deploy:
          placement:
            constraints:
              - "node.role==worker"
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.SERVER_TYPE=stream"
            - "bunkerweb.USE_REVERSE_PROXY=yes"
            - "bunkerweb.REVERSE_PROXY_HOST=myapp2:9000"
            - "bunkerweb.LISTEN_STREAM_PORT=20000"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## PHP

!!! example "Característica experimental"
	  Por el momento, el soporte de PHP con BunkerWeb todavía está en beta y te recomendamos que utilices una arquitectura de proxy inverso si puedes. Por cierto, PHP no es compatible en absoluto con algunas integraciones como Kubernetes.

BunkerWeb soporta PHP usando instancias externas o remotas de [PHP-FPM](https://www.php.net/manual/en/install.fpm.php). Asumiremos que ya estás familiarizado con la gestión de este tipo de servicios.

Se pueden usar las siguientes configuraciones:

- `REMOTE_PHP`: Nombre de host de la instancia remota de PHP-FPM.
- `REMOTE_PHP_PATH`: Carpeta raíz que contiene los archivos en la instancia remota de PHP-FPM.
- `REMOTE_PHP_PORT`: Puerto de la instancia remota de PHP-FPM (*el predeterminado es 9000*).
- `LOCAL_PHP`: Ruta al archivo de socket local de la instancia de PHP-FPM.
- `LOCAL_PHP_PATH`: Carpeta raíz que contiene los archivos en la instancia local de PHP-FPM.

=== "Todo en uno"

    Cuando se utiliza la [imagen Todo en uno](integrations.md#all-in-one-aio-image), para soportar aplicaciones PHP, necesitarás:

    - Montar tus archivos PHP en la carpeta `/var/www/html` de BunkerWeb.
    - Configurar un contenedor PHP-FPM para tu aplicación y montar la carpeta que contiene los archivos PHP.
    - Usar las configuraciones específicas `REMOTE_PHP` y `REMOTE_PHP_PATH` como variables de entorno al ejecutar BunkerWeb.

    Si habilitas el [modo multisitio](features.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse usando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    └── app2.example.com
        └── index.php

    2 directorios, 2 archivos
    ```

    Asumiremos que tus aplicaciones PHP están ubicadas en una carpeta llamada `www`. Ten en cuenta que necesitarás corregir los permisos para que BunkerWeb (UID/GID 101) pueda al menos leer archivos y listar carpetas, y que PHP-FPM (UID/GID 33 si usas la imagen `php:fpm`) sea el propietario de los archivos y carpetas:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Ahora puedes ejecutar BunkerWeb, configurarlo para tu aplicación PHP y también ejecutar las aplicaciones PHP. Necesitarás crear una red Docker personalizada para permitir que BunkerWeb se comunique con tus contenedores PHP-FPM.

    ```bash
    # Crear una red personalizada
    docker network create php-network

    # Ejecutar contenedores PHP-FPM
    docker run -d --name myapp1-php --network php-network -v ./www/app1.example.com:/app php:fpm
    docker run -d --name myapp2-php --network php-network -v ./www/app2.example.com:/app php:fpm

    # Ejecutar BunkerWeb Todo en uno
    docker run -d \
        --name bunkerweb-aio \
        --network php-network \
        -v ./www:/var/www/html \
        -v bw-storage:/data \
        -e SERVER_NAME="app1.example.com app2.example.com" \
        -e MULTISITE="yes" \
        -e REMOTE_PHP_PATH="/app" \
        -e app1.example.com_REMOTE_PHP="myapp1-php" \
        -e app2.example.com_REMOTE_PHP="myapp2-php" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

    Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se apliquen las nuevas variables de entorno.

=== "Docker"

    Cuando se utiliza la [integración de Docker](integrations.md#docker), para admitir aplicaciones PHP, necesitarás:

    - Montar tus archivos PHP en la carpeta `/var/www/html` de BunkerWeb
    - Configurar un contenedor PHP-FPM para tu aplicación y montar la carpeta que contiene los archivos PHP
    - Usar las configuraciones específicas `REMOTE_PHP` y `REMOTE_PHP_PATH` como variables de entorno al iniciar BunkerWeb

    Si habilitas el [modo multisitio](features.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse utilizando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directorios, 3 archivos
    ```

    Asumiremos que tus aplicaciones PHP están ubicadas en una carpeta llamada `www`. Ten en cuenta que necesitarás arreglar los permisos para que BunkerWeb (UID/GID 101) pueda al menos leer archivos y listar carpetas y PHP-FPM (UID/GID 33 si usas la imagen `php:fpm`) sea el propietario de los archivos y carpetas:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Ahora puedes ejecutar BunkerWeb, configurarlo para tu aplicación PHP y también ejecutar las aplicaciones PHP:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Usamos un ancla para evitar repetir la misma configuración para todos los servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # QUIC
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Esta configuración es obligatoria para especificar la instancia de BunkerWeb
          SERVER_NAME: "app1.example.com app2.example.com"
          MULTISITE: "yes"
          REMOTE_PHP_PATH: "/app" # Se aplicará a todos los servicios gracias a la configuración MULTISITE
          app1.example.com_REMOTE_PHP: "myapp1"
          app2.example.com_REMOTE_PHP: "myapp2"
          app3.example.com_REMOTE_PHP: "myapp3"
        volumes:
          - bw-storage:/data # Esto se usa para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe

      myapp1:
        image: php:fpm
        volumes:
          - ./www/app1.example.com:/app
        networks:
          - bw-services

      myapp2:
        image: php:fpm
        volumes:
          - ./www/app2.example.com:/app
        networks:
          - bw-services

      myapp3:
        image: php:fpm
        volumes:
          - ./www/app3.example.com:/app
        networks:
          - bw-services

    volumes:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
    ```

=== "Docker autoconf"

    !!! info "Modo multisitio habilitado"
        La integración de [Docker autoconf](integrations.md#docker-autoconf) implica el uso del modo multisitio: proteger una aplicación PHP es lo mismo que proteger varias.

    Cuando se utiliza la [integración de Docker autoconf](integrations.md#docker-autoconf), para admitir aplicaciones PHP, necesitarás:

    - Montar tus archivos PHP en la carpeta `/var/www/html` de BunkerWeb
    - Configurar contenedores PHP-FPM para tus aplicaciones y montar la carpeta que contiene las aplicaciones PHP
    - Usar las configuraciones específicas `REMOTE_PHP` y `REMOTE_PHP_PATH` como etiquetas para tu contenedor PHP-FPM

    Dado que la autoconfiguración de Docker implica el uso del [modo multisitio](features.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe tener el nombre del primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directorios, 3 archivos
    ```

    Una vez creadas las carpetas, copia tus archivos y corrige los permisos para que BunkerWeb (UID/GID 101) pueda al menos leer archivos y listar carpetas, y PHP-FPM (UID/GID 33 si usas la imagen `php:fpm`) sea el propietario de los archivos y carpetas:

    ```shell
    chown -R 33:101 ./www && \
    find ./www -type f -exec chmod 0640 {} \; && \
    find ./www -type d -exec chmod 0750 {} \;
    ```

    Cuando inicies el stack de autoconfiguración de BunkerWeb, monta la carpeta `www` en `/var/www/html` para el contenedor del **Scheduler**:

    ```yaml
    x-bw-api-env: &bw-api-env
      # Usamos un ancla para evitar repetir la misma configuración para todos los servicios
      AUTOCONF_MODE: "yes"
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        labels:
          - "bunkerweb.INSTANCE=yes"
        environment:
          <<: *bw-api-env
        volumes:
          - ./www:/var/www/html
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-api-env
          BUNKERWEB_INSTANCES: "" # No necesitamos especificar la instancia de BunkerWeb aquí, ya que son detectadas automáticamente por el servicio de autoconfiguración
          SERVER_NAME: "" # El nombre del servidor se llenará con las etiquetas de los servicios
          MULTISITE: "yes" # Configuración obligatoria para la autoconfiguración
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.8
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          AUTOCONF_MODE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
          DOCKER_HOST: "tcp://bw-docker:2375" # El socket de Docker
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        networks:
          - bw-docker

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-storage:

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
    ```

    Ahora puedes crear tus contenedores PHP-FPM, montar las subcarpetas correctas y usar etiquetas para configurar BunkerWeb:

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          labels:
            - "bunkerweb.SERVER_NAME=app1.example.com"
            - "bunkerweb.REMOTE_PHP=myapp1"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          labels:
            - "bunkerweb.SERVER_NAME=app2.example.com"
            - "bunkerweb.REMOTE_PHP=myapp2"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          labels:
            - "bunkerweb.SERVER_NAME=app3.example.com"
            - "bunkerweb.REMOTE_PHP=myapp3"
            - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

=== "Kubernetes"

    !!! warning "PHP no es compatible con Kubernetes"
        La integración de Kubernetes permite la configuración a través de [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) y el controlador de BunkerWeb solo admite aplicaciones HTTP por el momento.

=== "Linux"

    Asumiremos que ya tienes el stack de [integración de Linux](integrations.md#linux) funcionando en tu máquina.

    Por defecto, BunkerWeb buscará archivos web dentro de la carpeta `/var/www/html`. Puedes usarla para almacenar tus aplicaciones PHP. Ten en cuenta que necesitarás configurar tu servicio PHP-FPM para obtener o establecer el usuario/grupo de los procesos en ejecución y el archivo de socket UNIX utilizado para comunicarse con BunkerWeb.

    En primer lugar, deberás asegurarte de que tu instancia de PHP-FPM pueda acceder a los archivos dentro de la carpeta `/var/www/html` y también de que BunkerWeb pueda acceder al archivo de socket UNIX para comunicarse con PHP-FPM. Recomendamos establecer un usuario diferente como `www-data` para el servicio PHP-FPM y dar al grupo nginx acceso al archivo de socket UNIX. Aquí está la configuración correspondiente de PHP-FPM:

    ```ini
    ...
    [www]
    user = www-data
    group = www-data
    listen = /run/php/php-fpm.sock
    listen.owner = www-data
    listen.group = nginx
    listen.mode = 0660
    ...
    ```

    No olvides reiniciar tu servicio PHP-FPM:

    ```shell
    systemctl restart php-fpm
    ```

    Si habilitas el [modo multisitio](features.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse utilizando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

    ```
    /var/www/html
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directorios, 3 archivos
    ```

    Ten en cuenta que necesitarás arreglar los permisos para que BunkerWeb (grupo `nginx`) pueda al menos leer archivos y listar carpetas, y PHP-FPM (usuario `www-data`, pero podría ser diferente dependiendo de tu sistema) sea el propietario de los archivos y carpetas:

    ```shell
    chown -R www-data:nginx /var/www/html && \
    find /var/www/html -type f -exec chmod 0640 {} \; && \
    find /var/www/html -type d -exec chmod 0750 {} \;
    ```

    Ahora puedes editar el archivo `/etc/bunkerweb/variable.env`:

    ```conf
    HTTP_PORT=80
    HTTPS_PORT=443
    DNS_RESOLVERS=9.9.9.9 8.8.8.8 8.8.4.4
    API_LISTEN_IP=127.0.0.1
    MULTISITE=yes
    SERVER_NAME=app1.example.com app2.example.com app3.example.com
    app1.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app1.example.com_LOCAL_PHP_PATH=/var/www/html/app1.example.com
    app2.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app2.example.com_LOCAL_PHP_PATH=/var/www/html/app2.example.com
    app3.example.com_LOCAL_PHP=/run/php/php-fpm.sock
    app3.example.com_LOCAL_PHP_PATH=/var/www/html/app3.example.com
    ```

    Ahora verifiquemos el estado del Programador:

    ```shell
    systemctl status bunkerweb-scheduler
    ```

    Si ya se están ejecutando, podemos recargarlo:

    ```shell
    systemctl reload bunkerweb-scheduler
    ```

    De lo contrario, tendremos que iniciarlo:

    ```shell
    systemctl start bunkerweb-scheduler
    ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Se puede encontrar más información en la [documentación de integración de Swarm](integrations.md#swarm).**

    !!! info "Modo multisitio habilitado"
        La integración [Swarm](integrations.md#docker-autoconf) implica el uso del modo multisitio: proteger una aplicación PHP es lo mismo que proteger varias.

    !!! info "Volumen compartido"
        Usar PHP con la integración de Docker Swarm necesita un volumen compartido entre todas las instancias de BunkerWeb y PHP-FPM, lo cual no se cubre en esta documentación.

    Cuando se usa la integración [Swarm](integrations.md#swarm), para admitir aplicaciones PHP, necesitarás:

    - Montar tus archivos PHP en la carpeta `/var/www/html` de BunkerWeb
    - Configurar contenedores PHP-FPM para tus aplicaciones y montar la carpeta que contiene las aplicaciones PHP
    - Usar las configuraciones específicas `REMOTE_PHP` y `REMOTE_PHP_PATH` como etiquetas para tu contenedor PHP-FPM

    Dado que la integración de Swarm implica el uso del [modo multisitio](features.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe tener el nombre del primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

    ```
    www
    ├── app1.example.com
    │   └── index.php
    ├── app2.example.com
    │   └── index.php
    └── app3.example.com
        └── index.php

    3 directorios, 3 archivos
    ```

    Como ejemplo, consideraremos que tienes una carpeta compartida montada en tus nodos de trabajo en el punto final `/shared`.

    Una vez creadas las carpetas, copia tus archivos y corrige los permisos para que BunkerWeb (UID/GID 101) pueda al menos leer archivos y listar carpetas, y PHP-FPM (UID/GID 33 si usas la imagen `php:fpm`) sea el propietario de los archivos y carpetas:

    ```shell
    chown -R 33:101 /shared/www && \
    find /shared/www -type f -exec chmod 0640 {} \; && \
    find /shared/www -type d -exec chmod 0750 {} \;
    ```

    Cuando inicies el stack de BunkerWeb, monta la carpeta `/shared/www` en `/var/www/html` para el contenedor del **Scheduler**:

    ```yaml
    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.8
        volumes:
          - /shared/www:/var/www/html
    ...
    ```

    Ahora puedes crear tus servicios PHP-FPM, montar las subcarpetas correctas y usar etiquetas para configurar BunkerWeb:

    ```yaml
    services:
      myapp1:
          image: php:fpm
          volumes:
            - ./www/app1.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp1
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app1.example.com"
              - "bunkerweb.REMOTE_PHP=myapp1"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp2:
          image: php:fpm
          volumes:
            - ./www/app2.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp2
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app2.example.com"
              - "bunkerweb.REMOTE_PHP=myapp2"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

      myapp3:
          image: php:fpm
          volumes:
            - ./www/app3.example.com:/app
          networks:
            bw-services:
                aliases:
                  - myapp3
          deploy:
            placement:
              constraints:
                - "node.role==worker"
            labels:
              - "bunkerweb.SERVER_NAME=app3.example.com"
              - "bunkerweb.REMOTE_PHP=myapp3"
              - "bunkerweb.REMOTE_PHP_PATH=/app"

    networks:
      bw-services:
        external: true
        name: bw-services
    ```

## IPv6

!!! example "Característica experimental"

    Esta característica no está lista para producción. Siéntete libre de probarla y reportarnos cualquier error usando los [issues](https://github.com/bunkerity/bunkerweb/issues) en el repositorio de GitHub.

Por defecto, BunkerWeb solo escuchará en direcciones IPv4 y no usará IPv6 para las comunicaciones de red. Si quieres habilitar el soporte de IPv6, necesitas establecer `USE_IPV6=yes`. Ten en cuenta que la configuración de IPv6 de tu red y entorno está fuera del alcance de esta documentación.

=== "Docker / Autoconf / Swarm"

    En primer lugar, necesitarás configurar tu demonio de Docker para habilitar el soporte de IPv6 para los contenedores y usar ip6tables si es necesario. Aquí hay una configuración de ejemplo para tu archivo `/etc/docker/daemon.json`:

    ```json
    {
      "experimental": true,
      "ipv6": true,
      "ip6tables": true,
      "fixed-cidr-v6": "fd00:dead:beef::/48"
    }
    ```

    Ahora puedes reiniciar el servicio de Docker para aplicar los cambios:

    ```shell
    systemctl restart docker
    ```

    Una vez que Docker esté configurado para soportar IPv6, puedes agregar la configuración `USE_IPV6` y configurar la red `bw-services` para IPv6:

    ```yaml
    services:
      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          USE_IPv6: "yes"

    ...

    networks:
      bw-services:
        name: bw-services
        enable_ipv6: true
        ipam:
          config:
            - subnet: fd00:13:37::/48
              gateway: fd00:13:37::1

    ...
    ```

=== "Linux"

    Necesitarás agregar la configuración al archivo `/etc/bunkerweb/variables.env`:

    ```conf
    ...
    USE_IPV6=yes
    ...
    ```

    Verifiquemos el estado de BunkerWeb:

    ```shell
    systemctl status bunkerweb
    ```

    Si ya se está ejecutando, podemos reiniciarlo:

    ```shell
    systemctl restart bunkerweb
    ```

    De lo contrario, tendremos que iniciarlo:

    ```shell
    systemctl start bunkerweb
    ```

## Opciones de configuración de registros

BunkerWeb ofrece una configuración de registros flexible que permite enviar registros a múltiples destinos (por ejemplo, archivos, stdout/stderr o syslog) simultáneamente. Esto es especialmente útil para integrarse con recopiladores externos de registros mientras se mantienen registros locales para la interfaz web.

Hay dos categorías principales de registros para configurar:

1. **Registros de servicio**: Logs generados por los componentes de BunkerWeb (Scheduler, UI, Autoconf, etc.). Se controlan por servicio mediante `LOG_TYPES` (y opcionalmente `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`).
2. **Registros de acceso y error**: Registros HTTP de acceso y errores generados por NGINX. Solo el servicio `bunkerweb` usa estos (`ACCESS_LOG` / `ERROR_LOG` / `LOG_LEVEL`).

### Registros de servicio

Los registros de servicio se controlan con la configuración `LOG_TYPES`, que puede aceptar múltiples valores separados por espacios (por ejemplo, `LOG_TYPES="stderr syslog"`).

| Valor    | Descripción                                                                                                  |
| :------- | :----------------------------------------------------------------------------------------------------------- |
| `file`   | Escribe los registros en un archivo. Requerido para el visor de registros de la interfaz UI.                 |
| `stderr` | Escribe los registros en la salida de error estándar. Estándar en entornos con contenedores (`docker logs`). |
| `syslog` | Envía los registros a un servidor syslog. Requiere definir `LOG_SYSLOG_ADDRESS`.                             |

Al usar `syslog`, también debes configurar:

- `LOG_SYSLOG_ADDRESS`: La dirección del servidor syslog (por ejemplo, `udp://bw-syslog:514` o `/dev/log`).
- `LOG_SYSLOG_TAG`: Una etiqueta única para el servicio (por ejemplo, `bw-scheduler`) para distinguir sus entradas.
- `LOG_FILE_PATH`: Ruta para la salida de archivo cuando `LOG_TYPES` incluye `file` (por ejemplo, `/var/log/bunkerweb/scheduler.log`).

### Registros de acceso y error

Estos son registros estándar de NGINX, configurados únicamente mediante el **servicio `bunkerweb`**. Soportan múltiples destinos añadiendo sufijos numerados a la configuración (por ejemplo, `ACCESS_LOG`, `ACCESS_LOG_1` junto con `LOG_FORMAT`, `LOG_FORMAT_1`, o `ERROR_LOG`, `ERROR_LOG_1` con sus respectivos `LOG_LEVEL`, `LOG_LEVEL_1`).

- `ACCESS_LOG`: Destino para los registros de acceso (por defecto: `/var/log/bunkerweb/access.log`). Acepta ruta de archivo, `syslog:server=host[:port][,param=value]`, buffer compartido `memory:name:size`, o `off` para desactivar. Consulta la [documentación de NGINX sobre access_log](https://nginx.org/en/docs/http/ngx_http_log_module.html#access_log) para más detalles.
- `ERROR_LOG`: Destino para los registros de error (por defecto: `/var/log/bunkerweb/error.log`). Acepta ruta de archivo, `stderr`, `syslog:server=host[:port][,param=value]`, o buffer compartido `memory:size`. Consulta la [documentación de NGINX sobre error_log](https://nginx.org/en/docs/ngx_core_module.html#error_log) para más detalles.
- `LOG_LEVEL`: Nivel de verbosidad de los registros de error (por defecto: `notice`).

Estas configuraciones aceptan valores estándar de NGINX, incluyendo rutas de archivo, `stderr`, `syslog:server=...` (ver [documentación de syslog en NGINX](https://nginx.org/en/docs/syslog.html)), o buffers en memoria compartida. Soportan múltiples destinos mediante sufijos numerados (consulta la [convención de múltiples ajustes](features.md#multiple-settings)). Los demás servicios (Scheduler, UI, Autoconf, etc.) dependen únicamente de `LOG_TYPES`/`LOG_FILE_PATH`/`LOG_SYSLOG_*`.

**Ejemplo con múltiples registros de acceso/errores (solo bunkerweb, sufijos numerados):**

```conf
ACCESS_LOG=/var/log/bunkerweb/access.log
ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_FORMAT=$host $remote_addr - $request_id $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"
LOG_FORMAT_1=$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
ERROR_LOG=/var/log/bunkerweb/error.log
ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
LOG_LEVEL=notice
LOG_LEVEL_1=error
```

### Valores por defecto e integración — Ejemplos

=== "Linux"

    **Comportamiento predeterminado**: `LOG_TYPES="file"`. Los registros se escriben en `/var/log/bunkerweb/*.log`.

    **Ejemplo**: Mantener archivos locales (para la interfaz web) y también enviar una copia al syslog del sistema.

    ```conf
      # Registros de servicio (establecidos en /etc/bunkerweb/variables.env o en archivos env específicos del servicio)
      LOG_TYPES="file syslog"
      LOG_SYSLOG_ADDRESS=/dev/log
      SCHEDULER_LOG_FILE_PATH=/var/log/bunkerweb/scheduler.log
      UI_LOG_FILE_PATH=/var/log/bunkerweb/ui.log
      # ...
      # LOG_SYSLOG_TAG se asigna automáticamente por servicio (anular por servicio si es necesario)

      # Registros de NGINX (solo servicio bunkerweb; establecer en /etc/bunkerweb/variables.env)
      ACCESS_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb_access
      ERROR_LOG_1=syslog:server=unix:/dev/log,tag=bunkerweb
    ```

=== "Docker / Autoconf"

    **Comportamiento predeterminado**: `LOG_TYPES="stderr"`. Los registros son visibles mediante `docker logs`.

    **Ejemplo (adaptado de la guía de inicio rápido)**: Mantener `docker logs` (stderr) Y enviar también a un contenedor syslog central (necesario para la interfaz web y CrowdSec).

    ```yaml
    x-bw-env:
      &bw-env # Usamos un ancla para evitar repetir la misma configuración para ambos servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Asegúrate de establecer el rango de IP correcto para que el Scheduler pueda enviar la configuración a la instancia
      # Opcional: establece un token de API y refléjalo en ambos contenedores
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerda establecer una contraseña más segura para la base de datos
      # Registros de servicio
      LOG_TYPES: "stderr syslog"
      LOG_SYSLOG_ADDRESS: "udp://bw-syslog:514"
      # LOG_SYSLOG_TAG se asigna automáticamente por servicio (anular por servicio si es necesario)
      # Registros NGINX: enviar a Syslog (solo bunkerweb)
      ACCESS_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb_access"
      ERROR_LOG_1: "syslog:server=bw-syslog:514,tag=bunkerweb"

    services:
      bunkerweb:
        # Este es el nombre que se usará para identificar la instancia en el Scheduler
        image: bunkerity/bunkerweb:1.6.8
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para soporte QUIC / HTTP3
        environment:
          <<: *bw-env # Usamos el ancla para evitar repetir la misma configuración para todos los servicios
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrate de establecer el nombre correcto de la instancia
          SERVER_NAME: ""
          MULTISITE: "yes"
          UI_HOST: "http://bw-ui:7000" # Cambia si es necesario
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
        volumes:
          - bw-storage:/data # Esto se usa para persistir la caché y otros datos como las copias de seguridad
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-ui:
        image: bunkerity/bunkerweb-ui:1.6.8
        environment:
          <<: *bw-env
        volumes:
          - bw-logs:/var/log/bunkerweb # Esto se usa para leer los registros syslog desde la interfaz web
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Establecemos el tamaño máximo de paquete permitido para evitar problemas con consultas grandes
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Recuerda establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Servicio Redis para la persistencia de reportes/bloqueos/estadísticas
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

      bw-syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE # Enlazar a puertos bajos
          - NET_BROADCAST # Enviar broadcasts
          - NET_RAW # Usar sockets raw
          - DAC_READ_SEARCH # Leer archivos saltando permisos
          - DAC_OVERRIDE # Anular permisos de archivos
          - CHOWN # Cambiar propiedad de archivos
          - SYSLOG # Escribir en logs del sistema
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen usado para almacenar los registros
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Este es el archivo de configuración de syslog-ng
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:
      bw-logs:

    networks:
      bw-universe:
        name: bw-universe
      ipam:
        driver: default
        config:
          - subnet: 10.20.30.0/24 # Asegúrate de establecer el rango de IP correcto para que el Scheduler pueda enviar la configuración a la instancia
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

### Configuración de syslog-ng

Aquí tienes un ejemplo de un archivo `syslog-ng.conf` que puedes usar para reenviar los registros a un archivo:

```conf
@version: 4.10

# Configuración de la fuente para recibir registros enviados por los servicios de BunkerWeb (ACCESS_LOG / ERROR_LOG y LOG_TYPES=syslog)
source s_net {
  udp(
    ip("0.0.0.0")
  );
};

# Plantilla para formatear los mensajes de registro
template t_imp {
  template("$MSG\n");
  template_escape(no);
};

# Configuración de destino para escribir registros en archivos con nombre dinámico
destination d_dyna_file {
  file(
    "/var/log/bunkerweb/${PROGRAM}.log"
    template(t_imp)
    owner("101")
    group("101")
    dir_owner("root")
    dir_group("101")
    perm(0440)
    dir_perm(0770)
    create_dirs(yes)
    logrotate(
      enable(yes),
      size(100MB),
      rotations(7)
    )
  );
};

# Ruta de registro para dirigir los registros a archivos con nombre dinámico
log {
  source(s_net);
  destination(d_dyna_file);
};
```

## Buenas prácticas de registro de Docker

Cuando se utiliza Docker, es importante gestionar los registros de los contenedores para evitar que consuman un espacio excesivo en el disco. Por defecto, Docker utiliza el controlador de registro `json-file`, lo que puede dar lugar a archivos de registro muy grandes si no se configura.

Para evitar esto, puede configurar la rotación de registros. Esto se puede hacer para servicios específicos en su archivo `docker-compose.yml`, o globalmente para el demonio de Docker.

**Configuración por servicio**

Puede configurar el controlador de registro para sus servicios en su archivo `docker-compose.yml` para rotar automáticamente los registros. Aquí hay un ejemplo que mantiene hasta 10 archivos de registro de 20 MB cada uno:

```yaml
services:
  bunkerweb:
    image: bunkerity/bunkerweb:1.6.8
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "10"
    ...
```

Esta configuración asegura que los registros se roten, evitando que llenen su disco. Puede aplicar esto a cualquier servicio en su configuración de Docker Compose.

**Ajustes globales (daemon.json)**

Si desea aplicar esta configuración de registro a todos los contenedores en el host por defecto, puede configurar el demonio de Docker editando (o creando) el archivo `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "10"
  }
}
```

Después de modificar `daemon.json`, debe reiniciar el demonio de Docker para que los cambios surtan efecto:

```shell
sudo systemctl restart docker
```

Estos ajustes globales serán heredados por todos los contenedores. Sin embargo, cualquier configuración de registro definida por servicio en un archivo `docker-compose.yml` anulará los ajustes globales en `daemon.json`.

## Ajuste de seguridad {#security-tuning}

BunkerWeb ofrece muchas características de seguridad que puedes configurar con [características](features.md). Aunque los valores predeterminados de las configuraciones aseguran una "seguridad por defecto" mínima, te recomendamos encarecidamente que los ajustes. Al hacerlo, podrás asegurar el nivel de seguridad de tu elección y también gestionar los falsos positivos.

!!! tip "Otras características"
    Esta sección solo se enfoca en el ajuste de seguridad, consulta la sección de [características](features.md) de la documentación para otras configuraciones.

<figure markdown>
  ![Descripción general](assets/img/core-order.svg){ align=center }
  <figcaption>Descripción general y orden de los plugins de seguridad principales</figcaption>
</figure>

## Integración con la Consola de CrowdSec

Si aún no estás familiarizado con la integración de la Consola de CrowdSec, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) aprovecha la inteligencia de la comunidad para combatir las amenazas cibernéticas. Piénsalo como el "Waze de la ciberseguridad"—cuando un servidor es atacado, otros sistemas en todo el mundo son alertados y protegidos de los mismos atacantes. Puedes aprender más sobre ello [aquí](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

**¡Felicidades, tu instancia de BunkerWeb ahora está inscrita en tu Consola de CrowdSec!**

Consejo profesional: Al ver tus alertas, haz clic en la opción "columnas" y marca la casilla "contexto" para acceder a los datos específicos de BunkerWeb.

<figure markdown>
  ![Descripción general](assets/img/crowdity4.png){ align=center }
  <figcaption>Datos de BunkerWeb mostrados en la columna de contexto</figcaption>
</figure>

## Proxy directo para tráfico saliente {#forward-proxy-outgoing-traffic}

Si tu entorno requiere que el tráfico HTTP(S) saliente pase por un proxy directo (por ejemplo un proxy corporativo o Squid), puedes usar las variables de entorno estándar del proxy. No hay una configuración específica de BunkerWeb para esto.

**NGINX no utiliza estas variables para el tráfico upstream**, por lo que la configuración del proxy directo solo afecta a los componentes que inician solicitudes salientes. En la práctica, configúralas en el **Scheduler**, porque gestiona tareas periódicas como las renovaciones de certificados de Let's Encrypt, llamadas a API externas y webhooks.

Las variables habituales son:

- `HTTP_PROXY` / `HTTPS_PROXY`: URL del proxy, opcionalmente con credenciales.
- `NO_PROXY`: lista separada por comas de hosts, dominios o CIDR que deben excluir el proxy (ajusta según la integración: nombres de servicios en Docker/Swarm, dominios del clúster en Kubernetes, o solo localhost en Linux).
- `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`: opcional, necesario si el proxy usa una CA personalizada. Monta el bundle de CA en el contenedor y apunta las variables a él para que las solicitudes de Python validen TLS (ajusta la ruta a tu imagen base).

!!! warning "NO_PROXY es obligatorio para el tráfico interno"
    Si omites rangos internos o nombres de servicios, el tráfico interno puede ir al proxy y fallar. Ajusta la lista a tu integración (por ejemplo nombres de servicios Docker, dominios del clúster de Kubernetes o solo localhost en Linux).

=== "Linux"

    Añade las variables a `/etc/bunkerweb/variables.env`. Este archivo se carga para ambos servicios, pero solo el Scheduler las utilizará:

    ```conf
    HTTP_PROXY=http://proxy.example.local:3128
    HTTPS_PROXY=http://proxy.example.local:3128
    NO_PROXY=localhost,127.0.0.1
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    ```

    Reinicia los servicios para recargar el entorno:

    ```shell
    sudo systemctl restart bunkerweb && \
    sudo systemctl restart bunkerweb-scheduler
    ```

=== "All-in-one"

    Proporciona las variables al crear el contenedor (y monta el bundle de CA si es necesario). La imagen All-in-one incluye el Scheduler, así que esto cubre las tareas salientes:

    ```bash
    docker run -d \
        --name bunkerweb-aio \
        -v bw-storage:/data \
        -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
        -e HTTP_PROXY="http://proxy.example.local:3128" \
        -e HTTPS_PROXY="http://proxy.example.local:3128" \
        -e NO_PROXY="localhost,127.0.0.1" \
        -e REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt" \
        -e SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
        -p 80:8080/tcp \
        -p 443:8443/tcp \
        -p 443:8443/udp \
        bunkerity/bunkerweb-all-in-one:1.6.8
    ```

    Si el contenedor ya existe, recréalo para aplicar el nuevo entorno.

=== "Docker"

    Añade las variables al contenedor scheduler:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Docker autoconf"

    Aplica las variables al contenedor scheduler:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

=== "Kubernetes"

    Añade las variables al pod del Scheduler usando `extraEnvs`. Si necesitas una CA personalizada, móntala mediante `extraVolumes`/`extraVolumeMounts` y apunta las variables a la ruta montada:

    ```yaml
    scheduler:
      extraEnvs:
        - name: HTTP_PROXY
          value: "http://proxy.example.local:3128"
        - name: HTTPS_PROXY
          value: "http://proxy.example.local:3128"
        - name: NO_PROXY
          value: "localhost,127.0.0.1,.svc,.cluster.local"
        - name: REQUESTS_CA_BUNDLE
          value: "/etc/ssl/certs/ca-certificates.crt"
        - name: SSL_CERT_FILE
          value: "/etc/ssl/certs/ca-certificates.crt"
    ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración Swarm está obsoleta y se eliminará en una versión futura. Considera usar la [integración Kubernetes](integrations.md#kubernetes) en su lugar.

        **Más información en la [documentación de la integración Swarm](integrations.md#swarm).**

    Añade las variables al servicio scheduler:

    ```yaml
    bw-scheduler:
      image: bunkerity/bunkerweb-scheduler:1.6.8
      ...
      environment:
        HTTP_PROXY: "http://proxy.example.local:3128"
        HTTPS_PROXY: "http://proxy.example.local:3128"
        NO_PROXY: "localhost,127.0.0.1,bunkerweb,bw-scheduler,redis,db"
        REQUESTS_CA_BUNDLE: "/etc/ssl/certs/ca-certificates.crt"
        SSL_CERT_FILE: "/etc/ssl/certs/ca-certificates.crt"
      volumes:
        - /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
      ...
    ```

## Monitoreo y reportes

### Monitoreo <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

El plugin de monitoreo te permite recolectar y recuperar métricas sobre BunkerWeb. Al habilitarlo, tu(s) instancia(s) comenzará(n) a recolectar varios datos relacionados con ataques, solicitudes y rendimiento. Luego puedes recuperarlos llamando al punto final de la API `/monitoring` de forma regular o usando otros plugins como el exportador de Prometheus.

**Lista de características**

- Habilitar la recolección de varias métricas de BunkerWeb
- Recuperar métricas de la API
- Usar en combinación con otros plugins (p. ej. exportador de Prometheus)
- Página de interfaz de usuario dedicada para monitorear tu(s) instancia(s)

**Lista de configuraciones**

| Configuración                  | Predeterminado | Contexto | Múltiple | Descripción                                                  |
| ------------------------------ | -------------- | -------- | -------- | ------------------------------------------------------------ |
| `USE_MONITORING`               | `yes`          | global   | no       | Habilitar el monitoreo de BunkerWeb.                         |
| `MONITORING_METRICS_DICT_SIZE` | `10M`          | global   | no       | Tamaño del diccionario para almacenar métricas de monitoreo. |

### Exportador de Prometheus <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

El plugin exportador de Prometheus agrega un [exportador de Prometheus](https://prometheus.io/docs/instrumenting/exporters/) en tu(s) instancia(s) de BunkerWeb. Cuando está habilitado, puedes configurar tu(s) instancia(s) de Prometheus para que extraigan datos de un punto final específico en BunkerWeb y recopilen métricas internas.

También proporcionamos un [panel de control de Grafana](https://grafana.com/grafana/dashboards/20755-bunkerweb/) que puedes importar en tu propia instancia y conectar a tu propia fuente de datos de Prometheus.

**Ten en cuenta que el uso del plugin exportador de Prometheus requiere habilitar el plugin de Monitoreo (`USE_MONITORING=yes`)**

**Lista de características**

- Exportador de Prometheus que proporciona métricas internas de BunkerWeb
- Puerto, IP de escucha y URL dedicados y configurables
- Lista blanca de IP/red para máxima seguridad

**Lista de configuraciones**

| Configuración                  | Predeterminado                                        | Contexto | Múltiple | Descripción                                                                              |
| ------------------------------ | ----------------------------------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------- |
| `USE_PROMETHEUS_EXPORTER`      | `no`                                                  | global   | no       | Habilitar el exportador de Prometheus.                                                   |
| `PROMETHEUS_EXPORTER_IP`       | `0.0.0.0`                                             | global   | no       | IP de escucha del exportador de Prometheus.                                              |
| `PROMETHEUS_EXPORTER_PORT`     | `9113`                                                | global   | no       | Puerto de escucha del exportador de Prometheus.                                          |
| `PROMETHEUS_EXPORTER_URL`      | `/metrics`                                            | global   | no       | URL HTTP del exportador de Prometheus.                                                   |
| `PROMETHEUS_EXPORTER_ALLOW_IP` | `127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16` | global   | no       | Lista de IP/redes permitidas para contactar el punto final del exportador de Prometheus. |

### Reportes <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

!!! warning "Plugin de monitoreo necesario"
  Este plugin requiere que el plugin de monitoreo Pro esté instalado y habilitado con la configuración `USE_MONITORING` establecida en `yes`.

El plugin de Reportes proporciona una solución integral para reportes regulares de datos importantes de BunkerWeb, incluyendo estadísticas globales, ataques, bloqueos, solicitudes, razones e información de AS. Ofrece una amplia gama de características, incluyendo creación automática de reportes, opciones de personalización e integración perfecta con el plugin de monitoreo pro. Con el plugin de Reportes, puedes generar y gestionar fácilmente reportes para monitorear el rendimiento y la seguridad de tu aplicación.

**Lista de características**

- Reportes regulares de datos importantes de BunkerWeb, incluyendo estadísticas globales, ataques, bloqueos, solicitudes, razones e información de AS.
- Integración con el plugin de monitoreo Pro para una integración perfecta y capacidades de reporte mejoradas.
- Soporte para webhooks (clásicos, Discord y Slack) para notificaciones en tiempo real.
- Soporte para SMTP para notificaciones por correo electrónico.
- Opciones de configuración para personalización y flexibilidad.

**Lista de configuraciones**

| Configuración                  | Predeterminado     | Contexto | Descripción                                                                                             |
| ------------------------------ | ------------------ | -------- | ------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global   | Habilitar el envío del reporte por correo electrónico (HTML).                                           |
| `USE_REPORTING_WEBHOOK`        | `no`               | global   | Habilitar el envío del reporte por webhook (Markdown).                                                  |
| `REPORTING_SCHEDULE`           | `weekly`           | global   | Cadencia del reporte: `daily`, `weekly` o `monthly`.                                                    |
| `REPORTING_WEBHOOK_URLS`       |                    | global   | URLs de webhook separadas por espacios; Discord y Slack se detectan automáticamente.                    |
| `REPORTING_SMTP_EMAILS`        |                    | global   | Destinatarios de correo electrónico separados por espacios.                                             |
| `REPORTING_SMTP_HOST`          |                    | global   | Nombre de host o IP del servidor SMTP.                                                                  |
| `REPORTING_SMTP_PORT`          | `465`              | global   | Puerto SMTP. Usa `465` para SSL, `587` para TLS.                                                        |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global   | Dirección del remitente (desactiva 2FA si es requerido por tu proveedor).                               |
| `REPORTING_SMTP_FROM_USER`     |                    | global   | Nombre de usuario SMTP (recurre al correo del remitente cuando se omite y se establece una contraseña). |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global   | Contraseña SMTP.                                                                                        |
| `REPORTING_SMTP_SSL`           | `SSL`              | global   | Seguridad de conexión: `no`, `SSL` o `TLS`.                                                             |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global   | Línea de asunto para entregas por correo electrónico.                                                   |

!!! info "Notas de comportamiento"
  - `REPORTING_SMTP_EMAILS` es requerido cuando la entrega SMTP está habilitada; `REPORTING_WEBHOOK_URLS` es requerido cuando la entrega por webhook está habilitada.
  - Si tanto los webhooks como SMTP fallan, la entrega se reintenta en la próxima ejecución programada.
  - Las plantillas HTML y Markdown se encuentran en `reporting/files/`; personalízalas con precaución para mantener los marcadores de posición intactos.

## Copia de seguridad y restauración

### Copia de seguridad S3 <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :white_check_mark:

La herramienta de Copia de seguridad S3 automatiza sin problemas la protección de datos, de forma similar al plugin de copia de seguridad de la comunidad. Sin embargo, se destaca por almacenar de forma segura las copias de seguridad directamente en un bucket S3.

Al activar esta función, estás salvaguardando proactivamente la **integridad de tus datos**. Almacenar las copias de seguridad de forma **remota** protege la información crucial de amenazas como **fallos de hardware**, **ciberataques** o **desastres naturales**. Esto garantiza tanto la **seguridad** como la **disponibilidad**, permitiendo una rápida recuperación durante **eventos inesperados**, preservando la **continuidad operativa** y asegurando la **tranquilidad**.

??? warning "Información para usuarios de Red Hat Enterprise Linux (RHEL) 8.9"
    Si estás utilizando **RHEL 8.9** y planeas usar una **base de datos externa**, necesitarás instalar el paquete `mysql-community-client` para asegurar que el comando `mysqldump` esté disponible. Puedes instalar el paquete ejecutando los siguientes comandos:

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

        1. **Instalar el paquete de configuración del repositorio de PostgreSQL**

            ```bash
            dnf install "https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-$(uname -m)/pgdg-redhat-repo-latest.noarch.rpm"
            ```

        2. **Instalar el cliente de PostgreSQL**

            ```bash
            dnf install postgresql<version>
            ```

**Lista de características**

- Copia de seguridad automática de datos a un bucket S3
- Opciones de programación flexibles: diaria, semanal o mensual
- Gestión de rotación para controlar el número de copias de seguridad a mantener
- Nivel de compresión personalizable para los archivos de copia de seguridad

**Lista de configuraciones**

| Configuración                 | Predeterminado | Contexto | Descripción                                                     |
| ----------------------------- | -------------- | -------- | --------------------------------------------------------------- |
| `USE_BACKUP_S3`               | `no`           | global   | Habilitar o deshabilitar la función de copia de seguridad S3    |
| `BACKUP_S3_SCHEDULE`          | `daily`        | global   | La frecuencia de la copia de seguridad                          |
| `BACKUP_S3_ROTATION`          | `7`            | global   | El número de copias de seguridad a mantener                     |
| `BACKUP_S3_ENDPOINT`          |                | global   | El punto final S3                                               |
| `BACKUP_S3_BUCKET`            |                | global   | El bucket S3                                                    |
| `BACKUP_S3_DIR`               |                | global   | El directorio S3                                                |
| `BACKUP_S3_REGION`            |                | global   | La región S3                                                    |
| `BACKUP_S3_ACCESS_KEY_ID`     |                | global   | El ID de la clave de acceso S3                                  |
| `BACKUP_S3_ACCESS_KEY_SECRET` |                | global   | El secreto de la clave de acceso S3                             |
| `BACKUP_S3_COMP_LEVEL`        | `6`            | global   | El nivel de compresión del archivo zip de la copia de seguridad |

#### Copia de seguridad manual

Para iniciar manualmente una copia de seguridad, ejecuta el siguiente comando:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 save
    ```

Este comando creará una copia de seguridad de tu base de datos y la almacenará en el bucket S3 especificado en la configuración `BACKUP_S3_BUCKET`.

También puedes especificar un bucket S3 personalizado para la copia de seguridad proporcionando la variable de entorno `BACKUP_S3_BUCKET` al ejecutar el comando:

=== "Linux"

    ```bash
    BACKUP_S3_BUCKET=your-bucket-name bwcli plugin backup_s3 save
    ```

=== "Docker"

    ```bash
    docker exec -it -e BACKUP_S3_BUCKET=your-bucket-name <scheduler_container> bwcli plugin backup_s3 save
    ```

!!! note "Especificaciones para MariaDB/MySQL"

    En caso de que estés usando MariaDB/MySQL, puedes encontrar el siguiente error al intentar hacer una copia de seguridad de tu base de datos:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Para resolver este problema, puedes ejecutar el siguiente comando para cambiar el plugin de autenticación a `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si estás usando la integración de Docker, puedes agregar el siguiente comando al archivo `docker-compose.yml` para cambiar automáticamente el plugin de autenticación:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

#### Restauración manual

Para iniciar manualmente una restauración, ejecuta el siguiente comando:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
    ```

Este comando creará una copia de seguridad temporal de tu base de datos en el bucket S3 especificado en la configuración `BACKUP_S3_BUCKET` y restaurará tu base de datos a la última copia de seguridad disponible en el bucket.

También puedes especificar un archivo de copia de seguridad personalizado para la restauración proporcionando la ruta al mismo como argumento al ejecutar el comando:

=== "Linux"

    ```bash
    bwcli plugin backup_s3 restore s3_backup_file.zip
    ```

=== "Docker"

    ```bash
    docker exec -it <scheduler_container> bwcli plugin backup restore s3_backup_file.zip
    ```

!!! example "En caso de fallo"

    No te preocupes si la restauración falla, siempre puedes restaurar tu base de datos al estado anterior ejecutando el comando de nuevo, ya que se crea una copia de seguridad antes de la restauración:

    === "Linux"

        ```bash
        bwcli plugin backup_s3 restore
        ```

    === "Docker"

        ```bash
        docker exec -it <scheduler_container> bwcli plugin backup_s3 restore
        ```

## Migración <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :white_check_mark:

El plugin de Migración **revoluciona** las transferencias de configuración de BunkerWeb entre instancias con su **interfaz web fácil de usar**, simplificando todo el proceso de migración. Ya sea que estés actualizando sistemas, escalando la infraestructura o haciendo la transición de entornos, esta herramienta te permite transferir sin esfuerzo **configuraciones, preferencias y datos** con una facilidad y confianza inigualables. Di adiós a los engorrosos procesos manuales y hola a una **experiencia de migración fluida y sin complicaciones**.

**Lista de características**

- **Migración sin esfuerzo:** Transfiere fácilmente las configuraciones de BunkerWeb entre instancias sin las complejidades de los procedimientos manuales.

- **Interfaz web intuitiva:** Navega por el proceso de migración sin esfuerzo con una interfaz web fácil de usar diseñada para una operación intuitiva.

- **Compatibilidad entre bases de datos:** Disfruta de una migración fluida a través de varias plataformas de bases de datos, incluidas SQLite, MySQL, MariaDB y PostgreSQL, lo que garantiza la compatibilidad con tu entorno de base de datos preferido.

### Crear un archivo de migración

Para crear manualmente un archivo de migración, ejecuta el siguiente comando:

=== "Linux"

    ```bash
    bwcli plugin migration create /path/to/migration/file
    ```

=== "Docker"

    1. Crear un archivo de migración:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration create /path/to/migration/file
        ```

    2. Copiar el archivo de migración a tu máquina local:

        ```bash
        docker cp <scheduler_container>:/path/to/migration/file /path/to/migration/file
        ```

Este comando creará una copia de seguridad de tu base de datos y la almacenará en el directorio de copia de seguridad especificado en el comando.

!!! note "Especificaciones para MariaDB/MySQL"

    En caso de que estés usando MariaDB/MySQL, puedes encontrar el siguiente error al intentar hacer una copia de seguridad de tu base de datos:

    ```bash
    caching_sha2_password could not be loaded: Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so
    ```

    Para resolver este problema, puedes ejecutar el siguiente comando para cambiar el plugin de autenticación a `mysql_native_password`:

    ```sql
    ALTER USER 'yourusername'@'localhost' IDENTIFIED WITH mysql_native_password BY 'youpassword';
    ```

    Si estás usando la integración de Docker, puedes agregar el siguiente comando al archivo `docker-compose.yml` para cambiar automáticamente el plugin de autenticación:

    === "MariaDB"

        ```yaml
        bw-db:
            image: mariadb:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

    === "MySQL"

        ```yaml
        bw-db:
            image: mysql:<version>
            command: --default-authentication-plugin=mysql_native_password
            ...
        ```

### Iniciar una migración

Para iniciar manualmente una migración, ejecuta el siguiente comando:

=== "Linux"

    ```bash
    bwcli plugin migration migrate /path/to/migration/file
    ```

=== "Docker"

    1. Copia el archivo de migración al contenedor:

        ```bash
        docker cp /path/to/migration/file <scheduler_container>:/path/to/migration/file
        ```

    2. Inicia la migración:

        ```bash
        docker exec -it <scheduler_container> bwcli plugin migration migrate /path/to/migration/file
        ```

=== "Todo en uno"

    1. Copia el archivo de migración al contenedor:

        ```bash
        docker cp /path/to/migration/file bunkerweb-aio:/path/to/migration/file
        ```

    2. Inicia la migración:

        ```bash
        docker exec -it bunkerweb-aio bwcli plugin migration migrate /path/to/migration/file
        ```

Este comando migra sin problemas tus datos de BunkerWeb para que coincidan precisamente con la configuración descrita en el archivo de migración.

## Anti DDoS <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

El plugin **Anti DDoS** proporciona protección avanzada contra ataques de denegación de servicio distribuido (DDoS) mediante el monitoreo, análisis y filtrado de tráfico sospechoso en tiempo real.

Mediante el empleo de un **mecanismo de ventana deslizante**, el plugin mantiene un diccionario en memoria de las marcas de tiempo de las solicitudes para detectar picos de tráfico anormales de direcciones IP individuales. Según el modo de seguridad configurado, puede bloquear las conexiones ofensivas o registrar la actividad sospechosa para una revisión posterior.

### Características

- **Análisis de tráfico en tiempo real:** Monitorea continuamente las solicitudes entrantes para detectar posibles ataques DDoS.
- **Mecanismo de ventana deslizante:** Rastrea la actividad de solicitudes recientes dentro de una ventana de tiempo configurable.
- **Umbrales configurables:** Te permite definir el número máximo de solicitudes sospechosas por IP.
- **Lógica de bloqueo avanzada:** Evalúa tanto el recuento de solicitudes por IP como el número de IP distintas que superan el umbral.
- **Modos de seguridad flexibles:** Elige entre el bloqueo inmediato de la conexión o el modo de solo detección (registro).
- **Almacén de datos en memoria optimizado:** Garantiza búsquedas de alta velocidad y un seguimiento eficiente de las métricas.
- **Mantenimiento automático:** Borra periódicamente los datos obsoletos para mantener un rendimiento óptimo.

### Configuración

Personaliza el comportamiento del plugin usando las siguientes configuraciones:

| Configuración                | Predeterminado | Contexto | Múltiple | Descripción                                                                                             |
| ---------------------------- | -------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`           | global   | no       | Habilita o deshabilita la protección Anti DDoS. Establécelo en `"yes"` para activar el plugin.          |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`          | global   | no       | Tamaño del almacén de datos en memoria para el seguimiento de métricas de DDoS (p. ej., `10M`, `500k`). |
| `ANTIDDOS_THRESHOLD`         | `100`          | global   | no       | Número máximo de solicitudes sospechosas permitidas por IP dentro de la ventana de tiempo definida.     |
| `ANTIDDOS_WINDOW_TIME`       | `10`           | global   | no       | Ventana de tiempo en segundos durante la cual se cuentan las solicitudes sospechosas.                   |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444`  | global   | no       | Códigos de estado HTTP considerados sospechosos y utilizados para activar acciones anti-DDoS.           |
| `ANTIDDOS_DISTINCT_IP`       | `5`            | global   | no       | Número mínimo de IP distintas que deben superar el umbral antes de aplicar el modo de bloqueo.          |

### Mejores prácticas

- **Ajuste de umbrales:** Ajusta `ANTIDDOS_THRESHOLD` y `ANTIDDOS_WINDOW_TIME` según tus patrones de tráfico típicos.
- **Revisión de códigos de estado:** Actualiza regularmente `ANTIDDOS_STATUS_CODES` para capturar comportamientos sospechosos nuevos o en evolución.
- **Monitoreo:** Analiza los registros y las métricas periódicamente para ajustar la configuración y mejorar la protección general.

## Administrador de usuarios <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/EIohiUf9Fg4" title="Página del Administrador de usuarios" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

El Plugin de gestión de usuarios ofrece una interfaz robusta para administrar cuentas de usuario dentro de tu sistema.

Con este plugin, los administradores pueden crear, actualizar y deshabilitar cuentas de usuario sin esfuerzo, gestionar roles de usuario, activar o desactivar la autenticación de dos factores (2FA) y ver información detallada del usuario, como las marcas de tiempo del último inicio de sesión y los estados de la cuenta (activa o inactiva). Diseñado teniendo en cuenta la seguridad y la facilidad de uso, este plugin simplifica las tareas rutinarias de gestión de usuarios al tiempo que garantiza el cumplimiento y la auditabilidad.

### Características

- **Operaciones de cuenta de usuario:** Importar en formato CSV/XSLX, crear, editar y eliminar cuentas de usuario con facilidad.
- **Control de acceso basado en roles:** Asigna y modifica roles de usuario para gestionar permisos y niveles de acceso.
- **Gestión de 2FA:** Desactiva la autenticación de dos factores según las decisiones administrativas.
- **Información completa del usuario:** Supervisa los datos clave del usuario, incluidas las últimas horas de inicio de sesión, las fechas de creación de la cuenta y el estado activo/inactivo.
- **Registro de auditoría:** Mantiene un registro de auditoría de todas las acciones de gestión de usuarios para mejorar la seguridad y el cumplimiento.

<figure markdown>
  ![Descripción general](assets/img/user-manager.png){ align=center }
  <figcaption>Página del Administrador de usuarios</figcaption>
</figure>

<figure markdown>
  ![Formulario de creación de usuario](assets/img/user-manager-create.png){ align=center }
  <figcaption>Administrador de usuarios - Formulario de creación de usuario</figcaption>
</figure>

<figure markdown>
  ![Página de actividades](assets/img/user-manager-activities.png){ align=center }
  <figcaption>Administrador de usuarios - Página de actividades</figcaption>
</figure>

## Easy Resolve <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/45vX0WJqjxo" title="Easy Resolve" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

El plugin Easy Resolve te permite remediar rápidamente falsos positivos y problemas recurrentes directamente desde la página de Informes. Convierte las acciones guiadas de "Resolver" en actualizaciones de configuración seguras y acotadas, sin edición manual.

### Características

- Acciones con un solo clic desde Informes y detalles del informe.
- Sugerencias contextuales para ModSecurity, lista negra, DNSBL, limitación de velocidad, métodos HTTP permitidos y países en lista blanca/negra.
- Genera exclusiones seguras de ModSecurity o actualiza las listas de ignorados.
- Aplica cambios a nivel de servicio o global con comprobaciones de permisos.
- Apertura automática opcional de la página de configuración relacionada después de aplicar.

<figure markdown>
  ![Descripción general](assets/img/easy-resolve.png){ align=center }
  <figcaption>Página de informes - con Easy Resolve</figcaption>
</figure>

## Load Balancer <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/cOVp0rAt5nw?si=iVhDio8o8S4F_uag" title="Load Balancer" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

El Plugin de Load Balancer convierte BunkerWeb en un director de tráfico con guardarraíles. Declare pools upstream una vez, apunte su proxy inverso a ellos, y deje que el balanceo consciente de salud mantenga a los usuarios en backends responsivos. El modo sticky cookie emite automáticamente una cookie `BWLBID` para que las sesiones se mantengan ancladas donde quiera.

### Características

- Bloques por upstream: nombre pools y reutilícelos en hosts de proxy inverso.
- Balanceo flexible: round-robin por defecto, o sticky vía IP o cookie firmado.
- Objetivos inteligentes: resolución DNS opcional para backends de hostname más ajuste de keepalive.
- Salud integrada: sondas HTTP/HTTPS con rutas personalizadas, intervalos, códigos de estado y verificaciones SSL.
- Continuidad de sesión: cookie `BWLBID` automática cuando se habilita el modo sticky-cookie.

### Configuración

**Definición de upstream**

| Configuración                             | Predeterminado | Contexto | Múltiple | Descripción                                                                             |
| ----------------------------------------- | -------------- | -------- | -------- | --------------------------------------------------------------------------------------- |
| `LOADBALANCER_UPSTREAM_NAME`              |                | global   | sí       | Identificador upstream (referenciado por `REVERSE_PROXY_HOST`).                         |
| `LOADBALANCER_UPSTREAM_SERVERS`           |                | global   | sí       | Lista separada por espacios de direcciones backend (ej. `10.0.0.1:8080 10.0.0.2:8080`). |
| `LOADBALANCER_UPSTREAM_MODE`              | `round-robin`  | global   | sí       | Estrategia de balanceo (`round-robin` o `sticky`).                                      |
| `LOADBALANCER_UPSTREAM_STICKY_METHOD`     | `ip`           | global   | sí       | Método sticky (`ip` o `cookie`). Modo cookie emite `BWLBID`.                            |
| `LOADBALANCER_UPSTREAM_RESOLVE`           | `no`           | global   | sí       | Resolver hostnames upstream vía DNS.                                                    |
| `LOADBALANCER_UPSTREAM_KEEPALIVE`         |                | global   | sí       | Conexiones keepalive por worker.                                                        |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIMEOUT` | `60s`          | global   | sí       | Timeout inactivo para conexiones keepalive.                                             |
| `LOADBALANCER_UPSTREAM_KEEPALIVE_TIME`    | `1h`           | global   | sí       | Vida máxima para conexiones keepalive.                                                  |

**Verificaciones de salud**

| Configuración                             | Predeterminado | Contexto | Múltiple | Descripción                                                            |
| ----------------------------------------- | -------------- | -------- | -------- | ---------------------------------------------------------------------- |
| `LOADBALANCER_HEALTHCHECK_DICT_SIZE`      | `10m`          | global   | no       | Tamaño de diccionario compartido para estado de verificación de salud. |
| `LOADBALANCER_HEALTHCHECK_URL`            | `/status`      | global   | sí       | Ruta para sondear en cada backend.                                     |
| `LOADBALANCER_HEALTHCHECK_INTERVAL`       | `2000`         | global   | sí       | Intervalo entre verificaciones (ms).                                   |
| `LOADBALANCER_HEALTHCHECK_TIMEOUT`        | `1000`         | global   | sí       | Timeout por verificación (ms).                                         |
| `LOADBALANCER_HEALTHCHECK_FALL`           | `3`            | global   | sí       | Fallos consecutivos antes de marcar como down.                         |
| `LOADBALANCER_HEALTHCHECK_RISE`           | `1`            | global   | sí       | Éxitos consecutivos antes de marcar como up.                           |
| `LOADBALANCER_HEALTHCHECK_VALID_STATUSES` | `200`          | global   | sí       | Lista separada por espacios de códigos de estado HTTP válidos.         |
| `LOADBALANCER_HEALTHCHECK_CONCURRENCY`    | `10`           | global   | sí       | Máximo de sondas concurrentes.                                         |
| `LOADBALANCER_HEALTHCHECK_TYPE`           | `http`         | global   | sí       | Protocolo para verificaciones de salud (`http` o `https`).             |
| `LOADBALANCER_HEALTHCHECK_SSL_VERIFY`     | `yes`          | global   | sí       | Verificar certificados TLS al usar verificaciones HTTPS.               |
| `LOADBALANCER_HEALTHCHECK_HOST`           |                | global   | sí       | Sobrescribir header Host durante verificaciones (útil para SNI).       |

### Inicio rápido

1. Defina su pool: configure `LOADBALANCER_UPSTREAM_NAME=my-app` y liste objetivos en `LOADBALANCER_UPSTREAM_SERVERS` (ej. `10.0.0.1:8080 10.0.0.2:8080`).
2. Dirija tráfico: configure `REVERSE_PROXY_HOST=http://my-app` para que el proxy inverso use el upstream nombrado.
3. Elija un modo: mantenga round-robin por defecto o configure `LOADBALANCER_UPSTREAM_MODE=sticky` con `LOADBALANCER_UPSTREAM_STICKY_METHOD=cookie` o `ip`.
4. Agregue salud: mantenga `/status` o ajuste URLs, intervalos y estados válidos para reflejar el comportamiento de su app.
5. Ajuste conexiones: configure valores keepalive para reutilizar conexiones backend y reducir sobrecarga de handshake.

### Consejos de uso

- Haga coincidir `REVERSE_PROXY_HOST` con `LOADBALANCER_UPSTREAM_NAME` al usar cookies sticky para que los clientes se fijen al pool correcto.
- Mantenga intervalos y timeouts de verificación de salud balanceados para evitar fluctuaciones en enlaces lentos.
- Habilite `LOADBALANCER_UPSTREAM_RESOLVE` cuando apunte a hostnames que puedan cambiar vía DNS.
- Ajuste valores keepalive para reflejar capacidad backend y objetivos de reutilización de conexiones.

## Custom Pages <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

El plugin Custom Pages le permite reemplazar las páginas integradas de BunkerWeb (páginas de error, página del servidor por defecto y páginas de desafío antibot) con sus propias plantillas HTML o Lua personalizadas. Esto le permite mantener una marca consistente en todas las páginas orientadas al usuario servidas por BunkerWeb.

### Características

- **Páginas de error personalizadas por servicio** y **páginas de desafío antibot** (captcha, verificación JavaScript, reCAPTCHA, hCaptcha, Turnstile, mCaptcha).
- **Página del servidor por defecto personalizada global** para el vhost de respaldo/por defecto.
- **Análisis HTML y verificaciones de balance de etiquetas de plantilla Lua** antes de que una plantilla sea aceptada.
- **Caché automático** a `/var/cache/bunkerweb/custom_pages` con detección de cambios para activar recargas.
- **Configuración por sitio o global** a través de configuraciones/UI o variables de entorno.

### Cómo funciona

1. Al iniciar (o cuando cambian las configuraciones), el job `custom-pages.py` lee las rutas de plantilla configuradas.
2. Cada archivo debe existir y ser legible por el scheduler; el job valida la estructura HTML y el balance de etiquetas de plantilla Lua (`{% %}`, `{{ }}`, `{* *}`).
3. Los archivos aceptados se almacenan en caché bajo `/var/cache/bunkerweb/custom_pages/<type>.html`; configuraciones faltantes/vacías eliminan el archivo en caché.
4. NGINX apunta al directorio de caché vía `$template_root` cuando existe al menos una página en caché, de modo que sus plantillas se sirven en lugar de las predeterminadas.

### Configuraciones

| Configuración                    | Predeterminado | Contexto  | Descripción                                                                    |
| -------------------------------- | -------------- | --------- | ------------------------------------------------------------------------------ |
| `CUSTOM_ERROR_PAGE`              |                | multisite | Ruta absoluta a la plantilla de página de error personalizada.                 |
| `CUSTOM_DEFAULT_SERVER_PAGE`     |                | global    | Ruta absoluta a la plantilla de página del servidor por defecto personalizada. |
| `CUSTOM_ANTIBOT_CAPTCHA_PAGE`    |                | multisite | Ruta absoluta a la página de desafío CAPTCHA antibot personalizada.            |
| `CUSTOM_ANTIBOT_JAVASCRIPT_PAGE` |                | multisite | Ruta absoluta a la página de verificación JavaScript antibot personalizada.    |
| `CUSTOM_ANTIBOT_RECAPTCHA_PAGE`  |                | multisite | Ruta absoluta a la página reCAPTCHA antibot personalizada.                     |
| `CUSTOM_ANTIBOT_HCAPTCHA_PAGE`   |                | multisite | Ruta absoluta a la página hCaptcha antibot personalizada.                      |
| `CUSTOM_ANTIBOT_TURNSTILE_PAGE`  |                | multisite | Ruta absoluta a la página Turnstile antibot personalizada.                     |
| `CUSTOM_ANTIBOT_MCAPTCHA_PAGE`   |                | multisite | Ruta absoluta a la página mCaptcha antibot personalizada.                      |

### Referencia de variables de plantilla

Las plantillas de BunkerWeb usan el motor [lua-resty-template](https://github.com/bungle/lua-resty-template). Las siguientes variables están disponibles según el tipo de página:

#### Variables de página de error

Estas variables están disponibles en plantillas de página de error personalizadas (`CUSTOM_ERROR_PAGE`):

| Variable         | Tipo   | Descripción                                                          |
| ---------------- | ------ | -------------------------------------------------------------------- |
| `title`          | string | Título completo de la página (ej. `403 - Forbidden`)                 |
| `error_title`    | string | Texto del título de error (ej. `Forbidden`)                          |
| `error_code`     | string | Código de estado HTTP (ej. `403`, `404`, `500`)                      |
| `error_text`     | string | Mensaje de error descriptivo                                         |
| `error_type`     | string | Categoría de error: `client` (4xx) o `server` (5xx)                  |
| `error_solution` | string | Texto de solución sugerida                                           |
| `nonce_script`   | string | Valor nonce para etiquetas `<script>` inline (cumplimiento CSP)      |
| `nonce_style`    | string | Valor nonce para etiquetas `<style>` inline (cumplimiento CSP)       |
| `request_id`     | string | Identificador de solicitud único para depuración                     |
| `client_ip`      | string | Dirección IP del cliente                                             |
| `request_time`   | string | Marca de tiempo de la solicitud (formato: `YYYY-MM-DD HH:MM:SS UTC`) |

#### Variables de página del servidor por defecto

Estas variables están disponibles en plantillas de página del servidor por defecto personalizadas (`CUSTOM_DEFAULT_SERVER_PAGE`):

| Variable      | Tipo   | Descripción                                                    |
| ------------- | ------ | -------------------------------------------------------------- |
| `nonce_style` | string | Valor nonce para etiquetas `<style>` inline (cumplimiento CSP) |

#### Variables de página de desafío antibot

Estas variables están disponibles en plantillas de página de desafío antibot:

**Variables comunes (todas las páginas antibot):**

| Variable       | Tipo   | Descripción                                                     |
| -------------- | ------ | --------------------------------------------------------------- |
| `antibot_uri`  | string | URI de acción del formulario para enviar el desafío             |
| `nonce_script` | string | Valor nonce para etiquetas `<script>` inline (cumplimiento CSP) |
| `nonce_style`  | string | Valor nonce para etiquetas `<style>` inline (cumplimiento CSP)  |

**Desafío JavaScript (`CUSTOM_ANTIBOT_JAVASCRIPT_PAGE`):**

| Variable | Tipo   | Descripción                                          |
| -------- | ------ | ---------------------------------------------------- |
| `random` | string | Cadena aleatoria usada para resolución proof-of-work |

**Captcha (`CUSTOM_ANTIBOT_CAPTCHA_PAGE`):**

| Variable  | Tipo   | Descripción                                        |
| --------- | ------ | -------------------------------------------------- |
| `captcha` | string | Imagen captcha codificada en Base64 (formato JPEG) |

**reCAPTCHA (`CUSTOM_ANTIBOT_RECAPTCHA_PAGE`):**

| Variable            | Tipo    | Descripción                                      |
| ------------------- | ------- | ------------------------------------------------ |
| `recaptcha_sitekey` | string  | Su clave de sitio reCAPTCHA                      |
| `recaptcha_classic` | boolean | `true` si usa reCAPTCHA clásico, `false` para v3 |

**hCaptcha (`CUSTOM_ANTIBOT_HCAPTCHA_PAGE`):**

| Variable           | Tipo   | Descripción                |
| ------------------ | ------ | -------------------------- |
| `hcaptcha_sitekey` | string | Su clave de sitio hCaptcha |

**Turnstile (`CUSTOM_ANTIBOT_TURNSTILE_PAGE`):**

| Variable            | Tipo   | Descripción                            |
| ------------------- | ------ | -------------------------------------- |
| `turnstile_sitekey` | string | Su clave de sitio Cloudflare Turnstile |

**mCaptcha (`CUSTOM_ANTIBOT_MCAPTCHA_PAGE`):**

| Variable           | Tipo   | Descripción                |
| ------------------ | ------ | -------------------------- |
| `mcaptcha_sitekey` | string | Su clave de sitio mCaptcha |
| `mcaptcha_url`     | string | Su URL de mCaptcha         |

### Sintaxis de plantilla

Las plantillas usan sintaxis de plantilla Lua con los siguientes delimitadores:

- `{{ variable }}` – Mostrar una variable (escapada HTML)
- `{* variable *}` – Mostrar una variable (sin procesar, sin escapar)
- `{% lua_code %}` – Ejecutar código Lua (condicionales, bucles, etc.)
- `{-raw-}` ... `{-raw-}` – Bloque sin procesar (sin procesamiento)

**Importante**: Siempre use atributos nonce para scripts y estilos inline para cumplir con la Content Security Policy (CSP):

```html
<style nonce="{*nonce_style*}">
  /* Su CSS aquí */
</style>
<script nonce="{*nonce_script*}">
  // Su JavaScript aquí
</script>
```

### Ejemplos

=== "Página de error personalizada"

    Cree una plantilla de página de error personalizada en `/etc/bunkerweb/templates/error.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <title>{{ title }}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f5f5;
            color: #333;
          }
          .container {
            text-align: center;
            padding: 2rem;
          }
          .error-code {
            font-size: 6rem;
            font-weight: bold;
            color: {% if error_type == "server" %}#dc3545{% else %}#ffc107{% end %};
            margin: 0;
          }
          .error-title {
            font-size: 1.5rem;
            margin: 1rem 0;
          }
          .error-text {
            color: #666;
            margin-bottom: 1rem;
          }
          .request-info {
            font-size: 0.8rem;
            color: #999;
            margin-top: 2rem;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <p class="error-code">{{ error_code }}</p>
          <h1 class="error-title">{{ error_title }}</h1>
          <p class="error-text">{{ error_text }}</p>
          <p class="error-text">{{ error_solution }}</p>
          <div class="request-info">
            {% if request_id %}
            <p>ID de solicitud: <code>{{ request_id }}</code></p>
            {% end %}
            {% if request_time %}
            <p>Hora: {{ request_time }}</p>
            {% end %}
          </div>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Página captcha personalizada"

    Cree una página de desafío captcha personalizada en `/etc/bunkerweb/templates/captcha.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <title>Verificación de seguridad</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          }
          .card {
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            text-align: center;
            max-width: 400px;
          }
          h1 {
            color: #333;
            margin-bottom: 1rem;
          }
          .captcha-img {
            margin: 1rem 0;
            border-radius: 0.5rem;
          }
          input[type="text"] {
            width: 100%;
            padding: 0.75rem;
            font-size: 1.2rem;
            border: 2px solid #ddd;
            border-radius: 0.5rem;
            text-align: center;
            box-sizing: border-box;
          }
          button {
            margin-top: 1rem;
            padding: 0.75rem 2rem;
            font-size: 1rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
          }
          button:hover {
            background: #5a6fd6;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="card">
          <h1>🔒 Verificación de seguridad</h1>
          <p>Por favor ingrese el texto que ve abajo para continuar.</p>
          {-raw-}
          <form method="POST" action="{*antibot_uri*}">
            <img class="captcha-img" src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
            {-raw-}
            <input type="text" name="captcha" placeholder="Ingrese el código" required autocomplete="off" />
            <button type="submit">Verificar</button>
          </form>
        </div>
      </body>
    </html>
    {-raw-}
    ```

=== "Página del servidor por defecto personalizada"

    Cree una página del servidor por defecto personalizada en `/etc/bunkerweb/templates/default.html`:

    ```html
    {-raw-}<!doctype html>
    <html lang="es">
      <head>
        <meta charset="utf-8" />
        <title>Bienvenido</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {-raw-}
        <style nonce="{*nonce_style*}">
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
          }
          .container {
            text-align: center;
          }
          h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
          }
          p {
            color: #888;
          }
        </style>
        {-raw-}
      </head>
      <body>
        <div class="container">
          <h1>🛡️ Protegido por BunkerWeb</h1>
          <p>Este servidor está seguro y listo.</p>
        </div>
      </body>
    </html>
    {-raw-}
    ```

### Ejemplos de despliegue

=== "Linux"

    1. Cree sus archivos de plantilla en un directorio de su elección (ej. `/opt/bunkerweb/templates/`):

        ```bash
        sudo mkdir -p /opt/bunkerweb/templates
        sudo nano /opt/bunkerweb/templates/error.html
        # Pegue su plantilla de página de error personalizada
        ```

    2. Configure BunkerWeb editando `/etc/bunkerweb/variables.env`:

        ```conf
        # Página de error personalizada para todos los servicios (o use por servicio con prefijo)
        CUSTOM_ERROR_PAGE=/opt/bunkerweb/templates/error.html

        # Página del servidor por defecto personalizada (solo global)
        CUSTOM_DEFAULT_SERVER_PAGE=/opt/bunkerweb/templates/default.html

        # Página captcha personalizada (por servicio o global)
        CUSTOM_ANTIBOT_CAPTCHA_PAGE=/opt/bunkerweb/templates/captcha.html
        ```

    3. Recargue BunkerWeb:

        ```bash
        sudo systemctl reload bunkerweb
        ```

=== "Docker"

    El **scheduler** es responsable de leer, validar y almacenar en caché sus plantillas personalizadas. Solo el scheduler necesita acceso a los archivos de plantilla—BunkerWeb recibe la configuración validada automáticamente.

    1. Cree sus archivos de plantilla en un directorio local (ej. `./templates/`) y establezca los permisos correctos:

        ```bash
        mkdir templates && \
        chown root:101 templates && \
        chmod 770 templates
        ```

        !!! info "¿Por qué UID/GID 101?"
            El contenedor scheduler se ejecuta como un **usuario sin privilegios con UID 101 y GID 101**. El directorio debe ser legible por este usuario para que el scheduler pueda acceder a sus plantillas.

        Si la carpeta ya existe:

        ```bash
        chown -R root:101 templates && \
        chmod -R 770 templates
        ```

        Al usar [Docker en modo rootless](https://docs.docker.com/engine/security/rootless) o [Podman](https://podman.io/), los UID/GID de contenedor se remapean. Verifique sus rangos subuid/subgid:

        ```bash
        grep ^$(whoami): /etc/subuid && \
        grep ^$(whoami): /etc/subgid
        ```

        Por ejemplo, si el rango comienza en **100000**, el GID efectivo se convierte en **100100** (100000 + 100):

        ```bash
        mkdir templates && \
        sudo chgrp 100100 templates && \
        chmod 770 templates
        ```

    2. Monte el directorio de plantillas al **scheduler** y configure los ajustes en el scheduler (el scheduler actúa como gestor y distribuye la configuración a los workers de BunkerWeb). Puede montar las plantillas en cualquier ruta dentro del contenedor:

        ```yaml
        services:
          bunkerweb:
            image: bunkerity/bunkerweb:1.6.8
            # ... otras configuraciones (no se necesitan variables de entorno aquí para páginas personalizadas)

          bw-scheduler:
            image: bunkerity/bunkerweb-scheduler:1.6.8
            volumes:
              - ./templates:/custom_templates:ro
            environment:
              - CUSTOM_ERROR_PAGE=/custom_templates/error.html
              - CUSTOM_DEFAULT_SERVER_PAGE=/custom_templates/default.html
              - CUSTOM_ANTIBOT_CAPTCHA_PAGE=/custom_templates/captcha.html
              # ... otras configuraciones
        ```

    !!! warning "Acceso al scheduler requerido"
        Si el scheduler no puede leer los archivos de plantilla (debido a montaje faltante o permisos incorrectos), las plantillas serán silenciosamente ignoradas y se usarán las páginas por defecto. Verifique los logs del scheduler para errores de validación.

=== "Kubernetes"

    El **scheduler** es responsable de leer, validar y almacenar en caché sus plantillas personalizadas. Necesita montar las plantillas al pod del scheduler.

    1. Cree un ConfigMap con sus plantillas:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: bunkerweb-custom-templates
        data:
          error.html: |
            {-raw-}<!doctype html>
            <html lang="es">
              <head>
                <meta charset="utf-8" />
                <title>{{ title }}</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                  .error-code { font-size: 4rem; color: #dc3545; }
                </style>
                {-raw-}
              </head>
              <body>
                <p class="error-code">{{ error_code }}</p>
                <h1>{{ error_title }}</h1>
                <p>{{ error_text }}</p>
              </body>
            </html>
            {-raw-}
          captcha.html: |
            {-raw-}<!doctype html>
            <html lang="es">
              <head>
                <meta charset="utf-8" />
                <title>Verificación de seguridad</title>
                {-raw-}
                <style nonce="{*nonce_style*}">
                  body { font-family: sans-serif; text-align: center; padding: 2rem; }
                </style>
                {-raw-}
              </head>
              <body>
                <h1>Por favor verifique que es humano</h1>
                {-raw-}
                <form method="POST" action="{*antibot_uri*}">
                  <img src="data:image/jpeg;base64,{*captcha*}" alt="Captcha" />
                  {-raw-}
                  <input type="text" name="captcha" placeholder="Ingrese el código" required />
                  <button type="submit">Verificar</button>
                </form>
              </body>
            </html>
            {-raw-}
        ```

    2. Monte el ConfigMap de plantillas al pod del **scheduler** y configure los ajustes como variables de entorno:

        ```yaml
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: bunkerweb-scheduler
        spec:
          template:
            spec:
              containers:
                - name: bunkerweb-scheduler
                  image: bunkerity/bunkerweb-scheduler:1.6.8
                  env:
                    - name: CUSTOM_ERROR_PAGE
                      value: "/custom_templates/error.html"
                    - name: CUSTOM_ANTIBOT_CAPTCHA_PAGE
                      value: "/custom_templates/captcha.html"
                    # ... otras configuraciones
                  volumeMounts:
                    - name: custom-templates
                      mountPath: /custom_templates
                      readOnly: true
                  # ... otras configuraciones del contenedor
              volumes:
                - name: custom-templates
                  configMap:
                    name: bunkerweb-custom-templates
              # ... otras configuraciones del pod
        ```

    !!! tip "Usando el controlador Ingress de BunkerWeb"
        Si está usando el controlador Ingress de BunkerWeb, el scheduler está integrado en el controlador. Monte el ConfigMap al pod del controlador en su lugar.

### Notas y solución de problemas

- **Las rutas deben ser absolutas** y terminar con un nombre de archivo; valores vacíos desactivan la página personalizada correspondiente y eliminan su caché.
- **Si la validación falla** (HTML incorrecto o etiquetas Lua desbalanceadas), la plantilla se omite y la página por defecto permanece activa. Verifique los logs del scheduler para detalles.
- **Los archivos en caché** están en `/var/cache/bunkerweb/custom_pages`; actualizar el archivo fuente es suficiente—el job detecta el nuevo hash y recarga NGINX automáticamente.
- **Cumplimiento CSP**: Siempre use las variables `nonce_script` y `nonce_style` para scripts y estilos inline para asegurar el manejo adecuado de la Content Security Policy.
- **Probando plantillas**: Puede probar sus plantillas localmente renderizándolas con un motor de plantillas Lua antes de desplegarlas en BunkerWeb.

## OpenID Connect <img src='../../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

<p align="center">
  <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/0e4lcXTIIfs" title="OpenID Connect" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

El plugin **OpenID Connect** (PRO) agrega Single Sign-On (SSO) delante de su aplicación utilizando el flujo estándar OAuth 2.0 / OIDC **Authorization Code**.

Se ejecuta dentro de BunkerWeb (NGINX/Lua) y aplica la autenticación durante la **fase access**, por lo que las solicitudes no autenticadas se bloquean *antes* de llegar a su upstream.

### Cómo funciona el flujo de la solicitud

Cuando un navegador solicita una URL protegida:

1. Si no hay una sesión válida, BunkerWeb redirige al usuario al proveedor de identidad (IdP).
2. El IdP autentica al usuario y redirige de vuelta a BunkerWeb en `OPENIDC_REDIRECT_URI` (por defecto: `/callback`) con un código de autorización.
3. BunkerWeb intercambia el código por tokens en el endpoint token del IdP.
4. Los tokens se validan (issuer, audience, expiración, `iat` con tolerancia y firma mediante JWKS).
5. Se crea una sesión y el navegador es redirigido a la URL original.

```mermaid
sequenceDiagram
  participant B as Navegador
  participant BW as BunkerWeb (OpenIDC)
  participant IdP as Proveedor de identidad
  participant Up as Upstream

  B->>BW: GET /protected
  alt No autenticado
  BW-->>B: 302 Redirección al endpoint authorize del IdP
  B->>IdP: Solicitud de autorización (nonce/PKCE opcional)
  IdP-->>B: 302 Redirección a /callback?code=...
  B->>BW: GET /callback?code=...
  BW->>IdP: Solicitud de token (intercambio del código)
  IdP-->>BW: ID token + access token (+ refresh token)
  BW-->>B: 302 Redirección a la URL original
  end
  B->>BW: GET /protected (autenticado)
  BW->>Up: Reenviar solicitud (+ header de identidad opcional)
  Up-->>BW: Respuesta
  BW-->>B: Respuesta
```

!!! warning "La URL de callback debe coincidir con la configuración del cliente en el IdP"
    Registre la URL completa de callback en el IdP (esquema + host + ruta). Por ejemplo con valores por defecto: `https://app.example.com/callback`.

### Ajustes (explicados)

!!! info "Ajustes requeridos"
    Como mínimo, `OPENIDC_DISCOVERY` y `OPENIDC_CLIENT_ID` deben estar configurados para que el plugin funcione.

#### Activación

- `USE_OPENIDC` (por defecto: `no`): habilita o deshabilita la autenticación OpenID Connect para el sitio.

#### Proveedor de identidad (IdP) + registro del cliente

- `OPENIDC_DISCOVERY`: URL de discovery (p. ej. `https://idp.example.com/.well-known/openid-configuration`).
- `OPENIDC_CLIENT_ID`: identificador del cliente OAuth 2.0 registrado en el IdP.
- `OPENIDC_CLIENT_SECRET`: secreto del cliente OAuth 2.0 (usado por `basic`, `post` y `secret_jwt`).

#### Callback / redirección

- `OPENIDC_REDIRECT_URI` (por defecto: `/callback`): ruta de callback usada por el IdP tras autenticar (debe registrarse en el IdP).

#### Scopes y parámetros de autorización

- `OPENIDC_SCOPE` (por defecto: `openid email profile`): lista de scopes separados por espacios.
- `OPENIDC_AUTHORIZATION_PARAMS`: parámetros extra de autorización como pares `key=value` separados por comas.

#### Refuerzo de seguridad

- `OPENIDC_USE_NONCE` (por defecto: `yes`): añade nonce a las solicitudes de autorización.
- `OPENIDC_USE_PKCE` (por defecto: `no`): habilita PKCE para el flujo Authorization Code.
- `OPENIDC_IAT_SLACK` (por defecto: `120`): tolerancia de desfase de reloj (segundos) para validar tokens.
- `OPENIDC_ACCEPT_UNSUPPORTED_ALG` (por defecto: `no`): acepta tokens con algoritmos no soportados (no recomendado).
- `OPENIDC_FORCE_REAUTHORIZE` (por defecto: `no`): fuerza reautorización en cada solicitud (solo debug).

#### Ciclo de vida de sesión/tokens

- `OPENIDC_REFRESH_SESSION_INTERVAL`: intervalo en segundos para reautenticar/renovar la sesión silenciosamente (vacío desactiva).
- `OPENIDC_ACCESS_TOKEN_EXPIRES_IN` (por defecto: `3600`): expiración por defecto del access token si el IdP no la especifica.
- `OPENIDC_RENEW_ACCESS_TOKEN_ON_EXPIRY` (por defecto: `yes`): renueva el access token usando el refresh token cuando expira.

#### Ajustes de autenticación del endpoint token

- `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD` (por defecto: `basic`): `basic`, `post`, `secret_jwt`, `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY`: requerido con `private_key_jwt`.
- `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`: `kid` opcional para `private_key_jwt`.
- `OPENIDC_CLIENT_JWT_ASSERTION_EXPIRES_IN`: vida útil de la aserción JWT (segundos).

#### Comportamiento de logout

- `OPENIDC_LOGOUT_PATH` (por defecto: `/logout`): ruta local de logout gestionada por BunkerWeb.
- `OPENIDC_REVOKE_TOKENS_ON_LOGOUT` (por defecto: `no`): revoca tokens en el IdP al hacer logout.
- `OPENIDC_REDIRECT_AFTER_LOGOUT_URI`: redirección después del logout local (vacío = comportamiento por defecto del IdP).
- `OPENIDC_POST_LOGOUT_REDIRECT_URI`: redirección tras completar el logout en el IdP (si lo soporta).

#### Conectividad y TLS hacia el IdP

- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` (por defecto: `10000` ms cada uno): timeouts para llamadas HTTP al IdP.
- `OPENIDC_SSL_VERIFY` (por defecto: `yes`): verifica certificados TLS del IdP.
- `OPENIDC_KEEPALIVE` (por defecto: `yes`): keepalive para conexiones al IdP.
- `OPENIDC_HTTP_PROXY` / `OPENIDC_HTTPS_PROXY`: proxies para llamadas al IdP.

#### Envío de identidad al upstream

- `OPENIDC_USER_HEADER` (por defecto: `X-User`): header para pasar identidad al upstream (vacío desactiva).
- `OPENIDC_USER_HEADER_CLAIM` (por defecto: `sub`): claim a extraer para el valor del header.
- `OPENIDC_DISPLAY_CLAIM` (por defecto: `preferred_username`): claim para mostrar en logs/métricas.

#### Caché

- `OPENIDC_DISCOVERY_DICT_SIZE` (por defecto: `1m`): tamaño del shared dict para caché de discovery.
- `OPENIDC_JWKS_DICT_SIZE` (por defecto: `1m`): tamaño del shared dict para caché de JWKS.

!!! tip "Almacenamiento de sesión en Redis"
    Cuando `USE_REDIS=yes` está configurado globalmente en BunkerWeb, el plugin OpenIDC almacena las sesiones en Redis en lugar de cookies (con fallback automático a cookies si Redis no está disponible). Es el modo recomendado para despliegues multi-instancia / HA.

### Caché de discovery + JWKS

El plugin usa `OPENIDC_DISCOVERY` (la URL `.well-known/openid-configuration` del IdP) para descubrir endpoints y luego obtiene y cachea claves JWKS para validar firmas.

Los datos de discovery/JWKS se cachean en shared dictionaries de NGINX. Si tiene muchos tenants/IdPs o conjuntos grandes de claves, incremente:

- `OPENIDC_DISCOVERY_DICT_SIZE` (global)
- `OPENIDC_JWKS_DICT_SIZE` (global)

### Sesiones (cookies vs Redis)

Por defecto, las sesiones se almacenan como cookies seguras gestionadas por la librería de OpenID Connect.

Si `USE_REDIS=yes` está habilitado globalmente y Redis está configurado, el plugin cambia automáticamente a **sesiones en Redis** (con fallback automático a cookies si Redis no está disponible temporalmente). Recomendado en load balancing / HA y evita límites de tamaño de cookies cuando los tokens son grandes.

### Envío de identidad del usuario al upstream

Si `OPENIDC_USER_HEADER` está configurado (por defecto: `X-User`), el plugin inyecta un valor de header extraído de un claim (por defecto: `OPENIDC_USER_HEADER_CLAIM=sub`).

Comportamiento de seguridad importante:

- El plugin **borra cualquier header entrante** que coincida con `OPENIDC_USER_HEADER` para evitar spoofing del cliente.
- Si el claim configurado falta, el header no se establece.
- Configure `OPENIDC_USER_HEADER` como vacío para desactivar el envío de identidad.

!!! tip "Elegir un claim"
    Prefiera identificadores estables presentes en los tokens (p. ej. `sub`, `email`, `preferred_username`). Los claims se leen primero del ID token, luego de userinfo si existe.

### Logout

Las solicitudes de logout se gestionan en `OPENIDC_LOGOUT_PATH` (por defecto: `/logout`).

- Para revocar tokens en el IdP al hacer logout, configure `OPENIDC_REVOKE_TOKENS_ON_LOGOUT=yes`.
- Use `OPENIDC_REDIRECT_AFTER_LOGOUT_URI` y `OPENIDC_POST_LOGOUT_REDIRECT_URI` para controlar redirecciones tras logout.

### Autenticación del endpoint token

La mayoría de IdPs funcionan con el valor por defecto `OPENIDC_TOKEN_ENDPOINT_AUTH_METHOD=basic` (client secret via HTTP Basic). También se soportan:

- `post`
- `secret_jwt`
- `private_key_jwt` (requiere `OPENIDC_CLIENT_RSA_PRIVATE_KEY`, opcional `OPENIDC_CLIENT_RSA_PRIVATE_KEY_ID`)

### Ejemplos de configuración mínima

Ajustes mínimos requeridos por servicio protegido:

- `USE_OPENIDC=yes`
- `OPENIDC_DISCOVERY=...`
- `OPENIDC_CLIENT_ID=...`
- `OPENIDC_CLIENT_SECRET=...` (o configuración de clave JWT para `private_key_jwt`)

Opciones comunes de hardening/tuning:

- `OPENIDC_USE_NONCE=yes` (por defecto)
- `OPENIDC_USE_PKCE=yes`
- `OPENIDC_IAT_SLACK=...` si hay desfase de reloj
- `OPENIDC_TIMEOUT_CONNECT|SEND|READ` según latencia del IdP
- `OPENIDC_SSL_VERIFY=yes` (por defecto)

### Solución de problemas

- **403 con "Authentication failed"**: normalmente URL de discovery incorrecta, mismatch de URL de callback en el IdP o IdP inaccesible.
- **Desfase de reloj / "token not yet valid"**: habilite NTP; ajuste `OPENIDC_IAT_SLACK` si es necesario.
- **No se inyecta el header de usuario**: verifique que el claim de `OPENIDC_USER_HEADER_CLAIM` exista en el ID token/userinfo.
- **Despliegues multi-instancia**: habilite `USE_REDIS=yes` y configure `REDIS_HOST` (o Sentinel) para compartir sesiones.

## OpenAPI Validator <img src='../assets/img/pro-icon.svg' alt='crown pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

SOPORTE STREAM: :x:

El plugin **OpenAPI Validator** aplica su contrato de API validando las solicitudes entrantes contra una especificación OpenAPI / Swagger. Asegura que la ruta solicitada exista, que el método HTTP esté permitido y, opcionalmente, valida los parámetros de consulta, cabecera, cookie y ruta contra sus definiciones de esquema.

### Cómo funciona

1. Un trabajo programado (`openapi-download.py`) obtiene el documento OpenAPI de una URL o archivo y lo guarda en caché en el disco (cada hora por defecto).
2. En el momento de la inicialización de NGINX, el plugin compila las rutas de la especificación almacenada en caché y las guarda en un almacenamiento interno compartido.
3. Durante el procesamiento de la solicitud, el plugin hace coincidir la solicitud con las rutas compiladas y aplica la validación.

### Características

- Validación de ruta y método con una respuesta `405` cuando el método no está permitido.
- Validación opcional de parámetros para consulta, cabecera, cookie y ruta.
- Sobrescritura de la ruta base mediante `OPENAPI_BASE_PATH` o derivación automática desde la especificación.
- Permitir o denegar solicitudes a rutas no listadas en la especificación.
- Lista de ignorados configurable para endpoints como documentación o archivos de especificación.
- La especificación almacenada en caché se actualiza cada hora sin bloquear las solicitudes.

### Configuración

| Ajuste                       | Por defecto                          | Contexto  | Múltiple | Descripción                                                               |
| ---------------------------- | ------------------------------------ | --------- | -------- | ------------------------------------------------------------------------- |
| `USE_OPENAPI_VALIDATOR`      | `no`                                 | multisite | no       | Habilita la validación de rutas OpenAPI para este sitio.                  |
| `OPENAPI_SPEC`               |                                      | multisite | no       | Ruta absoluta o URL HTTP(S) al documento OpenAPI en formato JSON/YAML.    |
| `OPENAPI_BASE_PATH`          |                                      | multisite | no       | Prefijo de ruta base opcional para anteponer a cada ruta en la especificación. |
| `OPENAPI_ALLOW_UNSPECIFIED`  | `no`                                 | multisite | no       | Permite solicitudes a rutas no listadas en la especificación.             |
| `OPENAPI_ALLOW_INSECURE_URL` | `no`                                 | multisite | no       | Permite obtener la especificación OpenAPI a través de HTTP simple (no recomendado). |
| `OPENAPI_IGNORE_URLS`        | `^/docs$ ^/redoc$ ^/openapi\\.json$` | multisite | no       | Lista de regex de URL separadas por espacios para omitir la validación OpenAPI. |
| `OPENAPI_MAX_SPEC_SIZE`      | `2M`                                 | global    | no       | Tamaño máximo permitido del documento OpenAPI (acepta sufijos k/M/G).     |
| `OPENAPI_VALIDATE_PARAMS`    | `yes`                                | multisite | no       | Valida parámetros de consulta, cabecera, cookie y ruta contra la especificación. |

### Notas de comportamiento

- `OPENAPI_SPEC` puede ser un archivo local o una URL HTTPS. Las URL HTTP se bloquean a menos que `OPENAPI_ALLOW_INSECURE_URL=yes`.
- Si `OPENAPI_BASE_PATH` está vacío, el plugin deriva la ruta base de `servers[*].url` (OpenAPI 3) o `basePath` (Swagger 2) cuando está presente.
- Se aceptan solicitudes `HEAD` cuando se define `GET` para la misma ruta, y la coincidencia de ruta tolera una barra diagonal final.
- Cuando una ruta falta en la especificación y `OPENAPI_ALLOW_UNSPECIFIED=no`, la solicitud se deniega utilizando el estado de denegación configurado.
- Los fallos de validación de parámetros se deniegan y solo se registra el primer error para mantener los registros concisos.

### Inicio rápido

Establezca los valores mínimos por servicio protegido:

- `USE_OPENAPI_VALIDATOR=yes`
- `OPENAPI_SPEC=/ruta/a/openapi.yaml` (o `https://...`)

Opcionalmente, permita rutas desconocidas durante el despliegue:

- `OPENAPI_ALLOW_UNSPECIFIED=yes`
