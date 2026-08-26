El complemento de Proxy Inverso proporciona capacidades de proxy sin interrupciones para BunkerWeb, lo que le permite enrutar solicitudes a servidores y servicios de backend. Esta función permite que BunkerWeb actúe como un frontend seguro para sus aplicaciones al tiempo que proporciona beneficios adicionales como la terminación de SSL y el filtrado de seguridad.

**Cómo funciona:**

1.  Cuando un cliente envía una solicitud a BunkerWeb, el complemento de Proxy Inverso reenvía la solicitud a su servidor de backend configurado.
2.  BunkerWeb agrega encabezados de seguridad, aplica reglas de WAF y realiza otras verificaciones de seguridad antes de pasar las solicitudes a su aplicación.
3.  El servidor de backend procesa la solicitud y devuelve una respuesta a BunkerWeb.
4.  BunkerWeb aplica medidas de seguridad adicionales a la respuesta antes de enviarla de vuelta al cliente.
5.  El complemento admite el proxy de flujo tanto HTTP como TCP/UDP, lo que permite una amplia gama de aplicaciones, incluidos WebSockets y otros protocolos no HTTP.

### Cómo usar

Siga estos pasos para configurar y usar la función de Proxy Inverso:

1.  **Habilite la función:** Establezca el ajuste `USE_REVERSE_PROXY` en `yes` para habilitar la funcionalidad de proxy inverso.
2.  **Configure sus servidores de backend:** Especifique los servidores upstream utilizando el ajuste `REVERSE_PROXY_HOST`.
3.  **Ajuste la configuración del proxy:** Afine el comportamiento con ajustes opcionales para tiempos de espera, tamaños de búfer y otros parámetros.
4.  **Configure las opciones específicas del protocolo:** Para WebSockets o requisitos HTTP especiales, ajuste la configuración correspondiente.
5.  **Configure el almacenamiento en caché (opcional):** Habilite y configure el almacenamiento en caché del proxy para mejorar el rendimiento del contenido al que se accede con frecuencia.

### Upstreams reutilizables

Los ajustes de más abajo apuntan un `location` a un único backend. Cuando varios backends sirven la misma aplicación, o varios servicios comparten los mismos backends, puede en su lugar declarar un **grupo con nombre y reutilizable** — un upstream — desde la página **Upstreams** de la interfaz web o a través de los endpoints de API `/upstreams`, y adjuntarlo a tantos servicios como quiera. Editar el grupo actualiza todos los servicios a los que está adjunto.

- Un grupo lleva un nombre, un **protocolo**, un método de balanceo de carga (`round_robin`, `least_conn` o `ip_hash`), un número opcional de conexiones `keepalive` y uno o varios servidores.
- Cada servidor lleva su dirección (`host` o `host:puerto`, sin esquema), un `weight` y los parámetros de comprobación de salud pasiva `max_fails` y `fail_timeout`; también puede marcarse como `backup` (solo se usa cuando los demás fallan) o `down` (retirado temporalmente).
- El **protocolo** decide qué consumidor usa el grupo y cómo se adjunta:
    - `http` — el proxy inverso (`proxy_pass`). Se adjunta a un **servicio y una ruta**, de modo que un mismo servicio puede enviar `/` a un grupo y `/api` a otro.
    - `grpc` — el complemento gRPC (`grpc_pass`), adjuntado de la misma forma. Los grupos HTTP y gRPC comparten un único espacio de nombres de rutas, ya que ambos renderizan un `location` en el mismo servidor.
    - `stream` — un servicio TCP/UDP. No hay ruta: el grupo se hace cargo de todo el servicio y sustituye al único backend implícito que la configuración de stream construye a partir de `REVERSE_PROXY_HOST`. Un servicio solo puede llevar uno, y `keepalive` no se aplica.
