El plugin Mutual TLS (mTLS) protege las aplicaciones sensibles exigiendo que los clientes presenten certificados emitidos por autoridades en las que confía. Con la función activada, BunkerWeb autentica cada llamada antes de que llegue a sus servicios, lo que mantiene blindadas herramientas internas e integraciones con socios.

BunkerWeb evalúa cada handshake TLS con base en el paquete de CA y en la política que configure. Los clientes que no cumplen las reglas se bloquean, mientras que las conexiones válidas pueden reenviar los detalles del certificado a las aplicaciones de backend para aplicar autorizaciones más precisas.

**Cómo funciona:**

1. El plugin vigila los handshakes HTTPS del sitio seleccionado.
2. Durante el intercambio TLS, BunkerWeb inspecciona el certificado del cliente y verifica la cadena con su almacén de confianza.
3. El modo de verificación decide si los clientes no autenticados se rechazan, se dejan pasar o se habilitan solo para diagnósticos. Consulte más abajo "Qué protege cada modo".
4. (Opcional) BunkerWeb expone el resultado por medio de las cabeceras `X-SSL-Client-*` para que sus aplicaciones apliquen su propia lógica de acceso.

!!! success "Beneficios clave"

      1. **Control perimetral sólido:** Solo las máquinas y usuarios autenticados alcanzan las rutas críticas.
      2. **Políticas flexibles:** Combine modos estrictos y opcionales según sus flujos de incorporación.
      3. **Visibilidad para las apps:** Reenvíe huellas e identidades de certificados a los servicios posteriores.
      4. **Seguridad en capas:** Refuerce mTLS con otros plugins de BunkerWeb como limitación de tasas o listas de control.

### Cómo utilizarlo

Siga estos pasos para desplegar Mutual TLS con confianza:

1. **Active la función:** Establezca `USE_MTLS` en `yes` en los sitios que necesitan autenticación por certificado.
2. **Aporte el paquete de CA:** Configure `MTLS_CA_CERTIFICATE` con la ruta a un archivo PEM legible por el Scheduler, o proporcione el paquete directamente como datos base64/PEM con `MTLS_CA_CERTIFICATE_DATA`. El Scheduler valida, almacena en caché y distribuye el paquete a cada instancia, por lo que no es necesario montarlo en cada una.
3. **Elija el modo de verificación:** Use `on` para exigir certificados, `optional` para dejar pasar a los clientes sin certificado (y exigir uno solo en las rutas listadas en `MTLS_URL`) u `optional_no_ca` de manera temporal para diagnosticar.
4. **Ajuste la profundidad de la cadena:** Modifique `MTLS_VERIFY_DEPTH` si su PKI incorpora varios intermedios.
5. **Reenvíe resultados (opcional):** Mantenga `MTLS_FORWARD_CLIENT_HEADERS` en `yes` si los servicios posteriores necesitan inspeccionar el certificado.
6. **Mantenga la revocación:** Si publica una CRL, configure `MTLS_CRL` (o `MTLS_CRL_DATA`) para que BunkerWeb rechace los certificados revocados.
7. **Elija qué hace HTTP sin cifrar:** `MTLS_HTTP_POLICY` (`redirect` por defecto) decide qué ocurre con las solicitudes HTTP sin cifrar que mTLS debería haber protegido.
8. **Decida si los fallos de certificado cuentan para los bloqueos (opcional):** `MTLS_COUNT_BAD_BEHAVIOR` (`no` por defecto) permite que Bad Behavior los cuente.

