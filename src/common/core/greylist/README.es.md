El complemento de Lista Gris proporciona un enfoque de seguridad flexible que permite el acceso de los visitantes mientras se mantienen las características de seguridad esenciales.

A diferencia de los enfoques tradicionales de [lista negra](#blacklist)/[lista blanca](#whitelist) —que bloquean o permiten completamente el acceso—, la lista gris crea un punto intermedio al conceder acceso a ciertos visitantes mientras los somete a controles de seguridad.

**Cómo funciona:**

1.  Usted define los criterios para que los visitantes sean incluidos en la lista gris (_direcciones IP, redes, DNS inverso, ASN, User-Agent o patrones de URI_).
2.  Cuando un visitante coincide con cualquiera de estos criterios, se le concede acceso a su sitio mientras las demás características de seguridad permanecen activas.
3.  Si un visitante no coincide con ningún criterio de la lista gris, se le deniega el acceso.
4.  Los datos de la lista gris se pueden actualizar automáticamente desde fuentes externas de forma programada.

### Cómo usar

Siga estos pasos para configurar y usar la función de Lista Gris:

1.  **Habilite la función:** La función de Lista Gris está desactivada por defecto. Establezca el ajuste `USE_GREYLIST` en `yes` para habilitarla.
2.  **Configure las reglas de la lista gris:** Defina qué IPs, redes, patrones de DNS inverso, ASNs, User-Agents o URIs deben incluirse en la lista gris.
3.  **Añada fuentes externas:** Opcionalmente, configure URLs para descargar y actualizar automáticamente los datos de la lista gris.
4.  **Supervise el acceso:** Revise la [interfaz de usuario web](web-ui.md) para ver qué visitantes están siendo permitidos o denegados.

!!! tip "Comportamiento del Control de Acceso"
    Cuando la función de lista gris está habilitada con el ajuste `USE_GREYLIST` establecido en `yes`:

    1.  **Visitantes en la lista gris:** Se les permite el acceso pero siguen estando sujetos a todos los controles de seguridad.
    2.  **Visitantes no incluidos en la lista gris:** Se les deniega completamente el acceso.

!!! info "modo stream"
    Cuando se utiliza el modo stream, solo se realizan las comprobaciones de IP, DNS inverso y ASN.

### Ajustes de Configuración

**General**

| Ajuste         | Valor por defecto | Contexto  | Múltiple | Descripción                                                                 |
| -------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------- |
| `USE_GREYLIST` | `no`              | multisite | no       | **Habilitar Lista Gris:** Establezca en `yes` para habilitar la lista gris. |

=== "Dirección IP"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según su dirección IP o red. Estos visitantes obtienen acceso pero siguen estando sujetos a los controles de seguridad.

    | Ajuste             | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                             |
    | ------------------ | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_IP`      |                   | multisite | no       | **Lista Gris de IP:** Lista de direcciones IP o redes (en notación CIDR) para incluir en la lista gris, separadas por espacios.         |
    | `GREYLIST_IP_URLS` |                   | multisite | no       | **URLs de Lista Gris de IP:** Lista de URLs que contienen direcciones IP o redes para incluir en la lista gris, separadas por espacios. |

=== "DNS Inverso"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según su nombre de dominio (en inverso). Útil para permitir el acceso condicional a visitantes de organizaciones o redes específicas.

    | Ajuste                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                               |
    | ---------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_RDNS`        |                   | multisite | no       | **Lista Gris de rDNS:** Lista de sufijos de DNS inverso para incluir en la lista gris, separados por espacios.                            |
    | `GREYLIST_RDNS_GLOBAL` | `yes`             | multisite | no       | **Solo rDNS Global:** Realiza comprobaciones de la lista gris de rDNS solo en direcciones IP globales cuando se establece en `yes`.       |
    | `GREYLIST_RDNS_URLS`   |                   | multisite | no       | **URLs de Lista Gris de rDNS:** Lista de URLs que contienen sufijos de DNS inverso para incluir en la lista gris, separadas por espacios. |

    !!! info "DNS inverso confirmado hacia delante (FCrDNS)"
        Los sufijos de `GREYLIST_RDNS` se confirman hacia delante: el nombre de host PTR coincidente se resuelve de nuevo a una IP y la concesión de la lista gris solo se aplica cuando coincide con la IP del cliente. Un PTR que no se puede confirmar hacia delante se trata como una posible suplantación y no se concede el acceso. Esto evita que un atacante que controle su propio registro PTR lo establezca en un sufijo incluido en la lista gris para obtener acceso.

=== "ASN"
    **Qué hace esto:** Incluye en la lista gris a los visitantes de proveedores de red específicos utilizando Números de Sistema Autónomo. Los ASN identifican a qué proveedor u organización pertenece una IP.

    | Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                            |
    | ------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_ASN`      |                   | multisite | no       | **Lista Gris de ASN:** Lista de Números de Sistema Autónomo para incluir en la lista gris, separados por espacios.     |
    | `GREYLIST_ASN_URLS` |                   | multisite | no       | **URLs de Lista Gris de ASN:** Lista de URLs que contienen ASNs para incluir en la lista gris, separadas por espacios. |

=== "User Agent"
    **Qué hace esto:** Incluye en la lista gris a los visitantes según el navegador o la herramienta que dicen estar usando. Esto permite el acceso controlado para herramientas específicas mientras se mantienen los controles de seguridad.

    | Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                   |
    | -------------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_USER_AGENT`      |                   | multisite | no       | **Lista Gris de User-Agent:** Lista de patrones de User-Agent (expresión regular PCRE) para incluir en la lista gris, separados por espacios. |
    | `GREYLIST_USER_AGENT_URLS` |                   | multisite | no       | **URLs de Lista Gris de User-Agent:** Lista de URLs que contienen patrones de User-Agent para incluir en la lista gris.                       |

=== "URI"
    **Qué hace esto:** Incluye en la lista gris las solicitudes a URLs específicas de su sitio. Esto permite el acceso condicional a ciertos puntos finales mientras se mantienen los controles de seguridad.

    | Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                       |
    | ------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_URI`      |                   | multisite | no       | **Lista Gris de URI:** Lista de patrones de URI (expresión regular PCRE) para incluir en la lista gris, separados por espacios.   |
    | `GREYLIST_URI_URLS` |                   | multisite | no       | **URLs de Lista Gris de URI:** Lista de URLs que contienen patrones de URI para incluir en la lista gris, separadas por espacios. |

=== "Reglas compuestas (AND)"
    **Función:** exigir varios criterios *a la vez*. Las listas simples anteriores se combinan con
    OR: basta una coincidencia para incluir al visitante en la lista gris. Una regla es AND: solo coincide si se cumplen todos sus términos.

    | Ajuste | Predeterminado | Contexto | Múltiple | Descripción |
    | ------ | -------------- | -------- | -------- | ----------- |
    | `GREYLIST_RULE` | | multisite | sí | **Regla de lista:** Términos unidos por ` AND `; deben coincidir todos. |

    Los términos se separan con el literal ` AND `, en mayúsculas y con un espacio a cada lado:

    ```
    <rule> := <term> ( " AND " <term> )*
    <term> := [ "NOT " ] <kind> ":" <value>
    <kind> := ip | country | asn | rdns | ua | uri
    ```

    `user_agent` es un alias de `ua`. Un `<value>` puede ser un grupo como `@office`, resuelto
    según el tipo del término. Usa sufijos numéricos: `GREYLIST_RULE_1`, `GREYLIST_RULE_2`, etc.

    ```yaml
    USE_GREYLIST: "yes"
    # Crawler del socio, solo desde la red del socio
    GREYLIST_RULE_1: "ip:203.0.113.0/24 AND ua:^PartnerCrawler"
    # Un ASN, salvo sus escáneres
    GREYLIST_RULE_2: "asn:12345 AND NOT ua:(?:nmap|masscan)"
    # País y ruta, con un grupo de países
    GREYLIST_RULE_3: "country:@internal-markets AND uri:^/api/v1/"
    ```

    !!! warning "OR entre reglas, AND dentro de cada una"
        **Las reglas se combinan con OR**, entre sí y con las listas simples: coincidir con
        `GREYLIST_IP` o con cualquier regla basta para incluir al visitante en la lista gris. **Los términos de una regla
        se combinan con AND**: deben cumplirse todos. Dos criterios en reglas distintas son OR;
        los mismos dos como términos de una regla son AND.

    !!! info "Límites"
        - Un término cuyo dato no está disponible es **desconocido** y una regla que lo contenga
          nunca coincide; `NOT` no lo cambia. `ua:` y `uri:` siempre son desconocidos en stream;
          `ua:` también lo es sin cabecera `User-Agent`. Un fallo de consulta (base GeoIP ausente,
          error DNS) también es desconocido. Una IP privada **no** lo es: no tiene ASN y su país
          es `local`, por lo que `NOT asn:…` sí coincide legítimamente.
        - Una regla con `ua:` o `uri:` no coincide en un servicio stream. No se rechaza porque la
          misma configuración puede servir HTTP, pero al cargarla se registra una advertencia
          que identifica la regla para evitar que quede inactiva sin explicación.
        - Una regla formada solo por términos `NOT` es válida pero coincide con casi todas las
          peticiones. Produce la misma advertencia.
        - No hay sintaxis de escape. Como ` AND ` es el separador, una regex `ua:` o `uri:` no
          puede contener " and " con ninguna combinación de mayúsculas: se rechaza al guardar.
        - `rdns:` requiere confirmación directa, igual que `GREYLIST_RDNS`: se resuelve
          el hostname PTR coincidente y solo es verdadero si devuelve la IP del cliente.


=== "Cabecera"
    **Qué hace esto:** Pone en la lista gris las peticiones que llevan una cabecera concreta, comprobada por nombre y, opcionalmente, por una expresión regular PCRE sobre su valor.

    | Ajuste                  | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                   |
    | ----------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | `GREYLIST_HEADER_NAME`  |                   | multisite | sí       | **Nombre de cabecera:** Nombre de una cabecera de petición que hace que la petición incluirla en la lista gris. Pares numerados: `_NAME_1` va con `_VALUE_1`. |
    | `GREYLIST_HEADER_VALUE` |                   | multisite | sí       | **Valor de cabecera:** Expresión regular PCRE que debe coincidir con el valor de la cabecera. Déjelo vacío para comprobar solo su presencia.                  |

    !!! warning "Una regla de cabecera es un secreto compartido"
        Cualquier cliente puede enviar una cabecera, así que una regla de cabecera es un token portador, no un control de red. Sírvala solo por HTTPS, ancle la expresión regular con `^` y `$` (la búsqueda no está anclada por defecto, así que `abc` también coincide con `xabcx`) y rote el valor. Si BunkerWeb está detrás de un proxy, ese proxy debe sobrescribir cualquier copia de la cabecera enviada por el cliente. Estas reglas son solo para HTTP: un servicio de stream no lleva cabeceras de petición, así que allí no coincide nada.

!!! info "Soporte de Formato de URL"
    Todos los ajustes `*_URLS` admiten URLs HTTP/HTTPS así como rutas de archivos locales usando el prefijo `file:///`. Se admite la autenticación básica usando el formato `http://usuario:contraseña@url`.

!!! tip "Actualizaciones Regulares"
    Las listas grises de las URLs se descargan y actualizan automáticamente cada hora para asegurar que su protección se mantenga actualizada con las últimas fuentes de confianza.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que aplica la lista gris a la red interna y al rastreador de una empresa:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP: "192.168.1.0/24 10.0.0.0/8"
    GREYLIST_USER_AGENT: "(?:\b)CompanyCrawler(?:\b)"
    ```

=== "Configuración Avanzada"

    Una configuración más completa con múltiples criterios de lista gris:

    ```yaml
    USE_GREYLIST: "yes"

    # Activos de la empresa y rastreadores aprobados
    GREYLIST_IP: "192.168.1.0/24 203.0.113.0/24"
    GREYLIST_RDNS: ".company.com .partner-company.org"
    GREYLIST_ASN: "12345 67890"  # ASNs de la empresa y del socio
    GREYLIST_USER_AGENT: "(?:\b)GoodBot(?:\b) (?:\b)PartnerCrawler(?:\b)"
    GREYLIST_URI: "^/api/v1/"

    # Fuentes externas de confianza
    GREYLIST_IP_URLS: "https://example.com/trusted-networks.txt"
    GREYLIST_USER_AGENT_URLS: "https://example.com/trusted-crawlers.txt"
    ```

=== "Usando Archivos Locales"

    Configuración usando archivos locales para las listas grises:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_IP_URLS: "file:///ruta/a/ip-greylist.txt"
    GREYLIST_RDNS_URLS: "file:///ruta/a/rdns-greylist.txt"
    GREYLIST_ASN_URLS: "file:///ruta/a/asn-greylist.txt"
    GREYLIST_USER_AGENT_URLS: "file:///ruta/a/user-agent-greylist.txt"
    GREYLIST_URI_URLS: "file:///ruta/a/uri-greylist.txt"
    ```

=== "Acceso Selectivo a la API"

    Una configuración que permite el acceso a puntos finales específicos de la API:

    ```yaml
    USE_GREYLIST: "yes"
    GREYLIST_URI: "^/api/v1/public/ ^/api/v1/status"
    GREYLIST_IP: "203.0.113.0/24"  # Red del socio externo
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
# /etc/bunkerweb/lists/ip-greylist.txt
192.0.2.10
198.51.100.0/24

# /etc/bunkerweb/lists/ua-greylist.txt
(?:^|\s)FriendlyScanner(?:\s|$)
TrustedMonitor/\d+\.\d+
```