- El interruptor `backend_ssl` selecciona TLS hacia los servidores: `https://` en lugar de `http://`, `grpcs://` en lugar de `grpc://`.
- El protocolo tiene que coincidir con el servicio: un grupo HTTP o gRPC va en un servicio cuyo `SERVER_TYPE` sea `http`, y un grupo stream en uno cuyo `SERVER_TYPE` sea `stream`. La interfaz web solo ofrece los servicios compatibles; la API rechaza el resto con una explicación.
- Los ajustes en línea `REVERSE_PROXY_HOST` y `GRPC_HOST` siguen funcionando exactamente igual que antes. Los grupos adjuntos se renderizan **después** de ellos, tomando los siguientes sufijos libres, de modo que las configuraciones existentes no se tocan y no hace falta ninguna migración. En un servicio con un grupo adjunto se activa automáticamente `USE_REVERSE_PROXY` (o `USE_GRPC`).
- **Una ruta, un propietario.** El proxy inverso, gRPC y las **redirecciones** renderizan todos un `location` en el mismo servidor, y NGINX rechaza dos bloques `location` con la misma URI. Por tanto, una ruta queda ocupada para los tres a la vez — la reclame un grupo adjunto, una redirección adjunta o un ajuste en línea — y el cambio en conflicto se rechaza con un mensaje que indica qué la ocupa ya.
- Un grupo que no está adjunto a nada no renderiza nada, y eliminar un grupo se rechaza mientras siga adjunto a un servicio; despréndalo primero. Cambiar el protocolo de un grupo adjunto se rechaza por la misma razón.
- Los nombres de grupo solo aceptan letras, dígitos, guiones y guiones bajos. Los puntos se rechazan a propósito: NGINX resuelve un nombre contra los upstreams declarados antes que con el resolutor DNS, así que un grupo con el nombre de un host real capturaría el tráfico destinado a él.

### TLS mutuo con el upstream

Los ajustes `REVERSE_PROXY_SSL_VERIFY` de más abajo comprueban el certificado *del backend*. Para presentar además un certificado **al** backend — TLS mutuo — configure el par de cliente:

- `REVERSE_PROXY_SSL_CLIENT_CERT` / `REVERSE_PROXY_SSL_CLIENT_KEY` para rutas de archivo legibles por el planificador, o `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` / `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` para PEM en base64 o en texto plano, seleccionados por `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY` (`file` o `data`).
- El par se valida con OpenSSL, se cachea y se distribuye a todas las instancias por el mismo trabajo que gestiona la CA de confianza, y allí se escribe con permisos solo de propietario y grupo.
- **Ambas mitades son obligatorias.** Un certificado sin su clave (o al revés) se rechaza en lugar de aplicarse a medias, porque NGINX necesita ambas directivas o ninguna.
- La identidad es **por servicio, y se comparte con gRPC y stream**: un servicio se autentica ante sus backends con un único certificado, sea cual sea el complemento que enruta el tráfico. En el contexto stream esto es además lo que habilita TLS hacia el backend (`proxy_ssl on`), de modo que un servicio sin par de cliente conserva su comportamiento actual en texto plano.
- Borrar los ajustes elimina los archivos en la siguiente ejecución, lo que vuelve a desactivar el TLS mutuo.

Esto es independiente del complemento `mtls`, que autentica *a los clientes que se conectan a BunkerWeb* — la dirección opuesta.

!!! warning "Un backend no resoluble hace fallar la recarga"
    NGINX resuelve las direcciones de los servidores upstream al cargar su configuración. Si un servidor de un grupo adjunto no puede resolverse, se rechaza toda la configuración y BunkerWeb conserva la última válida. Use una dirección que se resuelva en el momento de la recarga, o marque el servidor como `down` mientras no esté disponible.

### Guía de Configuración

=== "Configuración Básica"

    **Ajustes Principales**

    Los ajustes de configuración esenciales habilitan y controlan la funcionalidad básica de la función de proxy inverso.

    !!! success "Beneficios del Proxy Inverso"
        - **Mejora de la Seguridad:** Todo el tráfico pasa a través de las capas de seguridad de BunkerWeb antes de llegar a sus aplicaciones
        - **Terminación SSL:** Administre los certificados SSL/TLS de forma centralizada mientras que los servicios de backend pueden usar conexiones no cifradas
        - **Manejo de Protocolos:** Soporte para HTTP, HTTPS, WebSockets y otros protocolos
        - **Interceptación de Errores:** Personalice las páginas de error para una experiencia de usuario consistente