El Scheduler valida el paquete de CA candidato completo y todas las CRL antes de sustituir cualquiera de los archivos en caché. Una CRL se rechaza si no se puede analizar, o si su emisor forma parte del paquete y la firma no se verifica contra él; una CRL firmada por una CA ausente del paquete se publica con una advertencia, porque NGINX construye la cadena con los intermedios que presenta el cliente. Si los datos no se pueden leer, son inválidos o no coinciden, conserva el par CA/CRL anterior y registra un error. Rote la CA y su CRL juntas y corrija los orígenes inválidos cuanto antes, especialmente antes de que caduque una CRL. Vaciar tanto `MTLS_CRL` como `MTLS_CRL_DATA` elimina deliberadamente la comprobación de revocaciones. Eliminar la configuración de CA, desactivar mTLS o eliminar el servicio borra sus archivos en caché; mientras `USE_MTLS` siga en `yes` con un modo distinto de `optional_no_ca`, `ssl_verify_client` se aplica entonces contra una CA de marcador de posición integrada: con `on` cada cliente recibe un 400 y con `optional` lo recibe cada cliente que presente un certificado, hasta que se configure de nuevo una CA. Las eliminaciones efectivas solicitan una recarga.

El job `client-cert` se ejecuta cada hora, de modo que un paquete de CA o un archivo de CRL que sustituya en disco se recoge en una hora. Registra un error para una CRL caducada (se rechaza a todos los clientes de la CA que la firmó hasta que se publique una CRL nueva) y para un certificado de CA caducado. Registra una advertencia para una CRL que caduca en 7 días, para un certificado de CA que caduca en 30 días, para un certificado del paquete que no es una CA y, en cuanto hay al menos una CRL configurada, para cada CA del paquete que no tiene CRL. La advertencia por CRL ausente nombra a cada CA sin CRL: toda CA que emite un certificado de la cadena, la CA raíz incluida, debe tener su CRL en el conjunto, o se rechaza a los clientes cuya cadena incluye un certificado emitido por ella. En todos estos casos el job publica el material igualmente: NGINX rechaza de todos modos a los clientes afectados, y conservar material anterior no sería mejor.

### Qué protege cada modo

"Llega a su backend" significa que la solicitud se reenvía al servicio una vez que los demás plugins de BunkerWeb también la han aceptado.

- **`on`:** cada solicitud HTTPS necesita un certificado que se valide contra el paquete de CA. Una solicitud sin certificado o con un certificado inválido recibe un `400` de NGINX y nunca llega a su backend. El HTTP sin cifrar sigue `MTLS_HTTP_POLICY`, en todas las rutas.
- **`optional` sin `MTLS_URL`:** no aplica nada por sí mismo. Un cliente sin certificado llega a su backend, tanto por HTTPS como por HTTP sin cifrar. Un cliente que presenta un certificado inválido sigue siendo rechazado (`400`) en HTTPS. Úselo cuando su aplicación lea las cabeceras `X-SSL-Client-*` reenviadas y decida por sí misma.
- **`optional` con `MTLS_URL`:** solo las rutas que coinciden con una regla necesitan un certificado válido. En HTTPS un cliente sin certificado recibe un `403` en esas rutas. En HTTP sin cifrar esas rutas siguen `MTLS_HTTP_POLICY`. Cualquier otra ruta llega a su backend con o sin certificado, por HTTPS y por HTTP. Un cliente que presenta un certificado inválido es rechazado (`400`) en todas las rutas.
- **`optional_no_ca`:** para diagnóstico, no para proteger. NGINX pide un certificado y tolera los errores de la cadena de confianza (certificado autofirmado, emisor desconocido, cadena no confiable), de modo que un cliente que ninguna CA avala completa igualmente el handshake. Cualquier otro error de verificación sigue rechazando al cliente con un `400` por HTTPS, por ejemplo un certificado caducado o revocado. Sin `MTLS_URL` no aplica nada. Con `MTLS_URL`, las rutas coincidentes siguen necesitando un certificado que se valide contra un paquete de CA, y si no hay ningún paquete de CA configurado nada se puede validar, de modo que esas rutas deniegan a todos los clientes.

Con `SECURITY_MODE=detect`, las denegaciones y redirecciones que emite BunkerWeb (regla por ruta, política para HTTP sin cifrar, regla `MTLS_URL` inválida) solo se registran y no se aplican, y la solicitud continúa hacia el siguiente plugin. La comprobación a nivel de handshake de `on` y `optional` la hace NGINX y el modo de seguridad no la afecta.

### Solicitudes HTTP sin cifrar

