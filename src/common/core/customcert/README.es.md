El complemento de certificado SSL personalizado le permite usar sus propios certificados SSL/TLS con BunkerWeb en lugar de los generados automáticamente. Esta función es particularmente útil si tiene certificados existentes de una Autoridad de Certificación (CA) de confianza, necesita usar certificados con configuraciones específicas o desea mantener una gestión de certificados consistente en toda su infraestructura.

**Cómo funciona:**

1.  Usted proporciona a BunkerWeb sus archivos de certificado y clave privada, ya sea especificando las rutas de los archivos o proporcionando los datos en formato PEM codificado en base64 o en texto plano.
2.  BunkerWeb valida su certificado y clave para asegurarse de que estén formateados correctamente y sean utilizables.
3.  Cuando se establece una conexión segura, BunkerWeb sirve su certificado personalizado en lugar del generado automáticamente.
4.  BunkerWeb supervisa automáticamente la validez de su certificado y muestra advertencias si se acerca a su vencimiento.
5.  Usted tiene control total sobre la gestión de certificados, lo que le permite usar certificados de cualquier emisor que prefiera.

!!! info "Monitoreo Automático de Certificados"
    Cuando habilita SSL/TLS personalizado estableciendo `USE_CUSTOM_SSL` en `yes`, BunkerWeb monitorea automáticamente el certificado personalizado especificado en `CUSTOM_SSL_CERT`. Comprueba los cambios diariamente y recarga NGINX si se detecta alguna modificación, asegurando que el certificado más reciente esté siempre en uso.

### Cómo usar

Siga estos pasos para configurar y usar la función de certificado SSL personalizado:

1.  **Habilite la función:** Establezca el ajuste `USE_CUSTOM_SSL` en `yes` para habilitar el soporte de certificados personalizados.
2.  **Elija un método:** Decida si proporcionar los certificados a través de rutas de archivo o como datos codificados en base64/texto plano, y establezca la prioridad usando `CUSTOM_SSL_CERT_PRIORITY`.
3.  **Proporcione los archivos de certificado:** Si usa rutas de archivo, especifique las ubicaciones de sus archivos de certificado y clave privada.
4.  **O proporcione los datos del certificado:** Si usa datos, proporcione su certificado y clave como cadenas codificadas en base64 o en formato PEM de texto plano.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, BunkerWeb usa automáticamente sus certificados personalizados para todas las conexiones HTTPS.

!!! tip "Configuración en Modo Stream"
    Para el modo stream, debe configurar el ajuste `LISTEN_STREAM_PORT_SSL` para especificar el puerto de escucha SSL/TLS. Este paso es esencial para el correcto funcionamiento en modo stream.

### Ajustes de Configuración

| Ajuste                     | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                      |
| -------------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `USE_CUSTOM_SSL`           | `no`              | multisite | no       | **Habilitar SSL personalizado:** Establezca en `yes` para usar su propio certificado en lugar del generado automáticamente.      |
| `CUSTOM_SSL_CERT_PRIORITY` | `file`            | multisite | no       | **Prioridad del Certificado:** Elija si priorizar el certificado de la ruta del archivo o de los datos base64 (`file` o `data`). |
| `CUSTOM_SSL_CERT`          |                   | multisite | no       | **Ruta del Certificado:** Ruta completa a su archivo de certificado SSL o paquete de certificados.                               |
| `CUSTOM_SSL_KEY`           |                   | multisite | no       | **Ruta de la Clave Privada:** Ruta completa a su archivo de clave privada SSL.                                                   |
| `CUSTOM_SSL_CERT_DATA`     |                   | multisite | no       | **Datos del Certificado:** Su certificado codificado en formato base64 o como texto plano PEM.                                   |
| `CUSTOM_SSL_KEY_DATA`      |                   | multisite | no       | **Datos de la Clave Privada:** Su clave privada codificada en formato base64 o como texto plano PEM.                             |

### Certificado del servidor predeterminado

El **servidor predeterminado** es el bloque que responde a las solicitudes que no coinciden con ningún servicio configurado: un SNI desconocido, una conexión a una dirección IP en bruto, un `Host` que nadie sirve. El único certificado que podía presentar era el autofirmado interno que BunkerWeb genera al arrancar — por eso un navegador que llega a un hostname desconocido en tu instancia ve una advertencia de nombre no coincidente.