| Ajuste                            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                     |
| --------------------------------- | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_REVERSE_PROXY`               | `no`              | multisite | no       | **Habilitar Proxy Inverso:** Establezca en `yes` para habilitar la funcionalidad de proxy inverso.                                                                                                                                              |
| `REVERSE_PROXY_HOST`              |                   | multisite | yes      | **Host de Backend:** URL completa del recurso al que se hace proxy (proxy_pass).                                                                                                                                                                |
| `REVERSE_PROXY_URL`               | `/`               | multisite | yes      | **URL de Ubicación:** Ruta que se enviará al servidor de backend. Un valor que comienza por `^` o termina en `$` se trata como una ubicación de expresión regular.                                                                              |
| `REVERSE_PROXY_BUFFERING`         | `yes`             | multisite | yes      | **Almacenamiento en Búfer de Respuesta:** Habilite o deshabilite el almacenamiento en búfer de las respuestas del recurso al que se hace proxy.                                                                                                 |
| `REVERSE_PROXY_REQUEST_BUFFERING` | `yes`             | multisite | yes      | **Almacenamiento en Búfer de Solicitudes:** Habilite o deshabilite el almacenamiento en búfer de las solicitudes al recurso al que se hace proxy.                                                                                               |
| `REVERSE_PROXY_KEEPALIVE`         | `no`              | multisite | yes      | **Keep-Alive:** Habilite o deshabilite las conexiones keepalive con el recurso al que se hace proxy.                                                                                                                                            |
| `REVERSE_PROXY_HTTP_VERSION`      | `1.1`             | multisite | yes      | **Versión HTTP:** Versión del protocolo HTTP utilizada para hablar con el upstream (`1.0`, `1.1` o `2`). Establezca a `2` para multiplexación HTTP/2 en la conexión upstream. Las ubicaciones WebSocket están fijadas a 1.1 independientemente. |
| `REVERSE_PROXY_CUSTOM_HOST`       |                   | multisite | no       | **Host Personalizado:** Anule el encabezado Host enviado al servidor upstream.                                                                                                                                                                  |
| `REVERSE_PROXY_INTERCEPT_ERRORS`  | `yes`             | multisite | no       | **Interceptar Errores:** Si se deben interceptar y reescribir las respuestas de error del backend.                                                                                                                                              |

    !!! tip "Mejores Prácticas"
        - Siempre especifique la URL completa en `REVERSE_PROXY_HOST`, incluido el protocolo (http:// o https://)
        - Use `REVERSE_PROXY_INTERCEPT_ERRORS` para proporcionar páginas de error consistentes en todos sus servicios
        - Al configurar múltiples backends, use el formato de sufijo numerado (por ejemplo, `REVERSE_PROXY_HOST_2`, `REVERSE_PROXY_URL_2`)

    !!! warning "Comportamiento del almacenamiento en búfer de solicitudes"
        Desactivar `REVERSE_PROXY_REQUEST_BUFFERING` solo tiene efecto cuando ModSecurity está deshabilitado, porque el almacenamiento en búfer de solicitudes se fuerza de otro modo.

=== "Ajustes de Conexión"

    **Configuración de Conexión y Tiempo de Espera**

    Estos ajustes controlan el comportamiento de la conexión, el almacenamiento en búfer y los valores de tiempo de espera para las conexiones con proxy.

    !!! success "Beneficios"
        - **Rendimiento Optimizado:** Ajuste los tamaños de los búferes y la configuración de la conexión según las necesidades de su aplicación
        - **Gestión de Recursos:** Controle el uso de la memoria mediante configuraciones de búfer adecuadas
        - **Fiabilidad:** Configure los tiempos de espera adecuados para manejar conexiones lentas o problemas de backend

| Ajuste                          | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                    |
| ------------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `REVERSE_PROXY_CONNECT_TIMEOUT` | `60s`             | multisite | yes      | **Tiempo de Espera de Conexión:** Tiempo máximo para establecer una conexión con el servidor de backend.                       |
| `REVERSE_PROXY_STREAM_HALF_CLOSE` | `no` | multisite | sí | **Cierre parcial de stream:** con `yes`, mantiene abierta la conexión al backend después de que el cliente cierre su lado de escritura. Necesario en protocolos TCP donde el cliente cierra parcialmente y luego espera la respuesta; nginx cierra ambos sentidos por defecto. Solo servicios stream (TCP/UDP). |
| `REVERSE_PROXY_READ_TIMEOUT`    | `60s`             | multisite | yes      | **Tiempo de Espera de Lectura:** Tiempo máximo entre las transmisiones de dos paquetes sucesivos desde el servidor de backend. |
| `REVERSE_PROXY_SEND_TIMEOUT`    | `60s`             | multisite | yes      | **Tiempo de Espera de Envío:** Tiempo máximo entre las transmisiones de dos paquetes sucesivos al servidor de backend.         |
| `PROXY_BUFFERS`                 |                   | multisite | no       | **Búferes:** Número y tamaño de los búferes para leer la respuesta del servidor de backend.                                    |
| `PROXY_BUFFER_SIZE`             |                   | multisite | no       | **Tamaño del Búfer:** Tamaño del búfer para leer la primera parte de la respuesta del servidor de backend.                     |
| `PROXY_BUSY_BUFFERS_SIZE`       |                   | multisite | no       | **Tamaño de los Búferes Ocupados:** Tamaño de los búferes que pueden estar ocupados enviando la respuesta al cliente.          |

    !!! warning "Consideraciones sobre el Tiempo de Espera"
        - Establecer tiempos de espera demasiado bajos puede hacer que se terminen las conexiones legítimas pero lentas
        - Establecer tiempos de espera demasiado altos puede dejar las conexiones abiertas innecesariamente, lo que podría agotar los recursos
        - Para las aplicaciones WebSocket, aumente significativamente los tiempos de espera de lectura y envío (se recomienda 300s o más)

=== "Configuración SSL/TLS"

    **Ajustes SSL/TLS para Conexiones de Backend**

    Estos ajustes controlan cómo BunkerWeb establece conexiones seguras con los servidores de backend.

    !!! success "Beneficios"
        - **Cifrado de Extremo a Extremo:** Mantenga las conexiones cifradas desde el cliente hasta el backend
        - **Validación de Certificados:** Controle cómo se validan los certificados del servidor de backend
        - **Soporte SNI:** Especifique la Indicación del Nombre del Servidor para los backends que alojan múltiples sitios

| Ajuste                       | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                          |
| ---------------------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_SSL_SNI`      | `no`              | multisite | no       | **SSL SNI:** Habilite o deshabilite el envío de SNI (Indicación del Nombre del Servidor) al upstream.                |
| `REVERSE_PROXY_SSL_SNI_NAME` |                   | multisite | no       | **Nombre de SSL SNI:** Establece el nombre de host de SNI que se enviará al upstream cuando SSL SNI esté habilitado. |
| `REVERSE_PROXY_SSL_VERIFY`                       | `no`   | multisite | no       | **SSL Verify:** Habilita o deshabilita la verificación del certificado SSL del servidor upstream.        |
| `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY` | `file` | multisite | no       | **Prioridad del certificado de confianza:** Origen de la CA de confianza: `file` (ruta) o `data` (base64/PEM). |
| `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`          |        | multisite | no       | **Ruta del certificado de confianza SSL:** Ruta a un paquete de CA en PEM (legible por el planificador) usado para verificar el upstream. |
| `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`     |        | multisite | no       | **Datos del certificado de confianza SSL:** CA de confianza directamente como base64 o PEM (p. ej. mediante la interfaz web). |
| `REVERSE_PROXY_SSL_VERIFY_DEPTH`                 | `1`    | multisite | no       | **Profundidad de Verificación SSL:** Profundidad de verificación en la cadena de certificados del servidor upstream. |
| `REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY` | `file` | multisite | no | **Prioridad del certificado de cliente:** Origen del certificado y la clave que se presentan al upstream: `file` (ruta) o `data` (base64/PEM). |
| `REVERSE_PROXY_SSL_CLIENT_CERT` | | multisite | no | **Ruta del certificado de cliente:** Ruta al certificado de cliente PEM que BunkerWeb presenta al upstream, legible por el planificador. Requiere la clave correspondiente. |
| `REVERSE_PROXY_SSL_CLIENT_CERT_DATA` | | multisite | no | **Datos del certificado de cliente:** Certificado de cliente proporcionado directamente como base64 o PEM (p. ej. desde la interfaz web). |
| `REVERSE_PROXY_SSL_CLIENT_KEY` | | multisite | no | **Ruta de la clave de cliente:** Ruta a la clave privada PEM que corresponde al certificado de cliente, legible por el planificador. |
| `REVERSE_PROXY_SSL_CLIENT_KEY_DATA` | | multisite | no | **Datos de la clave de cliente:** Clave privada de cliente proporcionada directamente como base64 o PEM. Prefiera una ruta de archivo cuando sea posible: una clave puesta aquí se almacena como valor de ajuste. |

    !!! info "Verificación de Certificados"
        Cuando `REVERSE_PROXY_SSL_VERIFY` se establece en `yes`, NGINX valida tanto la cadena de certificados del upstream como su nombre:

        - **CA de confianza:** proporciónela como ruta de archivo (`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE`, legible por el planificador) o como datos base64/PEM (`REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA`), según `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY`. El planificador la valida, la almacena en caché y la distribuye a cada instancia, por lo que solo la configura una vez, sin montaje por instancia.
        - **Obligatorio:** se requiere un certificado de confianza; NGINX no tiene un almacén del sistema implícito para la verificación del upstream. Para verificar un upstream público, apunte la ruta al paquete de CA del sistema (p. ej. `/etc/ssl/certs/ca-certificates.crt`).
        - **Nombre:** se comprueba por defecto contra el host de `REVERSE_PROXY_HOST`. Si el CN/SAN del certificado del backend difiere, establezca `REVERSE_PROXY_SSL_SNI` en `yes` y `REVERSE_PROXY_SSL_SNI_NAME` con el nombre esperado.
        - **A prueba de fallos:** si no hay un certificado de confianza válido disponible, la verificación se deshabilita para ese servidor en lugar de romper cada conexión upstream.

        Estos ajustes se aplican por servicio: todas las entradas de upstream (`REVERSE_PROXY_HOST`, `REVERSE_PROXY_HOST_1`, ...) comparten la misma configuración de verificación.

    !!! info "SNI Explicado"
        La Indicación del Nombre del Servidor (SNI) es una extensión de TLS que permite a un cliente especificar el nombre de host al que intenta conectarse durante el proceso de handshake. Esto permite a los servidores presentar múltiples certificados en la misma dirección IP y puerto, lo que permite que múltiples sitios web seguros (HTTPS) se sirvan desde una única dirección IP sin requerir que todos esos sitios usen el mismo certificado.

