El plugin Mutual TLS (mTLS) protege las aplicaciones sensibles exigiendo que los clientes presenten certificados emitidos por autoridades en las que confía. Con la función activada, BunkerWeb autentica cada llamada antes de que llegue a sus servicios, lo que mantiene blindadas herramientas internas e integraciones con socios.

BunkerWeb evalúa cada handshake TLS con base en el paquete de CA y en la política que configure. Los clientes que no cumplen las reglas se bloquean, mientras que las conexiones válidas pueden reenviar los detalles del certificado a las aplicaciones de backend para aplicar autorizaciones más precisas.

**Cómo funciona:**

1. El plugin vigila los handshakes HTTPS del sitio seleccionado.
2. Durante el intercambio TLS, BunkerWeb inspecciona el certificado del cliente y verifica la cadena con su almacén de confianza.
3. El modo de verificación decide si los clientes no autenticados se rechazan, se aceptan con tolerancia o se habilitan solo para diagnósticos.
4. (Opcional) BunkerWeb expone el resultado por medio de las cabeceras `X-SSL-Client-*` para que sus aplicaciones apliquen su propia lógica de acceso.

!!! success "Beneficios clave"

      1. **Control perimetral sólido:** Solo las máquinas y usuarios autenticados alcanzan las rutas críticas.
      2. **Políticas flexibles:** Combine modos estrictos y opcionales según sus flujos de incorporación.
      3. **Visibilidad para las apps:** Reenvíe huellas e identidades de certificados a los servicios posteriores.
      4. **Seguridad en capas:** Refuerce mTLS con otros plugins de BunkerWeb como limitación de tasas o listas de control.

### Cómo utilizarlo

Siga estos pasos para desplegar Mutual TLS con confianza:

1. **Active la función:** Establezca `USE_MTLS` en `yes` en los sitios que necesitan autenticación por certificado.
2. **Aporte el paquete de CA:** Guarde los emisores de confianza en un archivo PEM y apunte `MTLS_CA_CERTIFICATE` a su ruta absoluta.
3. **Elija el modo de verificación:** Use `on` para exigir certificados, `optional` para permitir una ruta alternativa u `optional_no_ca` de manera temporal para diagnosticar.
4. **Ajuste la profundidad de la cadena:** Modifique `MTLS_VERIFY_DEPTH` si su PKI incorpora varios intermedios.
5. **Reenvíe resultados (opcional):** Mantenga `MTLS_FORWARD_CLIENT_HEADERS` en `yes` si los servicios posteriores necesitan inspeccionar el certificado.
6. **Mantenga la revocación:** Si publica una CRL, configure `MTLS_CRL` para que BunkerWeb rechace certificados revocados.

### Parámetros de configuración