Un certificado de cliente solo viaja dentro de TLS, así que la comprobación del handshake no puede proteger el HTTP sin cifrar. Para un servicio con `USE_MTLS` en `yes`, `MTLS_HTTP_POLICY` decide qué ocurre con una solicitud HTTP sin cifrar que mTLS debería haber protegido: todas las rutas cuando `MTLS_VERIFY_CLIENT` es `on`, y en caso contrario las rutas de `MTLS_URL`. Con `optional` u `optional_no_ca` sin `MTLS_URL`, mTLS no protege nada en HTTPS, y por tanto tampoco en HTTP.

- `redirect` (por defecto): el cliente recibe un `301` a la misma URL por HTTPS. Una solicitud sin una cabecera `Host` utilizable se deniega en su lugar. Conserva el puerto de la cabecera `Host`, como la redirección del plugin SSL: donde los puertos HTTP y HTTPS difieren y no son el par estándar 80/443, el cliente se redirige por HTTPS al número del puerto HTTP. Use allí `MTLS_HTTP_POLICY=deny` o redirija delante de BunkerWeb.
- `deny`: la solicitud se rechaza con el estado de denegación (`DENY_HTTP_STATUS`, `403` por defecto).
- `allow`: el HTTP sin cifrar se sirve como antes cuando `MTLS_VERIFY_CLIENT` es `on`. Las rutas de `MTLS_URL` siguen denegadas.

Una redirección a HTTPS que ya emite el plugin SSL (`REDIRECT_HTTP_TO_HTTPS`, o `AUTO_REDIRECT_HTTP_TO_HTTPS` cuando detecta HTTPS) va primero, así que la política solo ve las solicitudes HTTP sin cifrar que esa redirección deja pasar. Los desafíos ACME HTTP-01 siguen siendo accesibles: un `GET` o `HEAD` HTTP sin cifrar sobre `/.well-known/acme-challenge/<token>` no se toca cuando un solver es su propietario, es decir, el solver local de Let's Encrypt con el token presente, o `LETS_ENCRYPT_PASSTHROUGH` o `ACME_PASSTHROUGH` en `yes`. Cualquier otra ruta bajo `/.well-known/acme-challenge/` sigue la política. Ponga `LISTEN_HTTP` en `no` en el servicio para cerrar por completo el puerto HTTP sin cifrar.

### Parámetros de configuración

