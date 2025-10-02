El complemento de Lista Blanca le permite definir una lista de direcciones IP de confianza que omiten otros filtros de seguridad.
Para bloquear clientes no deseados, consulte el [complemento de Lista Negra](#blacklist).

El complemento de Lista Blanca proporciona un enfoque integral para permitir explícitamente el acceso a su sitio web basándose en diversos atributos del cliente. Esta característica proporciona un mecanismo de seguridad: a los visitantes que coinciden con criterios específicos se les concede acceso inmediato, mientras que todos los demás deben pasar por los controles de seguridad habituales.

**Cómo funciona:**

1.  Usted define los criterios para los visitantes que deben estar en la "lista blanca" (_direcciones IP, redes, DNS inverso, ASN, User-Agent o patrones de URI_).
2.  Cuando un visitante intenta acceder a su sitio, BunkerWeb comprueba si coincide con alguno de estos criterios de la lista blanca.
3.  Si un visitante coincide con alguna regla de la lista blanca (y no coincide con ninguna regla de omisión), se le concede acceso a su sitio y **omite todos los demás controles de seguridad**.
4.  Si un visitante no coincide con ningún criterio de la lista blanca, procede a través de todos los controles de seguridad normales como de costumbre.
5.  Las listas blancas se pueden actualizar automáticamente desde fuentes externas de forma programada.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Blanca:

1.  **Habilite la función:** La función de Lista Blanca está deshabilitada por defecto. Establezca el ajuste `USE_WHITELIST` en `yes` para habilitarla.
2.  **Configure las reglas de permiso:** Defina qué IP, redes, patrones de DNS inverso, ASN, User-Agents o URI deben estar en la lista blanca.
3.  **Configure las reglas de omisión:** Especifique cualquier excepción que deba omitir las comprobaciones de la lista blanca.
4.  **Añada fuentes externas:** Configure URL para descargar y actualizar automáticamente los datos de la lista blanca.
5.  **Supervise el acceso:** Consulte la [interfaz de usuario web](web-ui.md) para ver qué visitantes están siendo permitidos o denegados.

!!! info "modo stream"
Cuando se utiliza el modo stream, solo se realizan las comprobaciones de IP, DNS inverso y ASN.

### Ajustes de Configuración

**General**

| Ajuste          | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                |
| --------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------ |
| `USE_WHITELIST` | `no`              | multisite | no       | **Habilitar Lista Blanca:** Establezca en `yes` para habilitar la función de lista blanca. |

=== "Dirección IP"
**Qué hace esto:** Pone en la lista blanca a los visitantes según su dirección IP o red. Estos visitantes omitirán todos los controles de seguridad.

    | Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | -------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_IP`             |                   | multisite | no       | **Lista Blanca de IP:** Lista de direcciones IP o redes (notación CIDR) para permitir, separadas por espacios.                            |
    | `WHITELIST_IGNORE_IP`      |                   | multisite | no       | **Lista de Omisión de IP:** Lista de direcciones IP o redes que deben omitir las comprobaciones de la lista blanca de IP.                 |
    | `WHITELIST_IP_URLS`        |                   | multisite | no       | **URL de Lista Blanca de IP:** Lista de URL que contienen direcciones IP o redes para incluir en la lista blanca, separadas por espacios. |
    | `WHITELIST_IGNORE_IP_URLS` |                   | multisite | no       | **URL de Lista de Omisión de IP:** Lista de URL que contienen direcciones IP o redes para ignorar.                                        |

=== "DNS Inverso"
**Qué hace esto:** Pone en la lista blanca a los visitantes según su nombre de dominio (en inverso). Esto es útil para permitir el acceso a visitantes de organizaciones o redes específicas por su dominio.

    | Ajuste                       | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                 |
    | ---------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_RDNS`             |                   | multisite | no       | **Lista Blanca de rDNS:** Lista de sufijos de DNS inverso para permitir, separados por espacios.                                            |
    | `WHITELIST_RDNS_GLOBAL`      | `yes`             | multisite | no       | **Solo rDNS Global:** Realiza comprobaciones de la lista blanca de rDNS solo en direcciones IP globales cuando se establece en `yes`.       |
    | `WHITELIST_IGNORE_RDNS`      |                   | multisite | no       | **Lista de Omisión de rDNS:** Lista de sufijos de DNS inverso que deben omitir las comprobaciones de la lista blanca de rDNS.               |
    | `WHITELIST_RDNS_URLS`        |                   | multisite | no       | **URL de Lista Blanca de rDNS:** Lista de URL que contienen sufijos de DNS inverso para incluir en la lista blanca, separadas por espacios. |
    | `WHITELIST_IGNORE_RDNS_URLS` |                   | multisite | no       | **URL de Lista de Omisión de rDNS:** Lista de URL que contienen sufijos de DNS inverso para ignorar.                                        |

=== "ASN"
**Qué hace esto:** Pone en la lista blanca a los visitantes de proveedores de red específicos utilizando Números de Sistema Autónomo. Los ASN identifican a qué proveedor u organización pertenece una IP.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                             |
    | --------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_ASN`             |                   | multisite | no       | **Lista Blanca de ASN:** Lista de Números de Sistema Autónomo para permitir, separados por espacios.                    |
    | `WHITELIST_IGNORE_ASN`      |                   | multisite | no       | **Lista de Omisión de ASN:** Lista de ASN que deben omitir las comprobaciones de la lista blanca de ASN.                |
    | `WHITELIST_ASN_URLS`        |                   | multisite | no       | **URL de Lista Blanca de ASN:** Lista de URL que contienen ASN para incluir en la lista blanca, separados por espacios. |
    | `WHITELIST_IGNORE_ASN_URLS` |                   | multisite | no       | **URL de Lista de Omisión de ASN:** Lista de URL que contienen ASN para ignorar.                                        |

=== "User Agent"
**Qué hace esto:** Pone en la lista blanca a los visitantes según el navegador o la herramienta que dicen estar usando. Esto es efectivo para permitir el acceso a herramientas o servicios conocidos específicos.

    | Ajuste                             | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | ---------------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_USER_AGENT`             |                   | multisite | no       | **Lista Blanca de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) para permitir, separados por espacios.           |
    | `WHITELIST_IGNORE_USER_AGENT`      |                   | multisite | no       | **Lista de Omisión de User-Agent:** Lista de patrones de User-Agent que deben omitir las comprobaciones de la lista blanca de User-Agent. |
    | `WHITELIST_USER_AGENT_URLS`        |                   | multisite | no       | **URL de Lista Blanca de User-Agent:** Lista de URL que contienen patrones de User-Agent para incluir en la lista blanca.                 |
    | `WHITELIST_IGNORE_USER_AGENT_URLS` |                   | multisite | no       | **URL de Lista de Omisión de User-Agent:** Lista de URL que contienen patrones de User-Agent para ignorar.                                |