| Parámetro                     | Valor predeterminado | Contexto | Múltiple | Descripción                                                                                                                                             |
| ----------------------------- | -------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                    | `no`                 | multisite | no       | **Usar mutual TLS:** habilita la autenticación mediante certificados de cliente para el sitio actual.                                                   |
| `MTLS_CA_CERTIFICATE`         |                      | multisite | no       | **Paquete de CA de clientes:** ruta absoluta al paquete de CA de confianza (PEM). Obligatorio cuando `MTLS_VERIFY_CLIENT` es `on` u `optional`; debe ser legible. |
| `MTLS_VERIFY_CLIENT`          | `on`                 | multisite | no       | **Modo de verificación:** elija si los certificados son obligatorios (`on`), opcionales (`optional`) o aceptados sin validación de CA (`optional_no_ca`). |
| `MTLS_URL`                    |                      | multisite | sí       | **URL mTLS:** expresión regular comparada con la URI de la solicitud para exigir un certificado de cliente válido solo en las rutas coincidentes (solo HTTP). Requiere que `MTLS_VERIFY_CLIENT` sea `optional` u `optional_no_ca`. Déjelo vacío para aplicar mTLS a todo el sitio. |
| `MTLS_VERIFY_DEPTH`           | `2`                  | multisite | no       | **Profundidad de verificación:** profundidad máxima de la cadena aceptada para los certificados de cliente.                                            |
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`                | multisite | no       | **Reenviar cabeceras del cliente:** propaga los resultados de la verificación (`X-SSL-Client-*` con estado, DN, emisor, serie, huella y ventana de validez). |
| `MTLS_CRL`                    |                      | multisite | no       | **Ruta de la CRL de clientes:** ruta opcional a una lista de revocación de certificados en formato PEM. Solo se aplica cuando el paquete de CA se carga correctamente. |

!!! tip "Mantén los certificados actualizados"
    Guarde los paquetes de CA y las listas de revocación en un volumen montado que el Scheduler pueda leer, de modo que cada reinicio recupere los últimos anclajes de confianza.

!!! warning "Paquete de CA obligatorio en modos estrictos"
    Cuando `MTLS_VERIFY_CLIENT` está en `on` u `optional`, el archivo de CA debe existir en tiempo de ejecución. Si falta, BunkerWeb omite las directivas de mTLS para evitar que el servicio arranque con una ruta no válida. Utilice `optional_no_ca` solo para diagnóstico porque debilita la autenticación.

!!! info "Certificado confiable y verificación"
    BunkerWeb reutiliza el mismo paquete de CA tanto para comprobar clientes como para construir la cadena de confianza, manteniendo coherentes las verificaciones de revocación y el handshake.

!!! warning "El mTLS por ruta requiere el modo opcional"
    La directiva `ssl_verify_client` de NGINX solo es válida en el contexto `server`: no puede colocarse dentro de un bloque `location`. Para exigir un certificado únicamente en algunas rutas, ponga `MTLS_VERIFY_CLIENT` en `optional` (u `optional_no_ca`) para que el handshake se complete en todas las rutas, y luego liste las rutas protegidas en `MTLS_URL_n`. BunkerWeb aplica entonces el certificado por solicitud, en Lua, sobre las URL coincidentes. Si deja `MTLS_VERIFY_CLIENT` en `on` mientras define `MTLS_URL_n`, NGINX rechaza a los clientes sin certificado durante el handshake, antes de que se aplique la lógica por ruta, por lo que la exigencia sigue siendo para todo el sitio.

!!! info "Solicitudes de certificado del navegador en modo opcional"
    El handshake TLS ocurre antes de que NGINX conozca la URL solicitada, así que en modo `optional` NGINX sigue enviando un `CertificateRequest` en cada conexión. La exigencia pasa a ser por ruta, pero la invitación a nivel de handshake no: los navegadores aún pueden pedir un certificado en rutas no protegidas (el comportamiento varía según el navegador). En esas rutas BunkerWeb permite la solicitud se presente o no un certificado.

### Ejemplos de configuración

=== "Control de acceso estricto"

    Exija certificados de cliente válidos emitidos por su CA privada y reenvíe la información de verificación al backend:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Autenticación de cliente opcional"

    Permita usuarios anónimos, pero reenvíe los detalles del certificado cuando un cliente presente uno:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnóstico sin CA"

    Permita que las conexiones finalicen incluso si un certificado no puede encadenarse con un paquete de CA de confianza. Úselo solo para la resolución de problemas:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "mTLS por ruta (p. ej. solo `/login`)"

    Exija certificados de cliente solo en ciertas rutas y mantenga abierto el resto del sitio. La verificación se ejecuta en modo `optional` para que el handshake se complete en las rutas no autenticadas; BunkerWeb aplica luego el certificado por solicitud en las URL que coincidan con `MTLS_URL_n` (una expresión regular por entrada):

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login"
    MTLS_URL_2: "^/admin"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Solicitud        | Certificado         | Resultado                               |
    | ---------------- | ------------------- | --------------------------------------- |
    | `GET /`          | ninguno             | Permitido (ruta sin mTLS)               |
    | `GET /login`     | ninguno             | Denegado (`403`)                        |
    | `GET /login`     | válido              | Permitido, `X-SSL-Client-*` reenviado   |
    | `GET /login`     | inválido / expirado | Denegado (`403`)                        |