=== "Soporte de Protocolo"

    **Configuración Específica del Protocolo**

    Configure el manejo especial de protocolos, particularmente para WebSockets y otros protocolos no HTTP.

    !!! success "Beneficios"
        - **Flexibilidad de Protocolo:** El soporte para WebSockets permite aplicaciones en tiempo real
        - **Aplicaciones Web Modernas:** Habilite características interactivas que requieren comunicación bidireccional

| Ajuste             | Valor por defecto | Contexto  | Múltiple | Descripción                                                              |
| ------------------ | ----------------- | --------- | -------- | ------------------------------------------------------------------------ |
| `REVERSE_PROXY_WS` | `no`              | multisite | yes      | **Soporte de WebSocket:** Habilite el protocolo WebSocket en el recurso. |

    !!! tip "Configuración de WebSocket"
        - Al habilitar WebSockets con `REVERSE_PROXY_WS: "yes"`, considere aumentar los valores de tiempo de espera
        - Las conexiones WebSocket permanecen abiertas más tiempo que las conexiones HTTP típicas
        - Para las aplicaciones WebSocket, una configuración recomendada es:
          ```yaml
          REVERSE_PROXY_WS: "yes"
          REVERSE_PROXY_READ_TIMEOUT: "300s"
          REVERSE_PROXY_SEND_TIMEOUT: "300s"
          ```

