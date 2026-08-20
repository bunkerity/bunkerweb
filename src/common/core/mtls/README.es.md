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
| `MTLS_FORWARD_CLIENT_HEADERS` | `yes`                | multisite | no       | **Reenviar cabeceras del cliente:** propaga los resultados de la verificación (`X-SSL-Client-*` con estado, DN, emisor, serie, huella y ventana de validez). Las cabeceras `X-SSL-*` enviadas por el cliente siempre se eliminan en la entrada, de modo que estos valores no se pueden falsificar. |
| `MTLS_CRL`                    |                      | multisite | no       | **Ruta de la CRL de clientes:** ruta opcional a una lista de revocación de certificados en formato PEM. Se aplica siempre que la verificación de certificados de cliente está activa; nunca se omite en silencio. |

!!! tip "Mantén los certificados actualizados"
    Guarde los paquetes de CA y las listas de revocación en un volumen montado que pueda leer la **instancia de BunkerWeb**: NGINX abre `MTLS_CA_CERTIFICATE` y `MTLS_CRL` por sí mismo y ningún job los distribuye, así que en un despliegue separado no basta con montarlos donde se ejecuta el Scheduler.

!!! warning "Paquete de CA obligatorio en modos estrictos"
    Cuando `MTLS_VERIFY_CLIENT` está en `on` u `optional`, el paquete de CA es obligatorio. Si `MTLS_CA_CERTIFICATE` está vacío, BunkerWeb rechaza el handshake TLS de ese sitio (`ssl_reject_handshake`) en lugar de servirlo sin verificar los certificados de cliente; el HTTP en claro sigue respondiendo, por lo que la renovación ACME `http-01` no se ve afectada. Si la ruta está definida pero el archivo falta o no es legible en la instancia, NGINX se niega a cargar la configuración: en una recarga se mantiene la anterior y en un arranque en frío la instancia no llega a levantar. Lo mismo vale para `MTLS_CRL`: una lista de revocación configurada se aplica y nunca se omite en silencio. Utilice `optional_no_ca` solo para diagnóstico porque debilita la autenticación. Un handshake rechazado **sí** queda registrado, como `handshake rejected`, en el log de errores de NGINX de la instancia de BunkerWeb (`ERROR_LOG`, `/var/log/bunkerweb/error.log` por defecto), no en el del Scheduler. Se escribe en el nivel `info` mientras que `LOG_LEVEL` es `notice` por defecto, así que ponga `LOG_LEVEL=info` para verlo.

!!! info "Certificado confiable y verificación"
    `ssl_client_certificate` y `ssl_trusted_certificate` son ambos almacenes de confianza para verificar certificados de cliente; la única diferencia es que el primero anuncia sus CA al cliente en el CertificateRequest y el segundo no. BunkerWeb apuntaba los dos al mismo archivo, así que el segundo no aportaba nada y se ha eliminado. Es además el almacén con el que se verifican las respuestas OCSP cuando `ssl_stapling` está habilitado, algo que BunkerWeb nunca habilita: dirigido al paquete de CA de *clientes* quedaba inerte, pero era una trampa y ya no está.

!!! info "Las cabeceras `X-SSL-*` entrantes siempre se eliminan"
    BunkerWeb elimina toda cabecera de petición `X-SSL-*` enviada por el cliente antes de que la petición llegue a su aplicación: en todos los sitios, esté o no habilitado mTLS, y por igual en HTTP/1.1, HTTP/2 y HTTP/3. Solo se reenvían los valores que BunkerWeb obtiene del handshake TLS verificado, y únicamente cuando `MTLS_FORWARD_CLIENT_HEADERS` es `yes`, así que un cliente no puede falsificar `X-SSL-Client-Verify: SUCCESS`. Su aplicación debe comprobar igualmente que `X-SSL-Client-Verify` valga `SUCCESS`: con `MTLS_VERIFY_CLIENT=optional` también se reenvía una petición anónima, con `X-SSL-Client-Verify: NONE` y un `X-SSL-Client-DN` vacío, de modo que tratar el DN como prueba de autenticación la aceptaría.

    Si BunkerWeb está detrás de otro proxy que termina mTLS e inyecta estas cabeceras por su cuenta, capture el valor antes de la eliminación y vuelva a publicarlo. Añada una configuración personalizada `server-http`:

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    y luego reenvíelo con `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"`. `REVERSE_PROXY_HEADERS` por sí solo no funciona: `$http_x_ssl_client_verify` ya está vacío cuando `proxy_set_header` lo evalúa, mientras que `set` se ejecuta en la fase server-rewrite, antes de la eliminación.

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
