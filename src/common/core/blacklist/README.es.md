El complemento de Lista Negra proporciona una protección robusta para su sitio web al bloquear el acceso basado en varios atributos del cliente. Esta función defiende contra entidades maliciosas conocidas, escáneres y visitantes sospechosos al denegar el acceso basado en direcciones IP, redes, entradas de DNS inverso, ASN, agentes de usuario y patrones de URI específicos.

**Cómo funciona:**

1.  El complemento comprueba las solicitudes entrantes contra múltiples criterios de la lista negra (direcciones IP, redes, rDNS, ASN, User-Agent o patrones de URI).
2.  Las listas negras se pueden especificar directamente en su configuración o cargar desde URL externas.
3.  Si un visitante coincide con alguna regla de la lista negra (y no coincide con ninguna regla de omisión), se le deniega el acceso.
4.  Las listas negras se actualizan automáticamente en un horario regular desde las URL configuradas.
5.  Puede personalizar exactamente qué criterios se comprueban y se omiten según sus necesidades de seguridad específicas.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Negra:

1.  **Habilite la función:** La función de Lista Negra está habilitada por defecto. Si es necesario, puede controlarla con el ajuste `USE_BLACKLIST`.
2.  **Configure las reglas de bloqueo:** Defina qué IP, redes, patrones de rDNS, ASN, User-Agents o URI deben ser bloqueados.
3.  **Configure las reglas de omisión:** Especifique cualquier excepción que deba omitir las comprobaciones de la lista negra.
4.  **Añada fuentes externas:** Configure las URL para descargar y actualizar automáticamente los datos de la lista negra.
5.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver las estadísticas de las solicitudes bloqueadas.

!!! info "modo stream"
    Cuando se utiliza el modo stream, solo se realizarán comprobaciones de IP, rDNS y ASN.

### Ajustes de configuración

**General**

| Ajuste                      | Valor por defecto                                       | Contexto  | Múltiple | Descripción                                                                                                                            |
| --------------------------- | ------------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BLACKLIST`             | `yes`                                                   | multisite | no       | **Habilitar Lista Negra:** Establezca en `yes` para habilitar la función de lista negra.                                               |
| `BLACKLIST_COMMUNITY_LISTS` | `ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents` | multisite | no       | **Listas Negras de la Comunidad:** Seleccione listas negras preconfiguradas mantenidas por la comunidad para incluirlas en el bloqueo. |

=== "Listas Negras de la Comunidad"
    **Qué hace esto:** Le permite añadir rápidamente listas negras bien mantenidas y de origen comunitario sin tener que configurar manualmente las URL.

    El ajuste `BLACKLIST_COMMUNITY_LISTS` le permite seleccionar de fuentes de listas negras curadas. Las opciones disponibles incluyen:

    | ID                                  | Descripción                                                                                                                                                                                                                    | Fuente                                                                                                                         |
    | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
    | `ip:danmeuk-tor-exit`               | IP de nodos de salida de Tor (dan.me.uk)                                                                                                                                                                                       | `https://www.dan.me.uk/torlist/?exit`                                                                                          |
    | `ua:mitchellkrogza-bad-user-agents` | Nginx Block Bad Bots, Spam Referrer Blocker, Vulnerability Scanners, User-Agents, Malware, Adware, Ransomware, Malicious Sites, con anti-DDOS, Wordpress Theme Detector Blocking y Fail2Ban Jail para infractores reincidentes | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` |

    **Configuración:** Especifique múltiples listas separadas por espacios. Por ejemplo:
    ```yaml
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    !!! tip "Comunidad vs Configuración Manual"
        Las listas negras de la comunidad proporcionan una forma conveniente de empezar con fuentes de listas negras probadas. Puede usarlas junto con configuraciones de URL manuales para una máxima flexibilidad.

=== "Dirección IP"
    **Qué hace esto:** Bloquea a los visitantes según su dirección IP o red.

    | Ajuste                     | Valor por defecto                     | Contexto  | Múltiple | Descripción                                                                                                              |
    | -------------------------- | ------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------ |
    | `BLACKLIST_IP`             |                                       | multisite | no       | **Lista Negra de IP:** Lista de direcciones IP o redes (notación CIDR) a bloquear, separadas por espacios.               |
    | `BLACKLIST_IGNORE_IP`      |                                       | multisite | no       | **Lista de Omisión de IP:** Lista de direcciones IP o redes que deben omitir las comprobaciones de la lista negra de IP. |
    | `BLACKLIST_IP_URLS`        | `https://www.dan.me.uk/torlist/?exit` | multisite | no       | **URL de la Lista Negra de IP:** Lista de URL que contienen direcciones IP o redes a bloquear, separadas por espacios.   |
    | `BLACKLIST_IGNORE_IP_URLS` |                                       | multisite | no       | **URL de la Lista de Omisión de IP:** Lista de URL que contienen direcciones IP o redes a omitir.                        |

    El ajuste por defecto de `BLACKLIST_IP_URLS` incluye una URL que proporciona una **lista de nodos de salida de Tor conocidos**. Esta es una fuente común de tráfico malicioso y es un buen punto de partida para muchos sitios.

