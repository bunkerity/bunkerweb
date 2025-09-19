El complemento DNSBL (Domain Name System Blacklist) proporciona protección contra direcciones IP maliciosas conocidas al verificar las direcciones IP de los clientes contra servidores DNSBL externos. Esta función ayuda a proteger su sitio web contra el spam, las redes de bots y diversos tipos de ciberamenazas al aprovechar listas mantenidas por la comunidad de direcciones IP problemáticas.

**Cómo funciona:**

1.  Cuando un cliente se conecta a su sitio web, BunkerWeb consulta los servidores DNSBL que ha elegido utilizando el protocolo DNS.
2.  La verificación se realiza enviando una consulta de DNS inversa a cada servidor DNSBL con la dirección IP del cliente.
3.  Si algún servidor DNSBL confirma que la dirección IP del cliente está listada como maliciosa, BunkerWeb prohibirá automáticamente al cliente, evitando que amenazas potenciales lleguen a su aplicación.
4.  Los resultados se almacenan en caché para mejorar el rendimiento de los visitantes recurrentes de la misma dirección IP.
5.  Las búsquedas se realizan de manera eficiente utilizando consultas asíncronas para minimizar el impacto en los tiempos de carga de la página.

### Cómo usar

Siga estos pasos para configurar y usar la función DNSBL:

1.  **Habilite la función:** La función DNSBL está deshabilitada de forma predeterminada. Establezca la configuración `USE_DNSBL` en `yes` para habilitarla.
2.  **Configure los servidores DNSBL:** Agregue los nombres de dominio de los servicios DNSBL que desea usar a la configuración `DNSBL_LIST`.
3.  **Aplique la configuración:** Una vez configurado, BunkerWeb verificará automáticamente las conexiones entrantes contra los servidores DNSBL especificados.
4.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver las estadísticas de las solicitudes bloqueadas por las verificaciones de DNSBL.

### Ajustes de Configuración

**General**

| Ajuste       | Valor por defecto                                   | Contexto  | Múltiple | Descripción                                                                                                    |
| ------------ | --------------------------------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `USE_DNSBL`  | `no`                                                | multisite | no       | Habilitar DNSBL: establezca en `yes` para habilitar las verificaciones de DNSBL para las conexiones entrantes. |
| `DNSBL_LIST` | `bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org` | global    | no       | Servidores DNSBL: lista de dominios de servidores DNSBL para verificar, separados por espacios.                |

**Listas de Omisión**

| Ajuste                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                      |
| ---------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `DNSBL_IGNORE_IP`      | ``                | multisite | yes      | IPs/CIDRs separados por espacios para omitir las verificaciones de DNSBL (lista blanca).                         |
| `DNSBL_IGNORE_IP_URLS` | ``                | multisite | yes      | URL separadas por espacios que proporcionan IPs/CIDRs para omitir. Admite los esquemas `http(s)://` y `file://`. |

!!! tip "Elección de Servidores DNSBL"
Elija proveedores de DNSBL de buena reputación para minimizar los falsos positivos. La lista predeterminada incluye servicios bien establecidos que son adecuados para la mayoría de los sitios web:

    -   **bl.blocklist.de:** Lista las IP que han sido detectadas atacando otros servidores.
    -   **sbl.spamhaus.org:** Se centra en fuentes de spam y otras actividades maliciosas.
    -   **xbl.spamhaus.org:** Apunta a sistemas infectados, como máquinas comprometidas o proxies abiertos.

!!! info "Cómo Funciona DNSBL"
Los servidores DNSBL funcionan respondiendo a consultas DNS con formato especial. Cuando BunkerWeb verifica una dirección IP, invierte la IP y añade el nombre de dominio del DNSBL. Si la consulta DNS resultante devuelve una respuesta de "éxito", la IP se considera en la lista negra.

!!! warning "Consideraciones de Rendimiento"
Aunque BunkerWeb optimiza las búsquedas de DNSBL para el rendimiento, agregar un gran número de servidores DNSBL podría afectar potencialmente los tiempos de respuesta. Comience con unos pocos servidores DNSBL de buena reputación y supervise el rendimiento antes de agregar más.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple que utiliza los servidores DNSBL predeterminados:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "bl.blocklist.de sbl.spamhaus.org xbl.spamhaus.org"
    ```

=== "Configuración Mínima"

    Una configuración mínima que se centra en los servicios DNSBL más fiables:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    ```

    Esta configuración utiliza solo:

    -   **zen.spamhaus.org**: La lista combinada de Spamhaus a menudo se considera suficiente como una solución independiente debido a su amplia cobertura y reputación de precisión. Combina las listas SBL, XBL y PBL en una sola consulta, lo que la hace eficiente y completa.

=== "Excluyendo IPs de Confianza"

    Puede excluir clientes específicos de las verificaciones de DNSBL utilizando valores estáticos y/o archivos remotos:

    -   `DNSBL_IGNORE_IP`: Agregue IPs y rangos CIDR separados por espacios. Ejemplo: `192.0.2.10 203.0.113.0/24 2001:db8::/32`.
    -   `DNSBL_IGNORE_IP_URLS`: Proporcione URL cuyo contenido liste una IP/CIDR por línea. Los comentarios que comienzan con `#` o `;` se ignoran. Las entradas duplicadas se eliminan.

    Cuando la IP de un cliente entrante coincide con la lista de omisión, BunkerWeb omite las búsquedas de DNSBL y almacena en caché el resultado como "ok" para solicitudes posteriores más rápidas.

=== "Usando URL Remotas"

    El trabajo `dnsbl-download` descarga y almacena en caché las IPs a omitir cada hora:

    -   Protocolos: `https://`, `http://` y rutas locales `file://`.
    -   La caché por URL con suma de verificación evita descargas redundantes (período de gracia de 1 hora).
    -   Archivo combinado por servicio: `/var/cache/bunkerweb/dnsbl/<service>/IGNORE_IP.list`.
    -   Se carga al inicio y se combina con `DNSBL_IGNORE_IP`.

Ejemplo que combina fuentes estáticas y de URL:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP: "10.0.0.0/8 192.168.0.0/16 2001:db8::/32"
    DNSBL_IGNORE_IP_URLS: "https://example.com/allow-cidrs.txt file:///etc/bunkerweb/dnsbl/ignore.txt"
    ```

=== "Usando Archivos Locales"

    Cargue las IPs a omitir desde archivos locales usando URL `file://`:

    ```yaml
    USE_DNSBL: "yes"
    DNSBL_LIST: "zen.spamhaus.org"
    DNSBL_IGNORE_IP_URLS: "file:///etc/bunkerweb/dnsbl/ignore.txt file:///opt/data/allow-cidrs.txt"
    ```
