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

    CrowdSec también proporciona un [Componente de Seguridad de Aplicaciones](https://docs.crowdsec.net/docs/appsec/intro?utm_source=external-docs&utm_medium=cta&utm_campaign=bunker-web-docs) que se puede usar para proteger su aplicación frente a ataques. Si desea utilizarlo, debe crear otro archivo de adquisición para el Componente AppSec:

    ```yaml
    appsec_configs:
      - crowdsecurity/appsec-default
    labels:
      type: appsec
    listen_addr: 0.0.0.0:7422
    source: appsec
    ```

    `appsec_configs` (plural) es una lista y añade, de modo que las configuraciones AppSec adicionales amplían `appsec-default` en lugar de reemplazarlo. El singular `appsec_config` admite un solo nombre y no puede combinarse con la clave plural: use la forma plural si piensa habilitar la detección de bots.

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
        image: bunkerity/bunkerweb:1.7.0-beta
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
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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
        image: crowdsecurity/crowdsec:v1.7.8 # Use la última versión pero siempre fije la versión para una mejor estabilidad/seguridad
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
    appsec_configs:
      - crowdsecurity/appsec-default
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

Aplica las siguientes variables de entorno (o valores del scheduler) para que la instancia de BunkerWeb pueda comunicarse con la API local de CrowdSec. Como mínimo necesitas `USE_CROWDSEC`, `CROWDSEC_API` y `CROWDSEC_API_KEY` con una clave válida creada mediante `cscli bouncers add`.

| Ajuste                      | Valor por defecto      | Contexto  | Múltiple | Descripción                                                                                                                                   |
| --------------------------- | ---------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CROWDSEC`              | `no`                   | multisite | no       | **Habilitar CrowdSec:** Establezca en `yes` para habilitar el bouncer de CrowdSec.                                                            |
| `CROWDSEC_API`              | `http://crowdsec:8080` | multisite    | no       | **URL de la API de CrowdSec:** La dirección del servicio de la API Local de CrowdSec.                                                         |
| `CROWDSEC_API_KEY`          |                        | multisite    | no       | **Clave de API de CrowdSec:** La clave de API para autenticarse con la API de CrowdSec, obtenida usando `cscli bouncers add`.                 |
| `CROWDSEC_MODE`             | `live`                 | multisite    | no       | **Modo de Operación:** `live` (consultar la API para cada solicitud) o `stream` (almacenar en caché periódicamente todas las decisiones).     |
| `CROWDSEC_ENABLE_INTERNAL`  | `no`                   | multisite    | no       | **Tráfico Interno:** Establezca en `yes` para verificar el tráfico interno contra las decisiones de CrowdSec.                                 |
| `CROWDSEC_REQUEST_TIMEOUT`  | `1000`                 | multisite    | no       | **Tiempo de Espera de la Solicitud:** Tiempo de espera en milisegundos para las solicitudes HTTP a la API Local de CrowdSec en modo `live`.   |
| `CROWDSEC_EXCLUDE_LOCATION` |                        | multisite    | no       | **Ubicaciones Excluidas:** Lista de ubicaciones (URI) separadas por comas para excluir de las verificaciones de CrowdSec.                     |
| `CROWDSEC_CACHE_EXPIRATION` | `1`                    | multisite    | no       | **Expiración de la Caché:** El tiempo de expiración de la caché en segundos para las decisiones de IP en modo `live`.                         |
| `CROWDSEC_UPDATE_FREQUENCY` | `10`                   | multisite    | no       | **Frecuencia de Actualización:** Con qué frecuencia (en segundos) obtener decisiones nuevas/expiradas de la API de CrowdSec en modo `stream`. |

!!! info "Cómo compara `CROWDSEC_EXCLUDE_LOCATION`"
    Cada entrada separada por comas excluye la propia URI **y todo lo que cuelgue de ella**: `/health` omite `/health` y `/health/live`, pero no `/healthcheck` — siempre hace falta un separador antes del resto de la ruta. La exclusión es total: una petición excluida no llega ni a la Local API ni al Componente AppSec, así que no excluya una ruta que aún quiera inspeccionar. En particular, nunca excluya `/crowdsec-internal`: la detección de bots sirve desde ahí los recursos de su desafío y excluirlo lo desactiva de forma silenciosa.

#### Ajustes del Componente de Seguridad de Aplicaciones

| Ajuste                            | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                      |
| --------------------------------- | ----------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_APPSEC_URL`             |                   | multisite   | no       | **URL de AppSec:** La URL del Componente de Seguridad de Aplicaciones de CrowdSec. Dejar vacío para deshabilitar AppSec.         |
| `CROWDSEC_APPSEC_FAILURE_ACTION`  | `passthrough`     | multisite   | no       | **Acción en Caso de Falla:** Acción a tomar cuando AppSec devuelve un error. Puede ser `passthrough` o `deny`.                   |
| `CROWDSEC_APPSEC_CONNECT_TIMEOUT` | `100`             | multisite   | no       | **Tiempo de Espera de Conexión:** El tiempo de espera en milisegundos para conectarse al Componente AppSec.                      |
| `CROWDSEC_APPSEC_SEND_TIMEOUT`    | `100`             | multisite   | no       | **Tiempo de Espera de Envío:** El tiempo de espera en milisegundos para enviar datos al Componente AppSec.                       |
| `CROWDSEC_APPSEC_PROCESS_TIMEOUT` | `500`             | multisite   | no       | **Tiempo de Espera de Procesamiento:** El tiempo de espera en milisegundos para procesar la solicitud en el Componente AppSec.   |
| `CROWDSEC_ALWAYS_SEND_TO_APPSEC`  | `no`              | multisite   | no       | **Enviar Siempre:** Establezca en `yes` para enviar siempre las solicitudes a AppSec, incluso si hay una decisión a nivel de IP. |
| `CROWDSEC_APPSEC_SSL_VERIFY`      | `no`              | multisite   | no       | **Verificar SSL:** Establezca en `yes` para verificar el certificado SSL del Componente AppSec.                                  |

!!! info "Sobre los Modos de Operación"
    - **Modo `live`** consulta la API de CrowdSec para cada solicitud entrante, proporcionando protección en tiempo real a costa de una mayor latencia.
    - **Modo `stream`** descarga periódicamente todas las decisiones de la API de CrowdSec y las almacena en caché localmente, reduciendo la latencia con un ligero retraso en la aplicación de nuevas decisiones.

#### Endpoints por servicio

Como los endpoints son `multisite`, los servicios de la misma instancia pueden usar componentes CrowdSec distintos, o solo algunos de ellos. Las dos funciones son independientes:

- Las **consultas de decisiones** están activas cuando `CROWDSEC_API` está establecido. Ponlo como cadena vacía para que un servicio se salte por completo la Local API.
- La **inspección AppSec** está activa cuando `CROWDSEC_APPSEC_URL` está establecido. Ponlo como cadena vacía para que un servicio se salte la inspección profunda de la solicitud.

Un servicio con `USE_CROWDSEC` en `yes` y ambas URL vacías no comprueba nada, y la instancia registra que no hay ningún endpoint definido.

!!! warning "Una sola caché de decisiones por instancia"
    Las decisiones en caché viven en una única zona de memoria compartida para toda la instancia, indexada por la Local API de la que proceden. Los servicios que apuntan a la misma `CROWDSEC_API` reutilizan las decisiones en caché de los demás, lo que mantiene la consulta barata. Los servicios que apuntan a Local API distintas nunca ven las decisiones de los demás. El dimensionamiento de esa zona es a nivel de instancia, así que una flota con muchas Local API distintas y listas de decisiones grandes comparte un único presupuesto.

!!! info "Clave de bouncer por Local API"
    `CROWDSEC_API_KEY` se resuelve por servicio como cualquier otro ajuste. Cuando los servicios apuntan a Local API distintas, dale a cada uno la clave registrada con `cscli bouncers add` en su propio host de CrowdSec; de lo contrario, las consultas se rechazan por no estar autenticadas.

### Detección de bots (CrowdSec 1.8+)

CrowdSec 1.8 añade la detección de bots al Componente AppSec. En lugar de banear directamente a un cliente sospechoso, el Componente AppSec puede responder con un **desafío**: una página autocontenida que toma la huella del navegador y le hace resolver una prueba de trabajo, cuyo resultado puntúa después el propio CrowdSec. BunkerWeb sirve esa página exactamente como CrowdSec la produjo — mismo estado, mismas cabeceras, misma cookie, sobre la URI original — y nunca reenvía la petición a su aplicación. Un cliente que falla sigue siendo denegado por la página de baneo propia de BunkerWeb, así que la experiencia de bloqueo no cambia.

La detección de bots **no está activada por defecto**: el bouncer retransmite un desafío en cuanto el motor emite uno, pero el motor solo lo emite una vez que usted instala la colección y carga su configuración.

**Activarla en un motor CrowdSec independiente**

```shell
cscli collections install crowdsecurity/appsec-bot-challenge
```

Después añada al archivo de adquisición de AppSec las configuraciones que ha instalado, junto a `appsec-default`:

```yaml
appsec_configs:
  - crowdsecurity/appsec-default
  - crowdsecurity/appsec-bot-*
labels:
  type: appsec
listen_addr: 0.0.0.0:7422
source: appsec
```

Reinicie CrowdSec y confirme los rechazos con `cscli alerts list --kind bot-detection`.

Tres paquetes listos para usar fijan el umbral de rechazo: `crowdsecurity/appsec-bot-challenge` rechaza a partir de una puntuación de 75, `crowdsecurity/appsec-bot-challenge-strict` a partir de 45 y `crowdsecurity/appsec-bot-challenge-permissive` a partir de 100. Instale el que quiera: son alternativas, no capas.

**Activarla en la imagen All-In-One**

Defina `CROWDSEC_EXTRA_COLLECTIONS` en el contenedor y reinícielo; el entrypoint instala la colección y añade sus configuraciones al archivo de adquisición de AppSec por usted:

```shell
docker run -d --name bunkerweb-aio \
  -e USE_CROWDSEC=yes \
  -e CROWDSEC_APPSEC_URL=http://127.0.0.1:7422 \
  -e CROWDSEC_EXTRA_COLLECTIONS="crowdsecurity/appsec-bot-challenge" \
  bunkerity/bunkerweb-all-in-one:1.7.0-beta
```

!!! warning "Los clientes desafiados necesitan JavaScript y cookies"
    La página del desafío ejecuta un script y guarda su resultado en una cookie. Cualquier cliente legítimo que no tenga ambas cosas — consumidores de API, sondas de monitorización, lectores de feeds, la mayoría de herramientas de línea de comandos — no puede resolverlo y seguirá siendo desafiado. Exclúyalos o póngalos en lista de permitidos **del lado de CrowdSec** (el paquete incluye exclusiones para buscadores, monitorización, feeds, ficheros estáticos y rutas de API), no con `CROWDSEC_EXCLUDE_LOCATION`, que desactiva toda comprobación de CrowdSec para esa ruta y no solo el desafío.

!!! warning "El host de CrowdSec necesita memoria ejecutable"
    El desafío se ofusca en el servidor mediante un runtime WebAssembly que CrowdSec solo ejecuta en modo compilador: no hay alternativa interpretada. Por eso el **host donde corre CrowdSec** necesita SSE4.1 en amd64 (arm64 no tiene ese requisito) y un núcleo que permita convertir en ejecutable una zona de memoria escribible. En un host endurecido con W^X, o bajo una política restrictiva de seccomp o SELinux, CrowdSec registra `failed to create wasm runtime in compiler mode` o `the kernel likely denied an executable memory mapping` al arrancar y la detección de bots queda desactivada. Es un requisito del host del motor, no de los navegadores de sus visitantes.

!!! tip "Conserve la Content-Security-Policy de la página del desafío"
    CrowdSec siempre adjunta una Content-Security-Policy a la página del desafío, y la página la necesita para ejecutarse. BunkerWeb la conserva porque `Content-Security-Policy` figura en el valor por defecto de `KEEP_UPSTREAM_HEADERS`. Dos ajustes evitan esa lista y romperían el desafío: un `CUSTOM_HEADER` que defina usted mismo `Content-Security-Policy`, e incluirlo en `REMOVE_HEADERS`. Si usa alguno de los dos, la instancia registra un aviso al arrancar indicando el ajuste.

**Leer el veredicto de CrowdSec en la página de Informes**

Cada remediación de CrowdSec se registra como un informe, y el informe ahora nombra el veredicto en lugar de limitarse a decir `crowdsec`. La página **Informes** lo lee como una frase — *CrowdSec AppSec: bot-detection challenge*, *CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)* — y el detalle del informe conserva debajo los campos en bruto: `source` (`appsec` o `lapi`), `action` (`ban`, `captcha` o `challenge`), `http_status` (el estado que la remediación *declaró*, que no siempre es el servido: un baneo de LAPI no lleva ninguno y un baneo de AppSec declara 403 mientras BunkerWeb responde con `DENY_HTTP_STATUS`), además de `scenario`, `origin` y `duration` cuando la decisión viene de la API local.

Un desafío servido responde con un 200 y no con un código de bloqueo, y el filtro de informes conserva las filas 4xx, `detect` y de flujo: solo por su estado, el desafío se descartaría. Ahora el filtro conserva una remediación de CrowdSec por su **motivo**, sea cual sea el estado con el que terminó, así que el desafío sí se muestra. Con `SECURITY_MODE=detect` no se sirve nada y el veredicto nombra la remediación que *se habría* aplicado, invisible de otro modo: las líneas de alerta del propio bouncer solo se emiten en las rutas que generan una respuesta.

!!! info "El escenario solo aparece en una decisión reciente"
    Una decisión de la API local lleva su escenario únicamente en una consulta en vivo. Una vez que la remediación está en caché, la caché guarda la remediación y nada más, de modo que las siguientes peticiones del mismo cliente informan de la acción sin escenario. Los veredictos de AppSec nunca llevan uno: no proceden de una decisión.

### Remediación captcha (renderizada por el antibot de BunkerWeb)

Una decisión `captcha` de CrowdSec significa *demuestra que eres humano*, no *vete*. BunkerWeb la responde con su **propio desafío antibot** en lugar de la página captcha de CrowdSec: una sola apariencia para todos los desafíos que sirve su sitio, ningún segundo juego de claves captcha que gestionar, y los proveedores que CrowdSec no ofrece — `javascript`, `cookie`, `mcaptcha`, `capjs` — quedan disponibles también para una decisión de CrowdSec.

| Ajuste                      | Predeterminado | Contexto  | Múltiple | Descripción                                                                                                                          |
| --------------------------- | -------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_CAPTCHA_PROVIDER` | `captcha`      | multisite | no       | **Desafío captcha:** Qué desafío antibot mostrar cuando CrowdSec pide un captcha. Póngalo en `no` para ignorar las decisiones captcha. |

Acepta los mismos valores que `USE_ANTIBOT`: `cookie`, `javascript`, `captcha`, `recaptcha`, `hcaptcha`, `turnstile`, `mcaptcha`, `capjs`. Los de terceros leen sus claves de los propios ajustes `ANTIBOT_*` del antibot, así que no hay nada que configurar dos veces.

!!! warning "El antibot debe estar activado en el servicio"
    La página de desafío solo existe en un servicio cuyo `USE_ANTIBOT` esté puesto en algo distinto de `no` (o que tenga una regla de desafío de workflow). En un servicio sin ello, una decisión `captcha` se **banea** en lugar de desafiarse, y la instancia registra una línea que nombra ambos ajustes. `USE_ANTIBOT: "cookie"` es la forma más barata de activarlo: un visitante corriente pasa en un solo viaje de ida y vuelta, mientras que a un cliente marcado por CrowdSec se le muestra el desafío de `CROWDSEC_CAPTCHA_PROVIDER`.

!!! warning "Esto cambia el comportamiento al actualizar"
    Hasta ahora BunkerWeb solo reaccionaba a las decisiones `ban`, de modo que una decisión `captcha` de su Local API nunca se recuperaba y no tenía ningún efecto. Ahora se recupera, se cachea y se respeta, y renderiza el desafío descrito arriba. Para conservar el comportamiento anterior, ponga `CROWDSEC_CAPTCHA_PROVIDER: "no"`: las decisiones captcha se ignoran entonces exactamente como antes. Tenga en cuenta que el filtro ampliado es `BOUNCING_ON_TYPE=all` y no un par `ban`+`captcha` — el bouncer solo acepta un valor —, así que una decisión de **cualquier otro** tipo que emitan sus perfiles de CrowdSec también se respeta ahora y, al ser desconocida para el bouncer, se aplica como un baneo. Y la exclusión solo restaura el comportamiento anterior **por completo si todos los servicios que comparten la misma Local API de CrowdSec la ponen**: la caché de decisiones se particiona por Local API, no por servicio (`cache_partition.lua`), así que un servicio hermano que se quede con el valor por defecto cachea la decisión captcha y el servicio que se excluye la lee y banea con ella.

!!! tip "`cookie` no prueba nada aquí"
    El proveedor `cookie` se resuelve solo, sin preguntar nada al visitante. Es un valor barato y razonable para `USE_ANTIBOT`, pero como `CROWDSEC_CAPTCHA_PROVIDER` cuesta dos redirecciones y concede un pase de toda la sesión ante una decisión que significa *demuestra que eres humano*. Prefiera `captcha`, `javascript` o `capjs`.

!!! info "CrowdSec nunca se entera de que el captcha fue resuelto"
    El desafío se resuelve contra BunkerWeb, no contra el motor, así que `cscli metrics` no cuenta ningún captcha, `CAPTCHA_EXPIRATION` no se aplica y otro bouncer sobre la misma Local API seguirá desafiando al mismo cliente. Quien guarda la respuesta es la sesión BunkerWeb del visitante: una vez resuelto, ese navegador no vuelve a ser desafiado durante toda la vida de su sesión — incluso si entre tanto llega una **nueva** decisión captcha para la misma dirección. Cualquier cliente sin esa sesión (otro navegador, otro dispositivo, un almacén de cookies vaciado) es desafiado con normalidad.

### Delegar el veredicto a un flujo de trabajo de seguridad

Un veredicto de CrowdSec puede ser respondido por sus propios **flujos de trabajo de seguridad** en lugar de por la remediación de CrowdSec: una regla con una condición *veredicto de CrowdSec* puede desafiar, redirigir o bloquear una petición marcada según sus propios términos.

| Ajuste                        | Predeterminado | Contexto  | Múltiple | Descripción                                                                                                                     |
| ----------------------------- | -------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `CROWDSEC_DEFER_TO_WORKFLOWS` | `no`           | multisite | no       | **Dejar decidir a los flujos de seguridad:** entregar el veredicto a los flujos asociados a este servicio en lugar de aplicarlo aquí. |

La condición lee dos hechos: la **fuente** del veredicto (`appsec` o `lapi`) y la **remediación** solicitada por CrowdSec (`ban` o `captcha`; un `challenge` lo sirve CrowdSec antes de que se ejecuten los workflows, por lo que no se ofrece). Una petición que CrowdSec no juzgó deja la condición indecisa, lo que nunca coincide; una petición que CrowdSec juzgó y no tuvo nada en contra la hace falsa.

!!! warning "Por defecto no se abre nada"
    Con `no` —el valor predeterminado— CrowdSec aplica su veredicto él mismo, exactamente como antes. Con `yes`, el veredicto se aplica sin cambios cuando ninguna regla coincide, y la instancia registra una línea que nombra ambos ajustes si el servicio no tiene ningún flujo asociado.

!!! info "Tres respuestas siguen viniendo de BunkerWeb mientras el veredicto espera"
    El preflight CORS (`204`), `/robots.txt` y `/security.txt` los genera BunkerWeb antes de que se ejecuten los flujos, así que un cliente marcado todavía puede recibir esos tres. Ninguno llega a su aplicación, y toda petición que sí lo haría pasa antes por la escalera de flujos.

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

=== "Configuración por servicio"

    AppSec en todos los servicios públicos, consultas de decisiones solo en un subconjunto, y un servicio dejado fuera por completo. Los valores sin prefijo son la base a nivel de flota y cada servicio solo sobrescribe lo que difiere:

    ```yaml
    MULTISITE: "yes"
    SERVER_NAME: "app1.example.com app2.example.com intranet.example.com"

    # Base para todos los servicios
    USE_CROWDSEC: "yes"
    CROWDSEC_APPSEC_URL: "http://crowdsec:7422"
    CROWDSEC_API: "" # Sin consulta de decisiones a menos que un servicio la solicite
    CROWDSEC_API_KEY: ""

    # app1 añade la consulta de decisiones de la Local API además de AppSec
    app1.example.com_CROWDSEC_API: "http://crowdsec:8080"
    app1.example.com_CROWDSEC_API_KEY: "your-api-key-here"

    # app2 conserva solo AppSec, heredando la base vacía de CROWDSEC_API

    # intranet no se comprueba en absoluto
    intranet.example.com_USE_CROWDSEC: "no"
    ```

    Un servicio también puede apuntar a un host de CrowdSec completamente distinto, con su propia clave de bouncer:

    ```yaml
    app2.example.com_CROWDSEC_API: "http://crowdsec-dmz:8080"
    app2.example.com_CROWDSEC_API_KEY: "dmz-bouncer-key"
    app2.example.com_CROWDSEC_APPSEC_URL: "http://crowdsec-dmz:7422"
    ```

### Paso&nbsp;3 – Validar la integración

- En los registros del scheduler, busque las entradas `CrowdSec configuration successfully generated` y `CrowdSec bouncer denied request` para verificar que el complemento esté activo.
- En el lado de CrowdSec, supervise `cscli metrics show` o la CrowdSec Console para asegurarse de que las decisiones de BunkerWeb aparezcan como se espera.
- En la interfaz de BunkerWeb, abra la página del complemento CrowdSec para ver el estado de la integración.