=== "DNS Inverso"
    **Qué hace esto:** Bloquea a los visitantes según su nombre de dominio inverso. Esto es útil para bloquear escáneres y rastreadores conocidos basados en los dominios de su organización.

    | Ajuste                       | Valor por defecto       | Contexto  | Múltiple | Descripción                                                                                                                  |
    | ---------------------------- | ----------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_RDNS`             | `.shodan.io .censys.io` | multisite | no       | **Lista Negra de rDNS:** Lista de sufijos de DNS inverso a bloquear, separados por espacios.                                 |
    | `BLACKLIST_RDNS_GLOBAL`      | `yes`                   | multisite | no       | **Solo Global para rDNS:** Solo realizar comprobaciones de rDNS en direcciones IP globales cuando se establece en `yes`.     |
    | `BLACKLIST_IGNORE_RDNS`      |                         | multisite | no       | **Lista de Omisión de rDNS:** Lista de sufijos de DNS inverso que deben omitir las comprobaciones de la lista negra de rDNS. |
    | `BLACKLIST_RDNS_URLS`        |                         | multisite | no       | **URL de la Lista Negra de rDNS:** Lista de URL que contienen sufijos de DNS inverso a bloquear, separadas por espacios.     |
    | `BLACKLIST_IGNORE_RDNS_URLS` |                         | multisite | no       | **URL de la Lista de Omisión de rDNS:** Lista de URL que contienen sufijos de DNS inverso a omitir.                          |

    El ajuste por defecto de `BLACKLIST_RDNS` incluye dominios de escáneres comunes como **Shodan** y **Censys**. Estos son a menudo utilizados por investigadores de seguridad y escáneres para identificar sitios vulnerables.

=== "ASN"
    **Qué hace esto:** Bloquea a los visitantes de proveedores de red específicos. Los ASN son como los códigos postales de Internet: identifican a qué proveedor u organización pertenece una IP.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                             |
    | --------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_ASN`             |                   | multisite | no       | **Lista Negra de ASN:** Lista de Números de Sistema Autónomo a bloquear, separados por espacios.        |
    | `BLACKLIST_IGNORE_ASN`      |                   | multisite | no       | **Lista de Omisión de ASN:** Lista de ASN que deben omitir las comprobaciones de la lista negra de ASN. |
    | `BLACKLIST_ASN_URLS`        |                   | multisite | no       | **URL de la Lista Negra de ASN:** Lista de URL que contienen ASN a bloquear, separadas por espacios.    |
    | `BLACKLIST_IGNORE_ASN_URLS` |                   | multisite | no       | **URL de la Lista de Omisión de ASN:** Lista de URL que contienen ASN a omitir.                         |

