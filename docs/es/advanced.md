# Usos avanzados

Muchos ejemplos de casos de uso del mundo real están disponibles en la carpeta [examples](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/examples) del repositorio de GitHub.

También proporcionamos numerosos boilerplates, como archivos YAML para diversas integraciones y tipos de bases de datos. Estos están disponibles en la carpeta [misc/integrations](https://github.com/bunkerity/bunkerweb/tree/v1.6.5-rc3/misc/integrations).

Esta sección solo se enfoca en usos avanzados y ajustes de seguridad, consulta la [sección de características](features.md) de la documentación para ver todas las configuraciones disponibles.

## Casos de uso

!!! tip "Pruebas"
    Para realizar pruebas rápidas cuando el modo multisitio está habilitado (y si no tienes las entradas DNS adecuadas configuradas para los dominios) puedes usar curl con la cabecera HTTP Host de tu elección:
    ```shell
    curl -H "Host: app1.example.com" http://ip-o-fqdn-del-servidor
    ```

    Si estás usando HTTPS, necesitarás jugar con SNI:
    ```shell
    curl -H "Host: app1.example.com" --resolve example.com:443:ip-del-servidor https://example.com
    ```

### Detrás de un balanceador de carga o proxy inverso

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
            bunkerity/bunkerweb-all-in-one:1.6.5-rc3
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "X-Forwarded-For"
          ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
            bunkerity/bunkerweb-all-in-one:1.6.5-rc3
        ```

        Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

    === "Docker"

        Necesitarás agregar la configuración a las variables de entorno de los contenedores de BunkerWeb y del programador:

        ```yaml
        bunkerweb:
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
          image: bunkerity/bunkerweb:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ...
        bw-scheduler:
          image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
          ...
          environment:
            USE_REAL_IP: "yes"
            USE_PROXY_PROTOCOL: "yes"
            REAL_IP_FROM: "1.2.3.0/24 100.64.0.0/10"
            REAL_IP_HEADER: "proxy_protocol"
          ...
        ```

        Ten en cuenta que si tu servicio ya está creado, necesitarás eliminarlo y recrearlo para que se actualicen las nuevas variables de entorno.

### Usando mecanismos de resolución DNS personalizados

La configuración de NGINX de BunkerWeb se puede personalizar para usar diferentes resolutores de DNS según tus necesidades. Esto puede ser particularmente útil en varios escenarios:

1. Para respetar las entradas en tu archivo local `/etc/hosts`
2. Cuando necesitas usar servidores DNS personalizados para ciertos dominios
3. Para integrarse con soluciones locales de caché de DNS

#### Usando systemd-resolved

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

#### Usando dnsmasq

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
        bunkerity/bunkerweb-all-in-one:1.6.5-rc3
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
        image: bunkerity/bunkerweb:1.6.5-rc3
        ...
        environment:
          DNS_RESOLVERS: "dnsmasq"
        ...
        networks:
          - bw-universe
          - bw-services
          - bw-dns

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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

### Configuraciones personalizadas

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

Las configuraciones personalizadas se pueden aplicar globalmente o específicamente para un servidor en particular, dependiendo del contexto aplicable y de si el [modo multisitio](concepts.md#multisite-mode) está habilitado.

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
        bunkerity/bunkerweb-all-in-one:1.6.5-rc3
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
        bunkerity/bunkerweb-all-in-one:1.6.5-rc3
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
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
        Cuando usas etiquetas con la integración de autoconfiguración de Docker, solo puedes aplicar configuraciones personalizadas para el servicio web correspondiente. No es posible aplicar configuraciones **http**, **default-server-http**, **stream** o cualquier configuración global (como **server-http** o **server-stream** para todos los servicios): necesitarás montar archivos para ese propósito.

    Las etiquetas a usar deben seguir el patrón `bunkerweb.CUSTOM_CONF_<TYPE>_<NAME>`:

    - `<TYPE>`: el tipo de configuración, los valores aceptados son `SERVER_HTTP`, `MODSEC`, `MODSEC_CRS`, `CRS_PLUGINS_BEFORE`, `CRS_PLUGINS_AFTER` y `SERVER_STREAM`
    - `<NAME>`: el nombre de la configuración sin el sufijo .conf

    Aquí hay un ejemplo de prueba usando un archivo docker-compose:

    ```yaml
    myapp:
      image: nginxdemos/nginx-hello
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
      image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
      volumes:
        - ./bw-data:/data
      ...
    ```

=== "Kubernetes"

    Cuando se utiliza la [integración de Kubernetes](integrations.md#kubernetes), las configuraciones personalizadas se gestionan mediante [ConfigMap](https://kubernetes.io/docs/concepts/configuration/configmap/).

    Para mantenerlo simple, ni siquiera necesitas usar el ConfigMap con un Pod (por ejemplo, como variable de entorno o volumen): el Pod de autoconfiguración está escuchando eventos de ConfigMap y actualizará las configuraciones personalizadas cuando sea necesario.

    Al crear un ConfigMap, necesitarás añadir etiquetas especiales:

    *   **bunkerweb.io/CONFIG_TYPE**: debe establecerse a un tipo de configuración personalizada válido (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream o server-stream)
    *   **bunkerweb.io/CONFIG_SITE**: establece un nombre de servidor para aplicar la configuración a ese servidor específico (opcional, se aplicará globalmente si no se establece)

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

    !!! tip "Configuración extra personalizada"
        Desde la versión `1.6.0`, puedes añadir/sobrescribir configuraciones usando la anotación `bunkerweb.io/CONFIG_TYPE=settings`. Aquí hay un ejemplo:

        ```yaml
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: cfg-bunkerweb-extra-settings
          annotations:
            bunkerweb.io/CONFIG_TYPE: "settings"
        data:
          USE_ANTIBOT: "captcha" # configuración multisitio que se aplicará a todos los servicios que no la sobrescriban
          USE_REDIS: "yes" # configuración global que se aplicará globalmente
          ...
        ```

=== "Swarm"

    !!! warning "Obsoleto"
        La integración de Swarm está obsoleta y se eliminará en una futura versión. Por favor, considera usar la [integración de Kubernetes](integrations.md#kubernetes) en su lugar.

        **Puedes encontrar más información en la [documentación de la integración de Swarm](integrations.md#swarm).**

    Cuando se utiliza la [integración de Swarm](integrations.md#swarm), las configuraciones personalizadas se gestionan mediante [Docker Configs](https://docs.docker.com/engine/swarm/configs/).

    Para mantenerlo simple, ni siquiera necesitas adjuntar la Configuración a un servicio: el servicio de autoconfiguración está escuchando los eventos de Configuración y actualizará las configuraciones personalizadas cuando sea necesario.

    Al crear una Configuración, necesitarás añadir etiquetas especiales:

    *   **bunkerweb.CONFIG_TYPE**: debe establecerse a un tipo de configuración personalizada válido (http, server-http, default-server-http, modsec, modsec-crs, crs-plugins-before, crs-plugins-after, stream o server-stream)
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

### Ejecutando muchos servicios en producción

#### CRS Global

!!! warning "Plugins CRS"
    Cuando el CRS se carga globalmente, **los plugins CRS no son compatibles**. Si necesitas usarlos, tendrás que cargar el CRS por servicio.

Si usas BunkerWeb en producción con un gran número de servicios y habilitas la **característica de ModSecurity globalmente** con las reglas CRS, el tiempo requerido para cargar las configuraciones de BunkerWeb puede volverse demasiado largo, resultando potencialmente en un tiempo de espera agotado.

La solución es cargar las reglas CRS globalmente en lugar de por servicio. Este comportamiento no está habilitado por defecto por razones de compatibilidad con versiones anteriores y porque tiene un inconveniente: si habilitas la carga global de reglas CRS, **ya no será posible definir reglas modsec-crs** (ejecutadas antes de las reglas CRS) por servicio. Sin embargo, esta limitación puede ser superada escribiendo reglas de exclusión globales `modsec-crs` como esta:

```
SecRule REQUEST_FILENAME "@rx ^/somewhere$" "nolog,phase:4,allow,id:1010,chain"
SecRule REQUEST_HEADERS:Host "@rx ^app1\.example\.com$" "nolog"
```

Puedes habilitar la carga global de CRS estableciendo `USE_MODSECURITY_GLOBAL_CRS` en `yes`.

#### Ajustar max_allowed_packet para MariaDB/MySQL

Parece que el valor predeterminado para el parámetro `max_allowed_packet` en los servidores de bases de datos MariaDB y MySQL no es suficiente cuando se utiliza BunkerWeb con un gran número de servicios.

Si encuentras errores como este, especialmente en el programador:

```
[Warning] Aborted connection 5 to db: 'db' user: 'bunkerweb' host: '172.20.0.4' (Got a packet bigger than 'max_allowed_packet' bytes)
```

Necesitarás aumentar el `max_allowed_packet` en tu servidor de base de datos.

### Persistencia de bloqueos e informes

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

### Proteger aplicaciones UDP/TCP

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
        bunkerity/bunkerweb-all-in-one:1.6.5-rc3
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
        image: bunkerity/bunkerweb:1.6.5-rc3
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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
        image: bunkerity/bunkerweb:1.6.5-rc3
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
        image: bunkerity/bunkerweb:1.6.5-rc3
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

### PHP

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

    Si habilitas el [modo multisitio](concepts.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse usando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

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
        bunkerity/bunkerweb-all-in-one:1.6.5-rc3
    ```

    Ten en cuenta que si tu contenedor ya está creado, necesitarás eliminarlo y recrearlo para que se apliquen las nuevas variables de entorno.

=== "Docker"

    Cuando se utiliza la [integración de Docker](integrations.md#docker), para admitir aplicaciones PHP, necesitarás:

    - Montar tus archivos PHP en la carpeta `/var/www/html` de BunkerWeb
    - Configurar un contenedor PHP-FPM para tu aplicación y montar la carpeta que contiene los archivos PHP
    - Usar las configuraciones específicas `REMOTE_PHP` y `REMOTE_PHP_PATH` como variables de entorno al iniciar BunkerWeb

    Si habilitas el [modo multisitio](concepts.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse utilizando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

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
        image: bunkerity/bunkerweb:1.6.5-rc3
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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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

    Dado que la autoconfiguración de Docker implica el uso del [modo multisitio](concepts.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe tener el nombre del primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

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
        image: bunkerity/bunkerweb:1.6.5-rc3
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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc3
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

    Si habilitas el [modo multisitio](concepts.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe nombrarse utilizando el primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

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

    Dado que la integración de Swarm implica el uso del [modo multisitio](concepts.md#multisite-mode), necesitarás crear directorios separados para cada una de tus aplicaciones. Cada subdirectorio debe tener el nombre del primer valor de `SERVER_NAME`. Aquí hay un ejemplo de prueba:

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
        image: bunkerity/bunkerweb:1.6.5-rc3
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

### IPv6

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
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
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

## Ajuste de seguridad

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

## Monitoreo y reportes

#### Monitoreo <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Exportador de Prometheus <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

#### Reportes <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

!!! warning "Se necesita el plugin de Monitoreo"
    Este plugin requiere que el plugin de Monitoreo Pro esté instalado y habilitado con la configuración `USE_MONITORING` establecida en `yes`.

El plugin de Reportes proporciona una solución integral para la generación de informes periódicos de datos importantes de BunkerWeb, incluidas estadísticas globales, ataques, prohibiciones, solicitudes, motivos e información de AS. Ofrece una amplia gama de funciones, que incluyen la creación automática de informes, opciones de personalización y una integración perfecta con el plugin de monitoreo pro. Con el plugin de Reportes, puedes generar y gestionar fácilmente informes para monitorear el rendimiento y la seguridad de tu aplicación.

**Lista de características**

- Informes periódicos de datos importantes de BunkerWeb, incluidas estadísticas globales, ataques, prohibiciones, solicitudes, motivos e información de AS.
- Integración con el plugin Monitoring Pro para una integración perfecta y capacidades de generación de informes mejoradas.
- Soporte para webhooks (clásico, Discord y Slack) para notificaciones en tiempo real.
- Soporte para SMTP para notificaciones por correo electrónico.
- Opciones de configuración para personalización y flexibilidad.

**Lista de configuraciones**

| Configuración                  | Predeterminado     | Contexto | Descripción                                                                                                                                               |
| ------------------------------ | ------------------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REPORTING_SMTP`           | `no`               | global   | Habilitar el envío del informe por correo electrónico.                                                                                                    |
| `USE_REPORTING_WEBHOOK`        | `no`               | global   | Habilitar el envío del informe a través de webhook.                                                                                                       |
| `REPORTING_SCHEDULE`           | `weekly`           | global   | La frecuencia con la que se envían los informes.                                                                                                          |
| `REPORTING_WEBHOOK_URLS`       |                    | global   | Lista de URLs de webhook para recibir el informe en Markdown (separadas por espacios).                                                                    |
| `REPORTING_SMTP_EMAILS`        |                    | global   | Lista de direcciones de correo electrónico para recibir el informe en formato HTML (separadas por espacios).                                              |
| `REPORTING_SMTP_HOST`          |                    | global   | El servidor anfitrión utilizado para el envío SMTP.                                                                                                       |
| `REPORTING_SMTP_PORT`          | `465`              | global   | El puerto utilizado para SMTP. Ten en cuenta que existen diferentes estándares según el tipo de conexión (SSL = 465, TLS = 587).                          |
| `REPORTING_SMTP_FROM_EMAIL`    |                    | global   | La dirección de correo electrónico utilizada como remitente. Ten en cuenta que la 2FA debe estar deshabilitada para esta dirección de correo electrónico. |
| `REPORTING_SMTP_FROM_USER`     |                    | global   | El valor de autenticación del usuario para enviar a través de la dirección de correo electrónico del remitente.                                           |
| `REPORTING_SMTP_FROM_PASSWORD` |                    | global   | El valor de autenticación de la contraseña para enviar a través de la dirección de correo electrónico del remitente.                                      |
| `REPORTING_SMTP_SSL`           | `SSL`              | global   | Determinar si se debe utilizar o no una conexión segura para SMTP.                                                                                        |
| `REPORTING_SMTP_SUBJECT`       | `BunkerWeb Report` | global   | La línea de asunto del correo electrónico.                                                                                                                |

!!! info "Información y comportamiento"
    - si `USE_REPORTING_SMTP` se establece en `yes`, se debe establecer la configuración `REPORTING_SMTP_EMAILS`.
    - si `USE_REPORTING_WEBHOOK` se establece en `yes`, se debe establecer la configuración `REPORTING_WEBHOOK_URLS`.
    - Los valores aceptados para `REPORTING_SCHEDULE` son `daily`, `weekly` y `monthly`.
    - si no se establecen `REPORTING_SMTP_FROM_USER` y `REPORTING_SMTP_FROM_PASSWORD`, el plugin intentará enviar el correo electrónico sin autenticación.
    - si `REPORTING_SMTP_FROM_USER` no está configurado pero `REPORTING_SMTP_FROM_PASSWORD` sí, el plugin utilizará `REPORTING_SMTP_FROM_EMAIL` como nombre de usuario.
    - si el trabajo falla, el plugin volverá a intentar enviar el informe en la siguiente ejecución.

### Copia de seguridad y restauración

#### Copia de seguridad S3 <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

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

##### Copia de seguridad manual

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

##### Restauración manual

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

### Migración <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :white_check_mark:

El plugin de Migración **revoluciona** las transferencias de configuración de BunkerWeb entre instancias con su **interfaz web fácil de usar**, simplificando todo el proceso de migración. Ya sea que estés actualizando sistemas, escalando la infraestructura o haciendo la transición de entornos, esta herramienta te permite transferir sin esfuerzo **configuraciones, preferencias y datos** con una facilidad y confianza inigualables. Di adiós a los engorrosos procesos manuales y hola a una **experiencia de migración fluida y sin complicaciones**.

**Lista de características**

- **Migración sin esfuerzo:** Transfiere fácilmente las configuraciones de BunkerWeb entre instancias sin las complejidades de los procedimientos manuales.

- **Interfaz web intuitiva:** Navega por el proceso de migración sin esfuerzo con una interfaz web fácil de usar diseñada para una operación intuitiva.

- **Compatibilidad entre bases de datos:** Disfruta de una migración fluida a través de varias plataformas de bases de datos, incluidas SQLite, MySQL, MariaDB y PostgreSQL, lo que garantiza la compatibilidad con tu entorno de base de datos preferido.

#### Crear un archivo de migración

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

#### Iniciar una migración

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

## Anti DDoS <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

Soporte STREAM :x:

El plugin **Anti DDoS** proporciona protección avanzada contra ataques de denegación de servicio distribuido (DDoS) mediante el monitoreo, análisis y filtrado de tráfico sospechoso en tiempo real.

Mediante el empleo de un **mecanismo de ventana deslizante**, el plugin mantiene un diccionario en memoria de las marcas de tiempo de las solicitudes para detectar picos de tráfico anormales de direcciones IP individuales. Según el modo de seguridad configurado, puede bloquear las conexiones ofensivas o registrar la actividad sospechosa para una revisión posterior.

#### Características

- **Análisis de tráfico en tiempo real:** Monitorea continuamente las solicitudes entrantes para detectar posibles ataques DDoS.
- **Mecanismo de ventana deslizante:** Rastrea la actividad de solicitudes recientes dentro de una ventana de tiempo configurable.
- **Umbrales configurables:** Te permite definir el número máximo de solicitudes sospechosas por IP.
- **Lógica de bloqueo avanzada:** Evalúa tanto el recuento de solicitudes por IP como el número de IP distintas que superan el umbral.
- **Modos de seguridad flexibles:** Elige entre el bloqueo inmediato de la conexión o el modo de solo detección (registro).
- **Almacén de datos en memoria optimizado:** Garantiza búsquedas de alta velocidad y un seguimiento eficiente de las métricas.
- **Mantenimiento automático:** Borra periódicamente los datos obsoletos para mantener un rendimiento óptimo.

#### Configuración

Personaliza el comportamiento del plugin usando las siguientes configuraciones:

| Configuración                | Predeterminado | Contexto | Múltiple | Descripción                                                                                             |
| ---------------------------- | -------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------- |
| `USE_ANTIDDOS`               | `no`           | global   | no       | Habilita o deshabilita la protección Anti DDoS. Establécelo en `"yes"` para activar el plugin.          |
| `ANTIDDOS_METRICS_DICT_SIZE` | `10M`          | global   | no       | Tamaño del almacén de datos en memoria para el seguimiento de métricas de DDoS (p. ej., `10M`, `500k`). |
| `ANTIDDOS_THRESHOLD`         | `100`          | global   | no       | Número máximo de solicitudes sospechosas permitidas por IP dentro de la ventana de tiempo definida.     |
| `ANTIDDOS_WINDOW_TIME`       | `10`           | global   | no       | Ventana de tiempo en segundos durante la cual se cuentan las solicitudes sospechosas.                   |
| `ANTIDDOS_STATUS_CODES`      | `429 403 444`  | global   | no       | Códigos de estado HTTP considerados sospechosos y utilizados para activar acciones anti-DDoS.           |
| `ANTIDDOS_DISTINCT_IP`       | `5`            | global   | no       | Número mínimo de IP distintas que deben superar el umbral antes de aplicar el modo de bloqueo.          |

#### Mejores prácticas

- **Ajuste de umbrales:** Ajusta `ANTIDDOS_THRESHOLD` y `ANTIDDOS_WINDOW_TIME` según tus patrones de tráfico típicos.
- **Revisión de códigos de estado:** Actualiza regularmente `ANTIDDOS_STATUS_CODES` para capturar comportamientos sospechosos nuevos o en evolución.
- **Monitoreo:** Analiza los registros y las métricas periódicamente para ajustar la configuración y mejorar la protección general.

## Administrador de usuarios <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

El Plugin de gestión de usuarios ofrece una interfaz robusta para administrar cuentas de usuario dentro de tu sistema.

Con este plugin, los administradores pueden crear, actualizar y deshabilitar cuentas de usuario sin esfuerzo, gestionar roles de usuario, activar o desactivar la autenticación de dos factores (2FA) y ver información detallada del usuario, como las marcas de tiempo del último inicio de sesión y los estados de la cuenta (activa o inactiva). Diseñado teniendo en cuenta la seguridad y la facilidad de uso, este plugin simplifica las tareas rutinarias de gestión de usuarios al tiempo que garantiza el cumplimiento y la auditabilidad.

#### Características

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

## Easy Resolve <img src='../assets/img/pro-icon.svg' alt='crow pro icon' height='24px' width='24px' style="transform : translateY(3px);"> (PRO)

El plugin Easy Resolve te permite remediar rápidamente falsos positivos y problemas recurrentes directamente desde la página de Informes. Convierte las acciones guiadas de "Resolver" en actualizaciones de configuración seguras y acotadas, sin edición manual.

#### Características

- Acciones con un solo clic desde Informes y detalles del informe.
- Sugerencias contextuales para ModSecurity, lista negra y DNSBL.
- Genera exclusiones seguras de ModSecurity o actualiza las listas de ignorados.
- Aplica cambios a nivel de servicio o global con comprobaciones de permisos.
- Apertura automática opcional de la página de configuración relacionada después de aplicar.

<figure markdown>
  ![Descripción general](assets/img/easy-resolve.png){ align=center }
  <figcaption>Página de informes - con Easy Resolve</figcaption>
</figure>

<div class="grid grid-2" markdown>
<figure markdown>
  ![Resolución de ModSecurity](assets/img/easy-resolve-modsecurity.png){ width="100%" }
  <figcaption>Resolución de ModSecurity</figcaption>
</figure>
<figure markdown>
  ![Resolución de DNSBL](assets/img/easy-resolve-dnsbl.png){ width="100%" }
  <figcaption>Resolución de DNSBL</figcaption>
</figure>
</div>

<div class="grid grid-5" markdown>
<figure markdown>
  ![Resolución de lista negra - IP](assets/img/easy-resolve-blacklist-ip.png){ width="100%" }
  <figcaption>Lista negra - IP</figcaption>
</figure>
<figure markdown>
  ![Resolución de lista negra - User-Agent](assets/img/easy-resolve-blacklist-ua.png){ width="100%" }
  <figcaption>Lista negra - User-Agent</figcaption>
</figure>
<figure markdown>
  ![Resolución de lista negra - rDNS](assets/img/easy-resolve-blacklist-rdns.png){ width="100%" }
  <figcaption>Lista negra - rDNS</figcaption>
</figure>
<figure markdown>
  ![Resolución de lista negra - ASN](assets/img/easy-resolve-blacklist-asn.png){ width="100%" }
  <figcaption>Lista negra - ASN</figcaption>
</figure>
<figure markdown>
  ![Resolución de lista negra - URI](assets/img/easy-resolve-blacklist-uri.png){ width="100%" }
  <figcaption>Lista negra - URI</figcaption>
</figure>
</div>