=== "Gestión de Encabezados"

    **Configuración de Encabezados HTTP**

    Controle qué encabezados se envían a los servidores de backend y a los clientes, lo que le permite agregar, modificar o preservar los encabezados HTTP.

    !!! success "Beneficios"
        - **Control de la Información:** Administre con precisión qué información se comparte entre los clientes y los backends
        - **Mejora de la Seguridad:** Agregue encabezados relacionados con la seguridad o elimine los encabezados que podrían filtrar información sensible
        - **Soporte de Integración:** Proporcione los encabezados necesarios para la autenticación y el correcto funcionamiento del backend

| Ajuste                                 | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                          |
| -------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_HEADERS`                |                   | multisite | yes      | **Encabezados Personalizados:** Encabezados HTTP para enviar al backend separados por punto y coma.  |
| `REVERSE_PROXY_HIDE_HEADERS`           | `Upgrade`         | multisite | yes      | **Ocultar Encabezados:** Encabezados HTTP para ocultar a los clientes cuando se reciben del backend. |
| `REVERSE_PROXY_HEADERS_CLIENT`         |                   | multisite | yes      | **Encabezados del Cliente:** Encabezados HTTP para enviar al cliente separados por punto y coma.     |
| `REVERSE_PROXY_UNDERSCORES_IN_HEADERS` | `no`              | multisite | no       | **Guiones Bajos en los Encabezados:** Habilite o deshabilite la directiva `underscores_in_headers`.  |

    !!! warning "Consideraciones de Seguridad"
        Al usar la función de proxy inverso, tenga cuidado con los encabezados que reenvía a sus aplicaciones de backend. Ciertos encabezados pueden exponer información sensible sobre su infraestructura o eludir los controles de seguridad.

    !!! example "Ejemplos de Formato de Encabezado"
        Encabezados personalizados para los servidores de backend:
        ```
        REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"
        ```

        Encabezados personalizados para los clientes:
        ```
        REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
        ```

=== "Autenticación"

    **Configuración de Autenticación Externa**

    Integre con sistemas de autenticación externos para centralizar la lógica de autorización en sus aplicaciones.

    !!! success "Beneficios"
        - **Autenticación Centralizada:** Implemente un único punto de autenticación para múltiples aplicaciones
        - **Seguridad Consistente:** Aplique políticas de autenticación uniformes en diferentes servicios
        - **Control Mejorado:** Reenvíe los detalles de la autenticación a las aplicaciones de backend a través de encabezados o variables

| Ajuste                                  | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                      |
| --------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_AUTH_REQUEST`            |                   | multisite | yes      | **Solicitud de Autenticación:** Habilite la autenticación mediante un proveedor externo.                         |
| `REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL` |                   | multisite | yes      | **URL de Inicio de Sesión:** Redirija a los clientes a la URL de inicio de sesión cuando falle la autenticación. |
| `REVERSE_PROXY_AUTH_REQUEST_SET`        |                   | multisite | yes      | **Conjunto de Solicitudes de Autenticación:** Variables a establecer desde el proveedor de autenticación.        |

    !!! tip "Integración de Autenticación"
        - La función de solicitud de autenticación permite la implementación de microservicios de autenticación centralizados
        - Su servicio de autenticación debe devolver un código de estado 200 para una autenticación exitosa o 401/403 para fallas
        - Use la directiva `auth_request_set` para extraer y reenviar información del servicio de autenticación