| Parámetro                      | Valor predeterminado | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------------------------ | -------------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                     | `no`                 | multisite | no       | **Usar mutual TLS:** habilita la autenticación mediante certificados de cliente para el sitio actual.                                                                                                                                                                                                                                                                                                                                                                                         |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`               | multisite | no       | **Prioridad del paquete de CA de clientes:** origen del paquete de CA de clientes: `file` (ruta) o `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                       |
| `MTLS_CA_CERTIFICATE`          |                      | multisite | no       | **Ruta del paquete de CA de clientes:** ruta al paquete de CA de confianza (PEM), legible por el Scheduler. Obligatorio cuando `MTLS_VERIFY_CLIENT` es `on` u `optional`.                                                                                                                                                                                                                                                                                                                     |
| `MTLS_CA_CERTIFICATE_DATA`     |                      | multisite | no       | **Datos del paquete de CA de clientes:** paquete de CA de confianza aportado directamente como base64 o PEM (p. ej. mediante la interfaz web).                                                                                                                                                                                                                                                                                                                                                |
| `MTLS_VERIFY_CLIENT`           | `on`                 | multisite | no       | **Modo de verificación:** `on` exige un certificado válido en cada solicitud HTTPS. `optional` pide un certificado, rechaza uno inválido y no aplica nada más salvo que se defina `MTLS_URL`. `optional_no_ca` pide un certificado sin validarlo contra una CA (solo diagnóstico). Consulte "Qué protege cada modo".                                                                                                                                                                          |
| `MTLS_URL`                     |                      | multisite | sí       | **URL mTLS:** expresión regular sobre la URI normalizada de la solicitud que exige un certificado de cliente válido solo en las rutas coincidentes, por HTTPS y por HTTP sin cifrar. Requiere que `MTLS_VERIFY_CLIENT` sea `optional`. Distingue mayúsculas de minúsculas; ánclela a un directorio. Déjelo vacío para no definir ninguna regla por ruta: con `optional` u `optional_no_ca` no se aplica nada, y exigir un certificado en todo el sitio requiere `MTLS_VERIFY_CLIENT` en `on`. |
| `MTLS_HTTP_POLICY`             | `redirect`           | multisite | no       | **Política HTTP:** qué hacer con una solicitud HTTP sin cifrar que mTLS debería haber protegido: redirigirla a HTTPS (`redirect`), denegarla (`deny`) o permitirla (`allow`, solo en el modo para todo el sitio; las rutas de `MTLS_URL` siguen denegadas).                                                                                                                                                                                                                                   |
| `MTLS_COUNT_BAD_BEHAVIOR`      | `no`                 | multisite | no       | **Contar los fallos de mTLS en Bad Behavior:** deja que Bad Behavior cuente el `400` que NGINX responde ante un certificado de cliente ausente o inválido y las denegaciones que emite el propio mTLS. Con `no`, un cliente sin certificado válido no es bloqueado solo por eso.                                                                                                                                                                                                              |
| `MTLS_VERIFY_DEPTH`            | `2`                  | multisite | no       | **Profundidad de verificación:** profundidad máxima de la cadena aceptada para los certificados de cliente.                                                                                                                                                                                                                                                                                                                                                                                   |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`                | multisite | no       | **Reenviar cabeceras del cliente:** propaga los resultados de la verificación (`X-SSL-Client-*` con estado, DN, emisor, serie, huella y ventana de validez). Las cabeceras `X-SSL-*` enviadas por el cliente siempre se eliminan en la entrada, de modo que estos valores no se pueden falsificar.                                                                                                                                                                                            |
| `MTLS_CRL_PRIORITY`            | `file`               | multisite | no       | **Prioridad de la CRL de clientes:** origen de la CRL: `file` (ruta) o `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                                                   |
| `MTLS_CRL`                     |                      | multisite | no       | **Ruta de la CRL de clientes:** ruta opcional a una lista de revocación de certificados en formato PEM, legible por el Scheduler. Solo se aplica cuando el paquete de CA se carga correctamente. NGINX necesita una CRL de cada CA que emite un certificado de la cadena, la CA raíz incluida. Una CRL caducada rechaza a los clientes de su CA.                                                                                                                                              |
| `MTLS_CRL_DATA`                |                      | multisite | no       | **Datos de la CRL de clientes:** lista de revocación aportada directamente como base64 o PEM.                                                                                                                                                                                                                                                                                                                                                                                                 |

!!! info "Una nueva CRL o un cambio de CA de cliente descarta las sesiones TLS en caché"
    Un cambio de CRL o del paquete de CA de cliente descarta una vez todas las sesiones TLS en caché de la instancia, porque la caché de sesiones lleva el nombre de un hash de los paquetes de CA y las CRL publicados. Un certificado revocado no puede reanudar una sesión anterior y el resto de clientes hace un handshake completo.

!!! tip "Escriba las reglas de `MTLS_URL` con cuidado"
    - La coincidencia distingue mayúsculas de minúsculas: `^/admin` no coincide con `/Admin`. Empiece el patrón con `(?i)` para ignorar la capitalización.
    - La expresión regular se aplica a la URI tal como la normaliza NGINX (decodificada, con los segmentos de punto resueltos y las barras repetidas fusionadas), sin la cadena de consulta, así que `/a/../admin` y `//admin` ya están cubiertos.
    - Ancle a un directorio, no a un nombre de archivo. Escriba `^/admin(/|$)` en lugar de `^/admin$`, que no coincide con `/admin/`. Una regla anclada a un nombre de archivo como `^/admin/index\.html$` tampoco cubre `/admin/`: NGINX lo sirve desde ese archivo mediante una redirección interna.
    - Los parámetros de ruta como `/admin;x=1` y cualquier otra normalización que su backend aplique además de la de NGINX (por ejemplo `..;/` o las barras invertidas) deben cubrirse en la expresión regular por su cuenta. BunkerWeb compara la URI que ve NGINX.
    - Una expresión regular inválida falla en modo cerrado: toda solicitud que ninguna regla anterior haya aceptado se deniega (`403`) hasta que la corrija. BunkerWeb registra un error que nombra el servicio y el patrón al arrancar y tras cada recarga.

