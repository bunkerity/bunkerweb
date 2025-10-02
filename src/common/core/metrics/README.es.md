El complemento de Métricas proporciona capacidades completas de monitoreo y recolección de datos para su instancia de BunkerWeb. Esta función le permite rastrear varios indicadores de rendimiento, eventos de seguridad y estadísticas del sistema, brindándole información valiosa sobre el comportamiento y la salud de sus sitios web y servicios protegidos.

**Cómo funciona:**

1.  BunkerWeb recopila métricas clave durante el procesamiento de solicitudes y respuestas.
2.  Estas métricas incluyen contadores de solicitudes bloqueadas, mediciones de rendimiento y varias estadísticas relacionadas con la seguridad.
3.  Los datos se almacenan de manera eficiente en la memoria, con límites configurables para evitar el uso excesivo de recursos.
4.  Para configuraciones de múltiples instancias, se puede usar Redis para centralizar y agregar datos de métricas.
5.  Las métricas recopiladas se pueden acceder a través de la API o visualizarse en la [interfaz de usuario web](web-ui.md).
6.  Esta información le ayuda a identificar amenazas de seguridad, solucionar problemas y optimizar su configuración.

### Implementación Técnica

El complemento de métricas funciona mediante:

- El uso de diccionarios compartidos en NGINX, donde `metrics_datastore` se utiliza para HTTP y `metrics_datastore_stream` para el tráfico TCP/UDP
- El aprovechamiento de una caché LRU para un almacenamiento eficiente en memoria
- La sincronización periódica de datos entre los trabajadores (workers) mediante temporizadores
- El almacenamiento de información detallada sobre las solicitudes bloqueadas, incluida la dirección IP del cliente, el país, la marca de tiempo, los detalles de la solicitud y el motivo del bloqueo
- El soporte para métricas específicas de complementos a través de una interfaz común de recolección de métricas
- La provisión de puntos finales de API para consultar las métricas recopiladas

### Cómo usar

Siga estos pasos para configurar y usar la función de Métricas:

1.  **Habilite la función:** La recolección de métricas está habilitada por defecto. Puede controlar esto con el ajuste `USE_METRICS`.
2.  **Configure la asignación de memoria:** Establezca la cantidad de memoria a asignar para el almacenamiento de métricas utilizando el ajuste `METRICS_MEMORY_SIZE`.
3.  **Establezca los límites de almacenamiento:** Defina cuántas solicitudes bloqueadas almacenar por trabajador y en Redis con los ajustes respectivos.
4.  **Acceda a los datos:** Vea las métricas recopiladas a través de la [interfaz de usuario web](web-ui.md) o los puntos finales de la API.
5.  **Analice la información:** Use los datos recopilados para identificar patrones, detectar problemas de seguridad y optimizar su configuración.

### Métricas Recopiladas

El complemento de métricas recopila la siguiente información:

1.  **Solicitudes Bloqueadas**: Para cada solicitud bloqueada, se almacenan los siguientes datos:
    - ID de la solicitud y marca de tiempo
    - Dirección IP del cliente y país (cuando esté disponible)
    - Método HTTP y URL
    - Código de estado HTTP
    - Agente de usuario
    - Motivo del bloqueo y modo de seguridad
    - Nombre del servidor
    - Datos adicionales relacionados con el motivo del bloqueo

2.  **Contadores de Complementos**: Varios contadores específicos de complementos que rastrean actividades y eventos.

### Acceso a la API

Se puede acceder a los datos de las métricas a través de los puntos finales de la API interna de BunkerWeb:

- **Punto final**: `/metrics/{filtro}`
- **Método**: GET
- **Descripción**: Recupera los datos de las métricas según el filtro especificado
- **Formato de respuesta**: Objeto JSON que contiene las métricas solicitadas

Por ejemplo, `/metrics/requests` devuelve información sobre las solicitudes bloqueadas.