=== "Configuración Avanzada"

    **Opciones de Configuración Adicionales**

    Estos ajustes proporcionan una mayor personalización del comportamiento del proxy inverso para escenarios especializados.

    !!! success "Beneficios"
        - **Personalización:** Incluya fragmentos de configuración adicionales para requisitos complejos
        - **Optimización del Rendimiento:** Afine el manejo de solicitudes para casos de uso específicos
        - **Flexibilidad:** Adáptese a los requisitos únicos de la aplicación con configuraciones especializadas

| Ajuste                            | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                       |
| --------------------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `REVERSE_PROXY_INCLUDES`          |                   | multisite | yes      | **Configuraciones Adicionales:** Incluya configuraciones adicionales en el bloque de ubicación.                                                                                                   |
| `REVERSE_PROXY_PASS_REQUEST_BODY` | `yes`             | multisite | yes      | **Pasar el Cuerpo de la Solicitud:** Habilite o deshabilite el paso del cuerpo de la solicitud.                                                                                                   |
| `REVERSE_PROXY_MODSECURITY`       | `yes`             | multisite | yes      | **ModSecurity (por ubicación):** Establézcalo en `no` para emitir `modsecurity off;` en esta ubicación; omite el WAF en endpoints de cargas grandes para evitar OOM (consulte la nota siguiente). |
| `REVERSE_PROXY_SEND_PROXY_PROTOCOL` | `auto` | multisite | no | **Enviar protocolo PROXY:** Envía la cabecera del protocolo PROXY al upstream de stream. `auto` sigue el ajuste global `USE_PROXY_PROTOCOL`, que es lo que BunkerWeb hacía antes de que existiera este ajuste; `yes` y `no` deciden con independencia del listener de entrada. Solo servicios stream (TCP/UDP). |

    !!! warning "Consideraciones de Seguridad"
        Tenga cuidado al incluir fragmentos de configuración personalizados, ya que pueden anular la configuración de seguridad de BunkerWeb o introducir vulnerabilidades si no se configuran correctamente.

    !!! warning "Recomendación de seguridad para cargas grandes"
        ModSecurity almacena en memoria el cuerpo completo de la solicitud y no puede limitarlo para cargas de varios GB, lo que puede provocar OOM en el worker. Si, **y solo si**, una URL de proxy inverso se usa *exclusivamente* para cargas de archivos (por ejemplo, un endpoint `/upload` dedicado), establezca `REVERSE_PROXY_MODSECURITY_N: "no"` en esa URL. No lo deshabilite en URL de uso mixto: perdería la cobertura del WAF en todo lo servido por esa ubicación.

        Para mantener protegidas las cargas después de omitir ModSecurity, combínelo con un plugin de análisis de archivos como [ClamAV](https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav) o [VirusTotal](https://github.com/bunkerity/bunkerweb-plugins/tree/main/virustotal); inspeccionan el archivo cargado en sí en lugar del cuerpo bruto de la solicitud.

=== "Configuración de Caché"

    **Ajustes de Almacenamiento en Caché de Respuestas**

    Mejore el rendimiento almacenando en caché las respuestas de los servidores de backend, reduciendo la carga y mejorando los tiempos de respuesta.

    !!! success "Beneficios"
        - **Rendimiento:** Reduzca la carga en los servidores de backend sirviendo contenido en caché
        - **Latencia Reducida:** Tiempos de respuesta más rápidos para el contenido solicitado con frecuencia
        - **Ahorro de Ancho de Banda:** Minimice el tráfico de la red interna almacenando en caché las respuestas
        - **Personalización:** Configure exactamente qué, cuándo y cómo se almacena en caché el contenido

| Ajuste                       | Valor por defecto                  | Contexto  | Múltiple | Descripción                                                                                                         |
| ---------------------------- | ---------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `USE_PROXY_CACHE`            | `no`                               | multisite | no       | **Habilitar Caché:** Establezca en `yes` para habilitar el almacenamiento en caché de las respuestas del backend.   |
| `PROXY_CACHE_PATH_LEVELS`    | `1:2`                              | global    | no       | **Niveles de Ruta de Caché:** Cómo estructurar la jerarquía del directorio de caché.                                |
| `PROXY_CACHE_PATH_ZONE_SIZE` | `10m`                              | global    | no       | **Tamaño de la Zona de Caché:** Tamaño de la zona de memoria compartida utilizada para los metadatos de la caché.   |
| `PROXY_CACHE_PATH_PARAMS`    | `max_size=100m`                    | global    | no       | **Parámetros de la Ruta de Caché:** Parámetros adicionales para la ruta de la caché.                                |
| `PROXY_CACHE_METHODS`        | `GET HEAD`                         | multisite | no       | **Métodos de Caché:** Métodos HTTP que se pueden almacenar en caché.                                                |
| `PROXY_CACHE_MIN_USES`       | `2`                                | multisite | no       | **Usos Mínimos de Caché:** Número mínimo de solicitudes antes de que una respuesta se almacene en caché.            |
| `PROXY_CACHE_KEY`            | `$scheme$host$request_uri`         | multisite | no       | **Clave de Caché:** La clave utilizada para identificar de forma única una respuesta en caché.                      |
| `PROXY_CACHE_VALID`          | `200=24h 301=1h 302=24h`           | multisite | no       | **Validez de la Caché:** Cuánto tiempo almacenar en caché los códigos de respuesta específicos.                     |
| `PROXY_NO_CACHE`             | `$http_pragma $http_authorization` | multisite | no       | **Sin Caché:** Condiciones para no almacenar en caché las respuestas aunque normalmente sean almacenables en caché. |
| `PROXY_CACHE_BYPASS`         | `0`                                | multisite | no       | **Omitir Caché:** Condiciones bajo las cuales omitir la caché.                                                      |

    !!! tip "Mejores Prácticas de Almacenamiento en Caché"
        - Almacene en caché solo el contenido que no cambia con frecuencia o no es personalizado
        - Use duraciones de caché apropiadas según el tipo de contenido (los activos estáticos se pueden almacenar en caché por más tiempo)
        - Configure `PROXY_NO_CACHE` para evitar almacenar en caché contenido sensible o personalizado
        - Supervise las tasas de aciertos de la caché y ajuste la configuración en consecuencia

!!! danger "Usuarios de Docker Compose - Variables de NGINX"
    Al usar Docker Compose con variables de NGINX en sus configuraciones, debe escapar el signo de dólar (`$`) usando signos de dólar dobles (`$$`). Esto se aplica a todos los ajustes que contienen variables de NGINX como `$remote_addr`, `$proxy_add_x_forwarded_for`, etc.

    Sin este escape, Docker Compose intentará sustituir estas variables por variables de entorno, que normalmente no existen, lo que dará como resultado valores vacíos en su configuración de NGINX.

### Configuraciones de Ejemplo

=== "Proxy HTTP Básico"

    Una configuración simple para hacer proxy de las solicitudes HTTP a un servidor de aplicaciones de backend:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "60s"
    REVERSE_PROXY_READ_TIMEOUT: "60s"
    ```

=== "Aplicación WebSocket"

    Configuración optimizada para una aplicación WebSocket con tiempos de espera más largos:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://websocket-app:8080"
    REVERSE_PROXY_URL: "/"
    REVERSE_PROXY_WS: "yes"
    REVERSE_PROXY_CONNECT_TIMEOUT: "10s"
    REVERSE_PROXY_SEND_TIMEOUT: "300s"
    REVERSE_PROXY_READ_TIMEOUT: "300s"
    ```

=== "Múltiples Ubicaciones"

    Configuración para enrutar diferentes rutas a diferentes servicios de backend:

    ```yaml
    USE_REVERSE_PROXY: "yes"

    # Backend de la API
    REVERSE_PROXY_HOST: "http://api-server:8080"
    REVERSE_PROXY_URL: "/api/"

    # Backend de Administración
    REVERSE_PROXY_HOST_2: "http://admin-server:8080"
    REVERSE_PROXY_URL_2: "/admin/"

    # Aplicación Frontend
    REVERSE_PROXY_HOST_3: "http://frontend:3000"
    REVERSE_PROXY_URL_3: "/"
    ```

=== "Configuración de Caché"

    Configuración con el almacenamiento en caché del proxy habilitado para un mejor rendimiento:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"
    USE_PROXY_CACHE: "yes"
    PROXY_CACHE_VALID: "200=24h 301=1h 302=24h"
    PROXY_CACHE_METHODS: "GET HEAD"
    PROXY_NO_CACHE: "$http_authorization"
    ```

=== "Gestión Avanzada de Encabezados"

    Configuración con manipulación de encabezados personalizados:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Encabezados personalizados para el backend
    REVERSE_PROXY_HEADERS: "X-Real-IP $remote_addr;X-Forwarded-For $proxy_add_x_forwarded_for;X-Forwarded-Proto $scheme"

    # Encabezados personalizados para el cliente
    REVERSE_PROXY_HEADERS_CLIENT: "X-Powered-By BunkerWeb;X-Frame-Options SAMEORIGIN"
    ```

=== "Integración de Autenticación"

    Configuración con autenticación externa:

    ```yaml
    USE_REVERSE_PROXY: "yes"
    REVERSE_PROXY_HOST: "http://application:8080"
    REVERSE_PROXY_URL: "/"

    # Configuración de autenticación
    REVERSE_PROXY_AUTH_REQUEST: "/auth"
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL: "https://login.example.com"
    REVERSE_PROXY_AUTH_REQUEST_SET: "$auth_user $upstream_http_x_user;$auth_role $upstream_http_x_role"

    # Backend del servicio de autenticación
    REVERSE_PROXY_HOST_2: "http://auth-service:8080"
    REVERSE_PROXY_URL_2: "/auth"
    ```