!!! tip "Configúralo una vez, distribuido en todas partes"
    Los paquetes de CA y las listas de revocación no necesitan montarse en los contenedores de BunkerWeb. Aporte solo al Scheduler una ruta de archivo o datos incrustados; el Scheduler los valida, los almacena en caché y los distribuye a cada instancia. Las actualizaciones se recogen y redistribuyen automáticamente en la siguiente ejecución del job.

!!! warning "Paquete de CA obligatorio en modos estrictos"
    Cuando `MTLS_VERIFY_CLIENT` está en `on` u `optional`, el Scheduler debe poder validar y almacenar en caché un paquete de CA de clientes. Mientras no haya validado y distribuido uno, cada instancia recurre a una CA de marcador de posición con la que ningún cliente puede formar una cadena de confianza. Con `on` eso significa que se rechaza a todos los clientes, donde antes el servicio funcionaba sin ninguna verificación de cliente. Con `optional` un cliente que no presenta certificado sigue pasando, que es lo que significa ese modo; la aplicación para esas peticiones proviene de `MTLS_URL` cuando está definido, y no hay ninguna cuando se deja vacío. Un cliente que sí presenta un certificado es rechazado, porque no hay nada contra lo que validarlo. Utilice `optional_no_ca` solo para diagnóstico porque debilita la autenticación. Tras un reinicio del Scheduler con un `/var/cache/bunkerweb` no persistente, ese estado se mantiene hasta que se complete la primera ejecución del job y redistribuya el paquete de CA; utilice por tanto un volumen de caché persistente cuando se requiera una postura de aplicación estricta.

!!! warning "mTLS se ejecuta antes que la lista blanca"
    mTLS se evalúa justo después del plugin SSL y antes de la lista blanca. Un cliente que coincide con `WHITELIST_IP`, `WHITELIST_URI`, `WHITELIST_USER_AGENT` (o con una entrada predeterminada de `WHITELIST_RDNS` o `WHITELIST_ASN`) sigue necesitando un certificado donde mTLS lo exige. Antes de la 1.6.19 la lista blanca se saltaba la comprobación de `MTLS_URL`. Para restaurar esa precedencia, ponga `PLUGINS_ORDER_ACCESS` en `ssl whitelist mtls`. Si define `PLUGINS_ORDER_ACCESS` usted mismo, de forma global o por servicio, su valor se conserva: si no nombra `mtls`, mTLS sigue ejecutándose después de la lista blanca en ese caso. Ponga `mtls` justo después de `ssl` en ese valor.

!!! info "Bad Behavior no cuenta por defecto los fallos de certificado"
    Con `MTLS_COUNT_BAD_BEHAVIOR` en `no`, el plugin Bad Behavior no cuenta el `400` que NGINX responde cuando el certificado de cliente falta o es inválido, ni las denegaciones que emite el propio mTLS (regla por ruta, política para HTTP sin cifrar, expresión regular `MTLS_URL` inválida), así que un cliente sin certificado válido no es bloqueado solo por eso. Cualquier otro `400` en el mismo servicio sigue contando. Póngalo en `yes` para volver a contarlos. La respuesta ante un certificado ausente o inválido es ahora la página de error `400` de BunkerWeb cuando el plugin Errors gestiona el `400` (lo habitual, salvo que `ERRORS` defina una página propia para `400`); en caso contrario sigue siendo la página estándar de NGINX.