Estos cuatro ajustes globales lo sustituyen. Déjalos vacíos para conservar el certificado interno. Sus demás ajustes — TLS, cabeceras, páginas de error — se editan en el servicio reservado `default-server`, ver [Configuración del Servidor Predeterminado](#miscellaneous).

| Ajuste                          | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                       |
| ------------------------------ | ------- | ------- | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `DEFAULT_SERVER_SSL_CERT`      |         | global  | no       | **Ruta del Certificado del Servidor Predeterminado:** Ruta completa al certificado o paquete servido para solicitudes que no coinciden con ningún servicio configurado. Solo se sirve donde existe un bloque de servidor predeterminado: modo multisitio (`MULTISITE=yes`), o `DISABLE_DEFAULT_SERVER=yes` en modo de sitio único. |
| `DEFAULT_SERVER_SSL_KEY`       |         | global  | no       | **Ruta de la Clave del Servidor Predeterminado:** Ruta completa a la clave privada correspondiente.                                                              |
| `DEFAULT_SERVER_SSL_CERT_DATA` |         | global  | no       | **Datos del Certificado del Servidor Predeterminado:** El mismo certificado en base64 o texto plano PEM. Se usa solo cuando el ajuste de ruta está vacío. Solo se sirve donde existe un bloque de servidor predeterminado: modo multisitio (`MULTISITE=yes`), o `DISABLE_DEFAULT_SERVER=yes` en modo de sitio único. |
| `DEFAULT_SERVER_SSL_KEY_DATA`  |         | global  | no       | **Datos de la Clave del Servidor Predeterminado:** La misma clave privada en base64 o texto plano PEM. Se usa solo cuando el ajuste de ruta está vacío.          |

La anulación se consulta **en último lugar**, y solo dentro del servidor predeterminado: un servicio que resuelve su propio certificado — a través del inventario de certificados, `USE_CUSTOM_SSL`, Let's Encrypt o el proveedor autofirmado — siempre lo conserva.

!!! warning "Se rechaza un certificado que cubra alguno de tus servicios"
    El servidor predeterminado responde a *cualquier* hostname. Si su certificado también cubriera `www.example.com`, un cliente podría abrir una conexión con un SNI desconocido, recibir ese certificado, y luego reutilizar la misma conexión para `Host: www.example.com` — un certificado que ese servicio nunca autorizó, ahora utilizable para él (coalescencia de conexiones HTTP/2). Por eso el job `custom-cert` rechaza un certificado cuyos SAN o Common Name cubran algún hostname de cualquier servicio configurado, comodines incluidos, y registra el hostname por el que lo rechazó. Usa un certificado que no cubra ningún hostname de servicio configurado, o adjúntalo al servicio con `USE_CUSTOM_SSL` en su lugar.

!!! info "Un rechazo nunca retira lo que ya se está sirviendo"
    Un material inválido, un par que no coincide y un hostname cubierto hacen fallar el job de forma explícita y dejan en su sitio el certificado servido previamente, en vez de dejar al servidor predeterminado sin nada. La caducidad solo avisa, por la misma razón. Vaciar ambos ajustes elimina la anulación y restaura el certificado interno.

!!! tip "Inerte cuando el SNI estricto está activo"
    Con `DISABLE_DEFAULT_SERVER_STRICT_SNI` en `yes`, un SNI desconocido se cierra durante el handshake TLS, antes de elegir ningún certificado — así que la anulación nunca se alcanza. Déjalo desactivado si quieres que los hostnames desconocidos se respondan con tu propio certificado.

!!! warning "Consideraciones de Seguridad"
    Cuando use certificados personalizados, asegúrese de que su clave privada esté debidamente protegida y tenga los permisos adecuados. Los archivos deben ser legibles por el programador de BunkerWeb.

!!! tip "Formato del Certificado"
    BunkerWeb espera los certificados en formato PEM. Si su certificado está en un formato diferente, es posible que necesite convertirlo primero.

!!! info "Cadenas de Certificados"
    Si su certificado incluye una cadena (intermediarios), debe proporcionar la cadena de certificados completa en el orden correcto, con su certificado primero, seguido de los certificados intermedios.

### Configuraciones de Ejemplo

=== "Usando Rutas de Archivo"

    Una configuración que usa archivos de certificado y clave en el disco:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/ruta/a/su/certificado.pem"
    CUSTOM_SSL_KEY: "/ruta/a/su/clave-privada.pem"
    ```

=== "Usando Datos Base64"

    Una configuración que usa datos de certificado y clave codificados en base64:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...certificado codificado en base64...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...clave codificada en base64...Cg=="
    ```

=== "Usando Datos PEM de Texto Plano"

    Una configuración que usa datos de certificado y clave en texto plano en formato PEM:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "data"
    CUSTOM_SSL_CERT_DATA: |
      -----BEGIN CERTIFICATE-----
      MIIDdzCCAl+gAwIBAgIUJH...contenido del certificado...AAAA
      -----END CERTIFICATE-----
    CUSTOM_SSL_KEY_DATA: |
      -----BEGIN PRIVATE KEY-----
      MIIEvQIBADAN...contenido de la clave...AAAA
      -----END PRIVATE KEY-----
    ```

=== "Configuración de Respaldo"

    Una configuración que prioriza los archivos pero recurre a los datos base64 si los archivos no están disponibles:

    ```yaml
    USE_CUSTOM_SSL: "yes"
    CUSTOM_SSL_CERT_PRIORITY: "file"
    CUSTOM_SSL_CERT: "/ruta/a/su/certificado.pem"
    CUSTOM_SSL_KEY: "/ruta/a/su/clave-privada.pem"
    CUSTOM_SSL_CERT_DATA: "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUR...certificado codificado en base64...Cg=="
    CUSTOM_SSL_KEY_DATA: "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSEV...clave codificada en base64...Cg=="
    ```