=== "URI"
**Qué hace esto:** Pone en la lista blanca las solicitudes a URL específicas de su sitio. Esto es útil para permitir el acceso a puntos finales específicos independientemente de otros factores.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                         |
    | --------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
    | `WHITELIST_URI`             |                   | multisite | no       | **Lista Blanca de URI:** Lista de patrones de URI (expresión regular PCRE) para permitir, separados por espacios.                   |
    | `WHITELIST_IGNORE_URI`      |                   | multisite | no       | **Lista de Omisión de URI:** Lista de patrones de URI que deben omitir las comprobaciones de la lista blanca de URI.                |
    | `WHITELIST_URI_URLS`        |                   | multisite | no       | **URL de Lista Blanca de URI:** Lista de URL que contienen patrones de URI para incluir en la lista blanca, separados por espacios. |
    | `WHITELIST_IGNORE_URI_URLS` |                   | multisite | no       | **URL de Lista de Omisión de URI:** Lista de URL que contienen patrones de URI para ignorar.                                        |

!!! info "Soporte de Formato de URL"
Todos los ajustes `*_URLS` admiten URL HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
Las listas blancas de las URL se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada con las últimas fuentes de confianza.

!!! warning "Omisión de Seguridad"
Los visitantes en la lista blanca **omitirán por completo todos los demás controles de seguridad** en BunkerWeb, incluidas las reglas del WAF, la limitación de velocidad, la detección de bots maliciosos y cualquier otro mecanismo de seguridad. Use la lista blanca solo para fuentes de confianza en las que esté absolutamente seguro.

### Configuraciones de Ejemplo

=== "Acceso Básico de la Organización"

    Una configuración simple que pone en la lista blanca las IP de la oficina de la empresa:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP: "192.168.1.0/24 10.0.0.0/8 203.0.113.42"
    ```

=== "Configuración Avanzada"

    Una configuración más completa con múltiples criterios de lista blanca:

    ```yaml
    USE_WHITELIST: "yes"

    # Activos de la empresa y de socios de confianza
    WHITELIST_IP: "192.168.1.0/24 203.0.113.0/24"
    WHITELIST_RDNS: ".company.com .partner-company.org"
    WHITELIST_ASN: "12345 67890"  # ASN de la empresa y del socio
    WHITELIST_USER_AGENT: "(?:\b)CompanyBot(?:\b) (?:\b)PartnerCrawler(?:\b)"

    # Fuentes externas de confianza
    WHITELIST_IP_URLS: "https://example.com/trusted-networks.txt"
    WHITELIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas blancas:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_IP_URLS: "file:///ruta/a/ip-whitelist.txt"
    WHITELIST_RDNS_URLS: "file:///ruta/a/rdns-whitelist.txt"
    WHITELIST_ASN_URLS: "file:///ruta/a/asn-whitelist.txt"
    WHITELIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-whitelist.txt"
    WHITELIST_URI_URLS: "file:///ruta/a/uri-whitelist.txt"
    ```

=== "Patrón de Acceso a la API"

    Una configuración enfocada en permitir el acceso solo a puntos finales específicos de la API:

    ```yaml
    USE_WHITELIST: "yes"
    WHITELIST_URI: "^/api/v1/public/ ^/api/v1/status"
    WHITELIST_IP: "192.168.1.0/24"  # Red interna para todos los puntos finales
    ```

=== "Rastreadores Conocidos"

    Una configuración que pone en la lista blanca a los rastreadores comunes de motores de búsqueda y redes sociales:

    ```yaml
    USE_WHITELIST: "yes"

    # Verificación con DNS inverso para mayor seguridad
    WHITELIST_RDNS: ".googlebot.com .search.msn.com .crawl.yahoo.net .yandex.com .baidu.com .facebook.com"
    WHITELIST_RDNS_GLOBAL: "yes"  # Solo verificar IP globales
    ```

    Esta configuración permite que los rastreadores legítimos indexen su sitio sin estar sujetos a la limitación de velocidad u otras medidas de seguridad que podrían bloquearlos. Las comprobaciones de DNS inverso ayudan a verificar que los rastreadores provienen realmente de las empresas que dicen ser.
