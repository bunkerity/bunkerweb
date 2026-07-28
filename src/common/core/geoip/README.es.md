El complemento GeoIP administra las bases de datos en formato MaxMind (`.mmdb`) que BunkerWeb utiliza para determinar el **país**, el **ASN** y, opcionalmente, la **ciudad** de cada IP cliente. Estas consultas alimentan el complemento [Country](#country), las reglas ASN de las listas negra y gris, los informes mostrados en la [interfaz web](web-ui.md) y las variables de registro `$bw_country`, `$bw_asn_number`, `$bw_asn_org` y `$bw_city`.

No es necesario configurar nada de forma predeterminada: las bases de datos de países y ASN proceden de las ediciones gratuitas de [DB-IP Lite](https://db-ip.com/db/lite.php), actualizadas a diario. Solo necesita los ajustes de este complemento cuando quiera utilizar un **proveedor diferente**: una suscripción a MaxMind o una base de datos suministrada por usted.

**Cómo funciona:**

1. Tres tareas diarias actualizan las bases de datos de países, ASN y ciudades.
2. Cada tarea elige su fuente con una prioridad sencilla: primero su propio archivo, después MaxMind y por último DB-IP.
3. El archivo descargado se descomprime, se abre y se comprueba que corresponda al tipo de base de datos solicitado.
4. Si difiere de la copia en caché, se almacena y se distribuye a todas las instancias de BunkerWeb, que se recargan para utilizarlo.
5. Una consulta fallida nunca bloquea una solicitud: el país pasa a ser `unknown` y el tráfico se atiende con normalidad.

### Prioridad de las fuentes

No existe un ajuste de «fuente» que seleccionar. La prioridad depende simplemente de los ajustes que haya rellenado:

| Prioridad | Se utiliza cuando                             | Fuente                                                     |
| --------- | --------------------------------------------- | ---------------------------------------------------------- |
| 1         | `GEOIP_<KIND>_MMDB` está definido             | Su propio archivo o URL                                    |
| 2         | `MAXMIND_LICENSE_KEY` está definido            | MaxMind (GeoLite2 gratuito o su suscripción a GeoIP2)      |
| 3         | No hay nada definido                           | DB-IP Lite (predeterminado)                                |

Definir `MAXMIND_LICENSE_KEY` cambia las **tres** bases de datos a MaxMind. No se pueden mezclar proveedores por base de datos; utilice `GEOIP_<KIND>_MMDB` si necesita que una base concreta proceda de otra fuente.

### Ajustes de configuración

| Ajuste                   | Predeterminado | Contexto | Múltiple | Descripción                                                                                                                                                                       |
| ------------------------ | -------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAXMIND_LICENSE_KEY`    |                | global   | no       | **Clave de licencia de MaxMind:** cuando se define, las bases de países, ASN y ciudades se descargan de MaxMind en lugar de DB-IP.                                                 |
| `MAXMIND_ACCOUNT_ID`     |                | global   | no       | **ID de cuenta de MaxMind:** opcional, pero recomendado; sin él se utiliza el endpoint obsoleto que solo emplea la clave y la incluye en la URL.                                   |
| `GEOIP_CITY`             | `no`           | global   | no       | **Base de datos de ciudades:** descarga la base de ciudades. Es mucho mayor que las demás (125 MB descomprimida) y no se incluye en las imágenes.                                  |
| `GEOIP_COUNTRY_MMDB`     |                | global   | no       | **Base de países personalizada:** ruta absoluta legible por el worker o URL `http(s)`. Tiene prioridad sobre MaxMind y DB-IP.                                                      |
| `GEOIP_ASN_MMDB`         |                | global   | no       | **Base ASN personalizada:** ruta absoluta legible por el worker o URL `http(s)`. Tiene prioridad sobre MaxMind y DB-IP.                                                           |
| `GEOIP_CITY_MMDB`        |                | global   | no       | **Base de ciudades personalizada:** ruta absoluta legible por el worker o URL `http(s)`. Tiene prioridad sobre MaxMind y DB-IP.                                                   |

!!! warning "La base de datos de ciudades es grande"
    DB-IP City Lite es una **descarga de 59 MB que ocupa 125 MB descomprimida**, frente a 7.8 MB para países y 9.2 MB para ASN. A diferencia de esas dos, **no se incluye en las imágenes**: no habrá datos disponibles hasta la primera descarga correcta y una descarga fallida simplemente dejará `$bw_city` vacío.

    Como las cachés de las tareas se almacenan en la base de datos y se distribuyen a todas las instancias, activarla tiene consecuencias reales:

    - En MariaDB y MySQL, aumente `max_allowed_packet` por encima de 125 MB o la tarea fallará (el valor predeterminado es 64 MB). La tarea lo indica expresamente en sus registros cuando ocurre.
    - El worker mantiene la base de datos en memoria mientras la almacena, así que aumente `WORKER_MAX_MEMORY_KB` y el límite de memoria del contenedor del worker según corresponda.
    - Cada cambio de configuración vuelve a distribuir la caché a todas las instancias, así que tenga en cuenta el ancho de banda y el espacio en disco.

    `GeoLite2-City` de MaxMind es notablemente más pequeña si dispone de una clave de licencia.

!!! info "Obtener una clave de licencia de MaxMind"
    Cree una cuenta gratuita en [maxmind.com](https://www.maxmind.com/en/geolite2/signup), genere una clave de licencia **y** anote su ID de cuenta. Ambos aparecen en el portal de la cuenta. GeoLite2 se actualiza dos veces por semana, frente a una vez al mes para DB-IP Lite.

    Una clave recién creada puede tardar unos instantes en activarse; hasta entonces, las descargas fallarán con `401`.

!!! warning "Proporcione el ID de cuenta, no solo la clave"
    El ID de cuenta solo es opcional por compatibilidad con versiones anteriores. Prescindir de él es peor por dos razones:

    - El endpoint de MaxMind que solo utiliza la clave está **obsoleto** y puede retirarse.
    - Incluye su clave de licencia **en la cadena de consulta de la URL**, donde aparece en los registros de acceso de cualquier proxy de reenvío que haya en la ruta. Con un ID de cuenta, las credenciales se transmiten en una cabecera `Authorization`.

    BunkerWeb elimina la clave de sus propios registros en ambos casos, incluidos los mensajes de error de descarga, pero no puede eliminarla de registros de terceros.

!!! info "Utilizar su propia base de datos"
    Cualquier archivo `.mmdb` en formato MaxMind funciona, incluidas las ediciones comerciales de GeoIP2 y las bases de datos internas, siempre que utilice los nombres de campo estándar (`country.iso_code`, `autonomous_system_number`, `autonomous_system_organization`, `city.names.en`).

    Una ruta local debe ser legible por el **worker**, no por las instancias de BunkerWeb: el worker la lee una vez y la distribuye. Se aceptan archivos `.mmdb`, `.mmdb.gz` y `.tar.gz`.

    El archivo se abre y se comprueba su tipo **antes** de almacenarlo o enviarlo. Por tanto, si un ajuste apunta al tipo de base de datos equivocado —o a algo que ni siquiera es una base de datos—, se produce un error explícito en lugar de no devolver nada silenciosamente.

    Utilice preferentemente `https` para las URL. La geolocalización interviene en las decisiones de permitir y bloquear; una base de datos sustituida durante la transferencia puede hacer que el tráfico parezca proceder de un país permitido.

### Ejemplos de configuración

=== "Predeterminado (DB-IP)"

    No hay nada que configurar. Los países y ASN se actualizan a diario desde DB-IP Lite:

    ```yaml
    # no settings needed
    ```

=== "MaxMind GeoLite2"

    Cambie todas las bases de datos a MaxMind:

    ```yaml
    MAXMIND_ACCOUNT_ID: "123456"
    MAXMIND_LICENSE_KEY: "your-license-key"
    ```

=== "Añadir datos de ciudades"

    Active la base de datos de ciudades además de las fuentes predeterminadas:

    ```yaml
    GEOIP_CITY: "yes"
    ```

=== "Base de datos propia"

    Utilice una base de datos comercial montada en el worker y mantenga DB-IP para el resto:

    ```yaml
    GEOIP_COUNTRY_MMDB: "/data/geoip/GeoIP2-Country.mmdb"
    ```

=== "Espejo interno"

    Obtenga todas las bases de datos de un espejo HTTP interno:

    ```yaml
    GEOIP_COUNTRY_MMDB: "https://mirror.example.com/geoip/country.mmdb"
    GEOIP_ASN_MMDB: "https://mirror.example.com/geoip/asn.mmdb"
    GEOIP_CITY: "yes"
    GEOIP_CITY_MMDB: "https://mirror.example.com/geoip/city.mmdb.gz"
    ```

### Licencias

- Las bases de datos **DB-IP Lite** se publican bajo la licencia [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) y requieren atribución a DB-IP.com.
- Las bases de datos **GeoLite2** están sujetas al acuerdo de licencia de usuario final de MaxMind, que acepta al crear su clave. BunkerWeb nunca las redistribuye: se descargan con sus propias credenciales, por lo que ninguna base de datos de MaxMind se incluye en las imágenes.