!!! info "Servicios stream"
    En un servicio stream solo se aplica la comprobación a nivel de handshake, así que solo `MTLS_VERIFY_CLIENT` en `on` aplica algo. `optional` y `optional_no_ca` dejan pasar a un cliente sin certificado, y `MTLS_URL` y `MTLS_HTTP_POLICY` son solo para HTTP.

!!! info "Las cabeceras `X-SSL-Client-*` solo llegan a los upstreams de proxy inverso y gRPC"
    BunkerWeb reenvía los resultados de la verificación a los servicios configurados con los plugins de proxy inverso o gRPC. PHP/FastCGI y las locations personalizadas no los reciben: pase usted mismo las variables `$ssl_client_*` de NGINX en su configuración.

!!! info "Certificado confiable y verificación"
    BunkerWeb reutiliza el mismo paquete de CA tanto para comprobar clientes como para construir la cadena de confianza, manteniendo coherentes las verificaciones de revocación y el handshake.

!!! info "Las cabeceras `X-SSL-*` entrantes siempre se eliminan"
    BunkerWeb elimina toda cabecera de petición `X-SSL-*` enviada por el cliente antes de que la petición llegue a su aplicación: en todos los sitios, esté o no habilitado mTLS, y por igual en HTTP/1.1, HTTP/2 y HTTP/3. Solo se reenvían los valores que BunkerWeb obtiene del handshake TLS verificado, y únicamente cuando `MTLS_FORWARD_CLIENT_HEADERS` es `yes`, así que un cliente no puede falsificar `X-SSL-Client-Verify: SUCCESS`.

    Si BunkerWeb está detrás de otro proxy que termina mTLS e inyecta estas cabeceras por su cuenta, capture el valor antes de la eliminación y vuelva a publicarlo. Añada una configuración personalizada `server-http`:

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    y luego reenvíelo con `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"`. `REVERSE_PROXY_HEADERS` por sí solo no funciona: `$http_x_ssl_client_verify` ya está vacío cuando `proxy_set_header` lo evalúa, mientras que `set` se ejecuta en la fase server-rewrite, antes de la eliminación.

!!! warning "El mTLS por ruta requiere el modo opcional"
    La directiva `ssl_verify_client` de NGINX solo es válida en el contexto `server`: no puede colocarse dentro de un bloque `location`. Para exigir un certificado únicamente en algunas rutas, ponga `MTLS_VERIFY_CLIENT` en `optional` para que el handshake se complete en todas las rutas, y luego liste las rutas protegidas en `MTLS_URL_n`. BunkerWeb aplica entonces el certificado por solicitud, en Lua, sobre las URL coincidentes. Use `optional` para una aplicación real: `optional_no_ca` omite la comprobación de CA en el handshake, y la comprobación por ruta sigue necesitando un certificado que se valide contra un paquete de CA, así que sin ningún paquete de CA configurado las rutas coincidentes deniegan a todos los clientes. Si deja `MTLS_VERIFY_CLIENT` en `on` mientras define `MTLS_URL_n`, NGINX rechaza a los clientes sin certificado durante el handshake, antes de que se aplique la lógica por ruta, por lo que la exigencia sigue siendo para todo el sitio (BunkerWeb registra una advertencia al arrancar en ese caso).

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

    Permita usuarios anónimos, pero reenvíe los detalles del certificado cuando un cliente presente uno. Esto no aplica nada por sí mismo: su aplicación decide a partir de las cabeceras reenviadas:

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
    MTLS_URL_1: "^/login(/|$)"
    MTLS_URL_2: "^/admin(/|$)"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Solicitud           | Certificado         | Resultado                                             |
    | ------------------- | ------------------- | ----------------------------------------------------- |
    | `GET /`             | ninguno             | Permitido (ruta sin mTLS)                             |
    | `GET /login`        | ninguno             | Denegado (`403`)                                      |
    | `GET /login`        | válido              | Permitido, `X-SSL-Client-*` reenviado                 |
    | cualquier ruta      | inválido / expirado | Rechazado por NGINX (`400`)                           |
    | `GET /login` (HTTP) | ninguno             | Redirigido a HTTPS (`MTLS_HTTP_POLICY` es `redirect`) |
