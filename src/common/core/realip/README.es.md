El complemento de IP Real asegura que BunkerWeb identifique correctamente la dirección IP del cliente incluso cuando se encuentra detrás de proxies. Esto es esencial para aplicar correctamente las reglas de seguridad, la limitación de velocidad y el registro; sin él, todas las solicitudes parecerían provenir de la IP de su proxy en lugar de la IP real del cliente.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb examina las solicitudes entrantes en busca de encabezados específicos (como [`X-Forwarded-For`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-For)) que contienen la dirección IP original del cliente.
2.  BunkerWeb comprueba si la IP entrante está en su lista de proxies de confianza (`REAL_IP_FROM`), asegurando que solo los proxies legítimos puedan pasar las IP de los clientes.
3.  La IP original del cliente se extrae del encabezado especificado (`REAL_IP_HEADER`) y se utiliza para todas las evaluaciones de seguridad y el registro.
4.  Para las cadenas de IP recursivas, BunkerWeb puede rastrear a través de múltiples saltos de proxy para determinar la IP del cliente de origen.
5.  Además, se puede habilitar el soporte para el [protocolo PROXY](https://netnut.io/what-is-proxy-protocol-and-how-does-it-work/) para recibir las IP de los clientes directamente de proxies compatibles como [HAProxy](https://www.haproxy.org/).
6.  Las listas de IP de proxies de confianza se pueden descargar y actualizar automáticamente desde fuentes externas a través de URL.

### Cómo usar

Siga estos pasos para configurar y usar la función de IP Real:

1.  **Habilite la función:** Establezca el ajuste `USE_REAL_IP` en `yes` para habilitar la detección de la IP real.
2.  **Defina los proxies de confianza:** Enumere las direcciones IP o redes de sus proxies de confianza utilizando el ajuste `REAL_IP_FROM`.
3.  **Especifique el encabezado:** Configure qué encabezado contiene la IP real utilizando el ajuste `REAL_IP_HEADER`.
4.  **Configure la recursividad:** Decida si desea rastrear las cadenas de IP de forma recursiva con el ajuste `REAL_IP_RECURSIVE`.
5.  **Fuentes de URL opcionales:** Configure las descargas automáticas de listas de proxies de confianza con `REAL_IP_FROM_URLS`.
6.  **Protocolo PROXY:** Para la comunicación directa con el proxy, habilítelo con `USE_PROXY_PROTOCOL` si su upstream lo admite.

!!! danger "Advertencia sobre el Protocolo PROXY"
    Habilitar `USE_PROXY_PROTOCOL` sin configurar correctamente su proxy upstream para enviar los encabezados del protocolo PROXY **romperá su aplicación**. Solo habilite este ajuste si está seguro de que su proxy upstream está configurado correctamente para enviar la información del protocolo PROXY. Si su proxy no está enviando los encabezados del protocolo PROXY, todas las conexiones a BunkerWeb fallarán con errores de protocolo.

### Ajustes de Configuración

| Ajuste               | Valor por defecto                         | Contexto  | Múltiple | Descripción                                                                                                                                                 |
| -------------------- | ----------------------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REAL_IP`        | `no`                                      | multisite | no       | **Habilitar IP Real:** Establezca en `yes` para habilitar la obtención de la IP real del cliente desde los encabezados o el protocolo PROXY.                |
| `REAL_IP_FROM`       | `192.168.0.0/16 172.16.0.0/12 10.0.0.0/8` | multisite | no       | **Proxies de Confianza:** Lista de direcciones IP o redes de confianza desde donde provienen las solicitudes de proxy, separadas por espacios.              |
| `REAL_IP_HEADER`     | `X-Forwarded-For`                         | multisite | no       | **Encabezado de IP Real:** Encabezado HTTP que contiene la IP real o el valor especial `proxy_protocol` para el protocolo PROXY.                            |
| `REAL_IP_RECURSIVE`  | `yes`                                     | multisite | no       | **Búsqueda Recursiva:** Cuando se establece en `yes`, realiza una búsqueda recursiva en el encabezado que contiene múltiples direcciones IP.                |
| `REAL_IP_FROM_URLS`  |                                           | multisite | no       | **URL de la Lista de IP:** URL que contienen las IP/redes de los proxies de confianza para descargar, separadas por espacios. Admite URL de tipo `file://`. |
| `USE_PROXY_PROTOCOL` | `no`                                      | global    | no       | **Protocolo PROXY:** Establezca en `yes` para habilitar el soporte del protocolo PROXY para la comunicación directa de proxy a BunkerWeb.                   |

!!! tip "Redes de Proveedores de la Nube"
    Si está utilizando un proveedor de la nube como AWS, GCP o Azure, considere agregar los rangos de IP de sus balanceadores de carga a su ajuste `REAL_IP_FROM` para garantizar la correcta identificación de la IP del cliente.

!!! danger "Consideraciones de Seguridad"
    Solo incluya las IP de los proxies de confianza en su configuración. Agregar fuentes no confiables podría permitir ataques de suplantación de IP, donde los actores maliciosos podrían falsificar la IP del cliente manipulando los encabezados.

!!! info "Múltiples Direcciones IP"
    Cuando `REAL_IP_RECURSIVE` está habilitado y un encabezado contiene múltiples IP (p. ej., `X-Forwarded-For: cliente, proxy1, proxy2`), BunkerWeb identificará como la IP del cliente la IP más a la izquierda que no esté en su lista de proxies de confianza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para un sitio detrás de un proxy inverso:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24 10.0.0.5"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Balanceador de Carga en la Nube"

    Configuración para un sitio detrás de un balanceador de carga en la nube:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Forwarded-For"
    REAL_IP_RECURSIVE: "yes"
    ```

=== "Protocolo PROXY"

    Configuración utilizando el protocolo PROXY con un balanceador de carga compatible:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.1.0/24"
    REAL_IP_HEADER: "proxy_protocol"
    USE_PROXY_PROTOCOL: "yes"
    ```

=== "Múltiples Fuentes de Proxy con URL"

    Configuración avanzada con listas de IP de proxy actualizadas automáticamente:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_HEADER: "X-Real-IP"
    REAL_IP_RECURSIVE: "yes"
    REAL_IP_FROM_URLS: "https://example.com/proxy-ips.txt file:///etc/bunkerweb/custom-proxies.txt"
    ```

=== "Configuración de CDN"

    Configuración para un sitio web detrás de una CDN:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"
    REAL_IP_FROM_URLS: "https://cdn-provider.com/ip-ranges.txt"
    REAL_IP_HEADER: "CF-Connecting-IP"  # Ejemplo para Cloudflare
    REAL_IP_RECURSIVE: "no"  # No es necesario con encabezados de una sola IP
    ```

=== "Detrás de Cloudflare"

    Configuración para un sitio web detrás de Cloudflare:

    ```yaml
    USE_REAL_IP: "yes"
    REAL_IP_FROM: "" # Solo confiamos en las IPs de Cloudflare
    REAL_IP_FROM_URLS: "https://www.cloudflare.com/ips-v4/ https://www.cloudflare.com/ips-v6/" # Descargar las IPs de Cloudflare automáticamente
    REAL_IP_HEADER: "CF-Connecting-IP"  # Encabezado de Cloudflare para la IP del cliente
    REAL_IP_RECURSIVE: "yes"
    ```
