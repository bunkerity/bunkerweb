<figure markdown>
  ![Descripción general](assets/img/crowdsec.svg){ align=center, width="600" }
</figure>

El complemento CrowdSec integra BunkerWeb con el motor de seguridad CrowdSec, proporcionando una capa adicional de protección contra diversas ciberamenazas. Este complemento actúa como un bouncer de [CrowdSec](https://crowdsec.net/?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs), denegando solicitudes basadas en decisiones de la API de CrowdSec.

CrowdSec es un motor de seguridad moderno y de código abierto que detecta y bloquea direcciones IP maliciosas basándose en el análisis de comportamiento y la inteligencia colectiva de su comunidad. También puede configurar [escenarios](https://docs.crowdsec.net/docs/concepts?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios) para prohibir automáticamente direcciones IP basadas en comportamiento sospechoso, beneficiándose de una lista negra de origen colectivo.

**Cómo funciona:**

1.  El motor de CrowdSec analiza los registros y detecta actividades sospechosas en su infraestructura.
2.  Cuando se detecta una actividad maliciosa, CrowdSec crea una decisión para bloquear la dirección IP infractora.
3.  BunkerWeb, actuando como un bouncer, consulta la API local de CrowdSec para obtener decisiones sobre las solicitudes entrantes.
4.  Si la dirección IP de un cliente tiene una decisión de bloqueo activa, BunkerWeb deniega el acceso a los servicios protegidos.
5.  Opcionalmente, el Componente de Seguridad de Aplicaciones puede realizar una inspección profunda de las solicitudes para una mayor seguridad.

!!! success "Beneficios clave"

      1. **Seguridad impulsada por la comunidad:** Benefíciese de la inteligencia de amenazas compartida en toda la comunidad de usuarios de CrowdSec.
      2. **Análisis de comportamiento:** Detecte ataques sofisticados basados en patrones de comportamiento, no solo en firmas.
      3. **Integración ligera:** Impacto mínimo en el rendimiento de su instancia de BunkerWeb.
      4. **Protección multinivel:** Combine la defensa perimetral (bloqueo de IP) con la seguridad de aplicaciones para una protección en profundidad.

### Requisitos previos

- Una API local de CrowdSec a la que BunkerWeb pueda acceder (normalmente el agente que se ejecuta en el mismo host o dentro de la misma red Docker).
- Acceso a los registros de acceso de BunkerWeb (`/var/log/bunkerweb/access.log` de forma predeterminada) para que el agente de CrowdSec pueda analizar las solicitudes.
- Acceso a `cscli` en el host de CrowdSec para registrar la clave del bouncer de BunkerWeb.

### Flujo de integración

1. Preparar el agente de CrowdSec para ingerir los registros de BunkerWeb.
2. Configurar BunkerWeb para que consulte la API local de CrowdSec.
3. Validar el enlace mediante la API `/crowdsec/ping` o la tarjeta de CrowdSec en el panel de administración.

Las siguientes secciones desarrollan cada paso.

### Paso&nbsp;1 – Preparar CrowdSec para ingerir los registros de BunkerWeb

=== "Docker"
    **Archivo de adquisición**

    Necesitará ejecutar una instancia de CrowdSec y configurarla para analizar los registros de BunkerWeb. Utilice el valor dedicado `bunkerweb` para el parámetro `type` en su archivo de adquisición (suponiendo que los registros de BunkerWeb se almacenan tal cual sin datos adicionales):

    ```yaml
    filenames:
      - /var/log/bunkerweb.log
    labels:
      type: bunkerweb
    ```

    Si la colección no aparece dentro del contenedor de CrowdSec, ejecuta `docker exec -it <crowdsec-container> cscli hub update` y luego reinicia ese contenedor (`docker restart <crowdsec-container>`) para que los nuevos recursos estén disponibles. Sustituye `<crowdsec-container>` por el nombre de tu contenedor CrowdSec.

    **Componente de Seguridad de Aplicaciones (*opcional*)**

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    **Syslog**

    ```syslog
    @version: 4.10

    source s_net {
        udp(
            ip("0.0.0.0")
        );
    };

    template t_imp {
        template("$MSG\n");
        template_escape(no);
    };

    destination d_file {
        file("/var/log/bunkerweb.log" template(t_imp) logrotate(enable(yes), size(100MB), rotations(7)));
    };

    log {
        source(s_net);
        destination(d_file);
    };
    ```

    **Docker Compose**

    ```yaml
    x-bw-env: &bw-env
      # Usamos un ancla para evitar repetir la misma configuración para ambos servicios
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Asegúrese de establecer el rango de IP correcto para que el planificador pueda enviar la configuración a la instancia

    services:
      bunkerweb:
        # Este es el nombre que se utilizará para identificar la instancia en el Planificador
        image: bunkerity/bunkerweb:1.6.8-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # Para soporte de QUIC / HTTP3
        environment:
          <<: *bw-env # Usamos el ancla para evitar repetir la misma configuración para todos los servicios
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services
        logging:
          driver: syslog # Enviar registros a syslog
          options:
            syslog-address: "udp://10.20.30.254:514" # La dirección IP del servicio syslog

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.8-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Asegúrese de establecer el nombre de instancia correcto
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Recuerde establecer una contraseña más segura para la base de datos
          SERVER_NAME: ""
          MULTISITE: "yes"
          USE_CROWDSEC: "yes"
          CROWDSEC_API: "http://crowdsec:8080" # Esta es la dirección de la API del contenedor de CrowdSec en la misma red
          CROWDSEC_APPSEC_URL: "http://crowdsec:7422" # Comente si no desea usar el Componente AppSec
          CROWDSEC_API_KEY: "s3cr3tb0unc3rk3y" # Recuerde establecer una clave más segura para el bouncer
        volumes:
          - bw-storage:/data # Se utiliza para persistir la caché y otros datos como las copias de seguridad
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
          MYSQL_PASSWORD: "changeme" # Recuerde establecer una contraseña más segura para la base de datos
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      crowdsec:
        image: crowdsecurity/crowdsec:v1.7.4 # Use la última versión pero siempre fije la versión para una mejor estabilidad/seguridad
        volumes:
          - cs-data:/var/lib/crowdsec/data # Para persistir los datos de CrowdSec
          - bw-logs:/var/log:ro # Los registros de BunkerWeb para que CrowdSec los analice
          - ./acquis.yaml:/etc/crowdsec/acquis.yaml # El archivo de adquisición para los registros de BunkerWeb
          - ./appsec.yaml:/etc/crowdsec/acquis.d/appsec.yaml # Comente si no desea usar el Componente AppSec
        environment:
          BOUNCER_KEY_bunkerweb: "s3cr3tb0unc3rk3y" # Recuerde establecer una clave más segura para el bouncer
          COLLECTIONS: "bunkerity/bunkerweb crowdsecurity/appsec-virtual-patching crowdsecurity/appsec-generic-rules"
          #   COLLECTIONS: "bunkerity/bunkerweb" # Si no desea usar el Componente AppSec, use esta línea en su lugar
        networks:
          - bw-universe

      syslog:
        image: balabit/syslog-ng:4.10.2
        cap_add:
          - NET_BIND_SERVICE  # Vincular a puertos bajos
          - NET_BROADCAST  # Enviar difusiones
          - NET_RAW  # Usar sockets sin procesar
          - DAC_READ_SEARCH  # Leer archivos omitiendo permisos
          - DAC_OVERRIDE  # Anular permisos de archivo
          - CHOWN  # Cambiar propietario
          - SYSLOG  # Escribir en registros del sistema
        volumes:
          - bw-logs:/var/log/bunkerweb # Este es el volumen utilizado para almacenar los registros
          - ./syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf # Este es el archivo de configuración de syslog-ng
        networks:
            bw-universe:
              ipv4_address: 10.20.30.254

    volumes:
      bw-data:
      bw-storage:
      bw-logs:
      cs-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Asegúrese de establecer el rango de IP correcto para que el planificador pueda enviar la configuración a la instancia
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Linux"

    Necesita instalar CrowdSec y configurarlo para analizar los registros de BunkerWeb. Siga la [documentación oficial](https://doc.crowdsec.net/docs/getting_started/install_crowdsec?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs#scenarios).

    Para permitir que CrowdSec analice los registros de BunkerWeb, agregue las siguientes líneas a su archivo de adquisición ubicado en `/etc/crowdsec/acquis.yaml`:

    ```yaml
    filenames:
      - /var/log/bunkerweb/access.log
      - /var/log/bunkerweb/error.log
      - /var/log/bunkerweb/modsec_audit.log
    labels:
        type: bunkerweb
    ```

    Actualiza el hub de CrowdSec e instala la colección de BunkerWeb:

    ```shell
    sudo cscli hub update
    sudo cscli collections install bunkerity/bunkerweb
    ```

    Ahora, agregue su bouncer personalizado a la API de CrowdSec usando la herramienta `cscli`:

    ```shell
    sudo cscli bouncers add crowdsec-bunkerweb-bouncer/v1.6
    ```

    !!! warning "Clave de API"
        Guarde la clave generada por el comando `cscli`; la necesitará más tarde.

    Luego reinicie el servicio de CrowdSec:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Componente de Seguridad de Aplicaciones (*opcional*)**

    Si desea usar el Componente AppSec, debe crear otro archivo de adquisición para él ubicado en `/etc/crowdsec/acquis.d/appsec.yaml`:

    ```yaml
    appsec_config: crowdsecurity/appsec-default
    labels:
        type: appsec
    listen_addr: 127.0.0.1:7422
    source: appsec
    ```

    También necesitará instalar las colecciones del Componente AppSec:

    ```shell
    sudo cscli collections install crowdsecurity/appsec-virtual-patching
    sudo cscli collections install crowdsecurity/appsec-generic-rules
    ```

    Finalmente, reinicie el servicio de CrowdSec:

    ```shell
    sudo systemctl restart crowdsec
    ```

    **Ajustes**

    Configure el complemento agregando los siguientes ajustes a su archivo de configuración de BunkerWeb:

    ```env
    USE_CROWDSEC=yes
    CROWDSEC_API=http://127.0.0.1:8080
    CROWDSEC_API_KEY=<La clave proporcionada por cscli>
    # Comente si no desea usar el Componente AppSec
    CROWDSEC_APPSEC_URL=http://127.0.0.1:7422
    ```

    Finalmente, recargue el servicio de BunkerWeb:

    ```shell
    sudo systemctl reload bunkerweb
    ```

=== "Todo en uno"

    La imagen Docker Todo en Uno (AIO) de BunkerWeb viene con CrowdSec totalmente integrado. No necesita configurar una instancia de CrowdSec separada ni configurar manualmente los archivos de adquisición para los registros de BunkerWeb cuando usa el agente interno de CrowdSec.

    Consulte la [documentación de integración de la Imagen Todo en Uno (AIO)](integrations.md#crowdsec-integration).

### Paso&nbsp;2 – Configurar los ajustes de BunkerWeb

Aplica las siguientes variables de entorno (o valores del scheduler) para que la instancia de BunkerWeb pueda comunicarse con la API local de CrowdSec. Como mínimo necesitas `USE_CROWDSEC`, `CROWDSEC_API` y una clave válida creada con `cscli bouncers add`.

| Ajuste                      | Valor por defecto      | Contexto  | Múltiple | Descripción                                                                                                                                   |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Habilitar CrowdSec:** Establezca en `yes` para habilitar el bouncer de CrowdSec.                                                            |
| `CROWDSEC_API`              | `http://crowdsec:8080` | global    | no       | **URL de la API de CrowdSec:** La dirección del servicio de la API Local de CrowdSec.                                                         |
| `CROWDSEC_API_KEY`          |                        | global    | no       | **Clave de API de CrowdSec:** La clave de API para autenticarse con la API de CrowdSec, obtenida usando `cscli bouncers add`.                 |
| `CROWDSEC_MODE`             | `live`                 | global    | no       | **Modo de Operación:** `live` (consultar la API para cada solicitud) o `stream` (almacenar en caché periódicamente todas las decisiones).     |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | global    | no       | **Tráfico Interno:** Establezca en `yes` para verificar el tráfico interno contra las decisiones de CrowdSec.                                 |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | global    | no       | **Tiempo de Espera de la Solicitud:** Tiempo de espera en milisegundos para las solicitudes HTTP a la API Local de CrowdSec en modo `live`.   |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | global    | no       | **Ubicaciones Excluidas:** Lista de ubicaciones (URI) separadas por comas para excluir de las verificaciones de CrowdSec.                     |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | global    | no       | **Expiración de la Caché:** El tiempo de expiración de la caché en segundos para las decisiones de IP en modo `live`.                         |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | global    | no       | **Frecuencia de Actualización:** Con qué frecuencia (en segundos) obtener decisiones nuevas/expiradas de la API de CrowdSec en modo `stream`. |

#### Ajustes del Componente de Seguridad de Aplicaciones

| Ajuste                            | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | global   | no       | **URL de AppSec:** La URL del Componente de Seguridad de Aplicaciones de CrowdSec. Dejar vacío para deshabilitar AppSec.         |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | global   | no       | **Acción en Caso de Falla:** Acción a tomar cuando AppSec devuelve un error. Puede ser `passthrough` o `deny`.                   |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | global   | no       | **Tiempo de Espera de Conexión:** El tiempo de espera en milisegundos para conectarse al Componente AppSec.                      |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | global   | no       | **Tiempo de Espera de Envío:** El tiempo de espera en milisegundos para enviar datos al Componente AppSec.                       |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | global   | no       | **Tiempo de Espera de Procesamiento:** El tiempo de espera en milisegundos para procesar la solicitud en el Componente AppSec.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | global   | no       | **Enviar Siempre:** Establezca en `yes` para enviar siempre las solicitudes a AppSec, incluso si hay una decisión a nivel de IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | global   | no       | **Verificar SSL:** Establezca en `yes` para verificar el certificado SSL del Componente AppSec.                                  |

!!! info "Sobre los Modos de Operación" - **Modo `live`** consulta la API de CrowdSec para cada solicitud entrante, proporcionando protección en tiempo real a costa de una mayor latencia. - **Modo `stream`** descarga periódicamente todas las decisiones de la API de CrowdSec y las almacena en caché localmente, reduciendo la latencia con un ligero retraso en la aplicación de nuevas decisiones.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Esta es una configuración simple para cuando CrowdSec se ejecuta en el mismo host:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "tu-clave-de-api-aqui"
    CROWDSEC_MODE: "live"
    ```

=== "Configuración Avanzada con AppSec"

    Una configuración más completa que incluye el Componente de Seguridad de Aplicaciones:

    ```yaml
    USE_CROWDSEC: "yes"
    CROWDSEC_API: "http://crowdsec:8080"
    CROWDSEC_API_KEY: "tu-clave-de-api-aqui"
    CROWDSEC_MODE: "stream"
    CROWDSEC_UPDATE_FREQUENCY: "30"
    CROWDSEC_EXCLUDE_LOCATION: "/health,/metrics"

    # Configuración de AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```

### Paso&nbsp;3 – Validar la integración

- En los registros del scheduler, busque las entradas `CrowdSec configuration successfully generated` y `CrowdSec bouncer denied request` para verificar que el complemento esté activo.
- En el lado de CrowdSec, supervise `cscli metrics show` o la CrowdSec Console para asegurarse de que las decisiones de BunkerWeb aparezcan como se espera.
- En la interfaz de BunkerWeb, abra la página del complemento CrowdSec para ver el estado de la integración.
    # Configuración de AppSec
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_APPSEC_FAILURE_ACTION: "deny"
    CROWDSEC_ALWAYS_SEND_TO_APPSEC: "yes"
    CROWDSEC_APPSEC_SSL_VERIFY: "yes"
    ```