!!! info "Configuración del Acceso a la API"
Para acceder a las métricas a través de la API, debe asegurarse de que:

    1.  La función de API esté habilitada con `USE_API: "yes"` (habilitada por defecto)
    2.  Su IP de cliente esté incluida en el ajuste `API_WHITELIST_IP` (el valor predeterminado es `127.0.0.0/8`)
    3.  Esté accediendo a la API en el puerto configurado (el valor predeterminado es `5000` a través del ajuste `API_HTTP_PORT`)
    4.  Esté utilizando el valor correcto de `API_SERVER_NAME` en el encabezado Host (el valor predeterminado es `bwapi`)
    5.  Si `API_TOKEN` está configurado, incluya `Authorization: Bearer <token>` en los encabezados de la solicitud.

    Solicitudes típicas:

    Sin token (cuando `API_TOKEN` no está configurado):
    ```bash
    curl -H "Host: bwapi" \
         http://su-instancia-de-bunkerweb:5000/metrics/requests
    ```

    Con token (cuando `API_TOKEN` está configurado):
    ```bash
    curl -H "Host: bwapi" \
         -H "Authorization: Bearer $API_TOKEN" \
         http://su-instancia-de-bunkerweb:5000/metrics/requests
    ```

    Si ha personalizado el `API_SERVER_NAME` a algo diferente del valor predeterminado `bwapi`, use ese valor en el encabezado Host en su lugar.

    Para entornos de producción seguros, restrinja el acceso a la API a IPs de confianza y habilite `API_TOKEN`.

### Ajustes de Configuración

| Ajuste                               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                        |
| ------------------------------------ | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_METRICS`                        | `yes`             | multisite | no       | **Habilitar Métricas:** Establezca en `yes` para habilitar la recolección y recuperación de métricas.                                              |
| `METRICS_MEMORY_SIZE`                | `16m`             | global    | no       | **Tamaño de la Memoria:** Tamaño del almacenamiento interno para las métricas (p. ej., `16m`, `32m`).                                              |
| `METRICS_MAX_BLOCKED_REQUESTS`       | `1000`            | global    | no       | **Máximo de Solicitudes Bloqueadas:** Número máximo de solicitudes bloqueadas para almacenar por trabajador.                                       |
| `METRICS_MAX_BLOCKED_REQUESTS_REDIS` | `100000`          | global    | no       | **Máximo de Solicitudes Bloqueadas en Redis:** Número máximo de solicitudes bloqueadas para almacenar en Redis.                                    |
| `METRICS_SAVE_TO_REDIS`              | `yes`             | global    | no       | **Guardar Métricas en Redis:** Establezca en `yes` para guardar las métricas (contadores y tablas) en Redis para la agregación en todo el clúster. |

!!! tip "Dimensionamiento de la Asignación de Memoria"
El ajuste `METRICS_MEMORY_SIZE` debe ajustarse en función de su volumen de tráfico y el número de instancias. Para sitios de alto tráfico, considere aumentar este valor para garantizar que todas las métricas se capturen sin pérdida de datos.

!!! info "Integración con Redis"
Cuando BunkerWeb está configurado para usar [Redis](#redis), el complemento de métricas sincronizará automáticamente los datos de las solicitudes bloqueadas con el servidor Redis. Esto proporciona una vista centralizada de los eventos de seguridad en múltiples instancias de BunkerWeb.

!!! warning "Consideraciones de Rendimiento"
Establecer valores muy altos para `METRICS_MAX_BLOCKED_REQUESTS` o `METRICS_MAX_BLOCKED_REQUESTS_REDIS` puede aumentar el uso de la memoria. Supervise los recursos de su sistema y ajuste estos valores según sus necesidades reales y los recursos disponibles.

!!! note "Almacenamiento Específico del Trabajador"
Cada trabajador de NGINX mantiene sus propias métricas en la memoria. Al acceder a las métricas a través de la API, los datos de todos los trabajadores se agregan automáticamente para proporcionar una vista completa.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Configuración predeterminada adecuada para la mayoría de las implementaciones:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "16m"
    METRICS_MAX_BLOCKED_REQUESTS: "1000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "100000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Entorno de Bajos Recursos"

    Configuración optimizada para entornos con recursos limitados:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "8m"
    METRICS_MAX_BLOCKED_REQUESTS: "500"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "10000"
    METRICS_SAVE_TO_REDIS: "no"
    ```

=== "Entorno de Alto Tráfico"

    Configuración para sitios web de alto tráfico que necesitan rastrear más eventos de seguridad:

    ```yaml
    USE_METRICS: "yes"
    METRICS_MEMORY_SIZE: "64m"
    METRICS_MAX_BLOCKED_REQUESTS: "5000"
    METRICS_MAX_BLOCKED_REQUESTS_REDIS: "500000"
    METRICS_SAVE_TO_REDIS: "yes"
    ```

=== "Métricas Deshabilitadas"

    Configuración con la recolección de métricas deshabilitada:

    ```yaml
    USE_METRICS: "no"
    ```