=== "Agente de Usuario"
    **Qué hace esto:** Bloquea a los visitantes según el navegador o la herramienta que dicen estar usando. Esto es efectivo contra los bots que se identifican honestamente (como "ScannerBot" o "WebHarvestTool").

    | Ajuste                             | Valor por defecto                                                                                                              | Contexto  | Múltiple | Descripción                                                                                                                              |
    | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_USER_AGENT`             |                                                                                                                                | multisite | no       | **Lista Negra de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) a bloquear, separados por espacios.              |
    | `BLACKLIST_IGNORE_USER_AGENT`      |                                                                                                                                | multisite | no       | **Lista de Omisión de User-Agent:** Lista de patrones de User-Agent que deben omitir las comprobaciones de la lista negra de User-Agent. |
    | `BLACKLIST_USER_AGENT_URLS`        | `https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list` | multisite | no       | **URL de la Lista Negra de User-Agent:** Lista de URL que contienen patrones de User-Agent a bloquear.                                   |
    | `BLACKLIST_IGNORE_USER_AGENT_URLS` |                                                                                                                                | multisite | no       | **URL de la Lista de Omisión de User-Agent:** Lista de URL que contienen patrones de User-Agent a omitir.                                |

    El ajuste por defecto de `BLACKLIST_USER_AGENT_URLS` incluye una URL que proporciona una **lista de agentes de usuario maliciosos conocidos**. Estos son a menudo utilizados por bots y escáneres maliciosos para identificar sitios vulnerables.

=== "URI"
    **Qué hace esto:** Bloquea las solicitudes a URL específicas en su sitio. Esto es útil para bloquear intentos de acceso a páginas de administración, formularios de inicio de sesión u otras áreas sensibles que podrían ser objetivo de ataques.

    | Ajuste                      | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                         |
    | --------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
    | `BLACKLIST_URI`             |                   | multisite | no       | **Lista Negra de URI:** Lista de patrones de URI (expresión regular PCRE) a bloquear, separados por espacios.       |
    | `BLACKLIST_IGNORE_URI`      |                   | multisite | no       | **Lista de Omisión de URI:** Lista de patrones de URI que deben omitir las comprobaciones de la lista negra de URI. |
    | `BLACKLIST_URI_URLS`        |                   | multisite | no       | **URL de la Lista Negra de URI:** Lista de URL que contienen patrones de URI a bloquear, separadas por espacios.    |
    | `BLACKLIST_IGNORE_URI_URLS` |                   | multisite | no       | **URL de la Lista de Omisión de URI:** Lista de URL que contienen patrones de URI a omitir.                         |

!!! info "Soporte de Formato de URL"
    Todos los ajustes `*_URLS` admiten URL HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
    Las listas negras de las URL se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada contra las últimas amenazas.

### Configuraciones de Ejemplo

=== "Protección Básica de IP y User-Agent"

    Una configuración simple que bloquea los nodos de salida de Tor conocidos y los agentes de usuario maliciosos comunes usando listas negras de la comunidad:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_COMMUNITY_LISTS: "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents"
    ```

    Alternativamente, puede usar la configuración manual de URL:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Protección Avanzada con Reglas Personalizadas"

    Una configuración más completa con entradas de lista negra personalizadas y excepciones:

    ```yaml
    USE_BLACKLIST: "yes"

    # Entradas de lista negra personalizadas
    BLACKLIST_IP: "192.168.1.100 203.0.113.0/24"
    BLACKLIST_RDNS: ".shodan.io .censys.io .scanner.com"
    BLACKLIST_ASN: "16509 14618"  # ASN de AWS y Amazon
    BLACKLIST_USER_AGENT: "(?:\b)SemrushBot(?:\b) (?:\b)AhrefsBot(?:\b)"
    BLACKLIST_URI: "^/wp-login\.php$ ^/administrator/"

    # Reglas de omisión personalizadas
    BLACKLIST_IGNORE_IP: "192.168.1.200 203.0.113.42"

    # Fuentes de listas negras externas
    BLACKLIST_IP_URLS: "https://www.dan.me.uk/torlist/?exit https://www.spamhaus.org/drop/drop.txt"
    BLACKLIST_USER_AGENT_URLS: "https://raw.githubusercontent.com/mitchellkrogza/nginx-ultimate-bad-bot-blocker/master/_generator_lists/bad-user-agents.list"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas negras:

    ```yaml
    USE_BLACKLIST: "yes"
    BLACKLIST_IP_URLS: "file:///ruta/a/ip-blacklist.txt"
    BLACKLIST_RDNS_URLS: "file:///ruta/a/rdns-blacklist.txt"
    BLACKLIST_ASN_URLS: "file:///ruta/a/asn-blacklist.txt"
    BLACKLIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-blacklist.txt"
    BLACKLIST_URI_URLS: "file:///ruta/a/uri-blacklist.txt"
    ```

### Trabajar con archivos de listas locales

Las configuraciones `*_URLS` de los plugins de lista blanca, lista gris y lista negra utilizan el mismo descargador. Cuando referencia una URL `file:///`:

- La ruta se resuelve dentro del contenedor del **scheduler** (en despliegues Docker normalmente `bunkerweb-scheduler`). Monte los archivos allí y asegúrese de que el usuario del scheduler tenga permisos de lectura.
- Cada archivo es texto codificado en UTF-8 con una entrada por línea. Las líneas vacías se ignoran y las líneas de comentario deben comenzar con `#` o `;`. Los comentarios `//` no son compatibles.
- Valores esperados por tipo de lista:
  - **Listas IP** aceptan direcciones IPv4/IPv6 o redes CIDR (por ejemplo `192.0.2.10` o `2001:db8::/48`).
  - **Listas rDNS** esperan un sufijo sin espacios (por ejemplo `.search.msn.com`). Los valores se normalizan automáticamente a minúsculas.
  - **Listas ASN** pueden contener solo el número (`32934`) o el número con el prefijo `AS` (`AS15169`).
  - **Listas de User-Agent** se tratan como patrones PCRE y se conserva la línea completa (incluidos los espacios). Mantenga los comentarios en una línea separada para que no se interpreten como parte del patrón.
  - **Listas URI** deben comenzar con `/` y pueden usar tokens PCRE como `^` o `$`.

Ejemplos de archivos con el formato esperado:

```text
# /etc/bunkerweb/lists/ip-blacklist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-blacklist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
