El complemento Redis integra [Redis](https://redis.io/) o [Valkey](https://valkey.io/) en BunkerWeb para el almacenamiento en caché y la recuperación rápida de datos. Esta función es esencial para implementar BunkerWeb en entornos de alta disponibilidad donde los datos de sesión, las métricas y otra información compartida deben ser accesibles a través de múltiples nodos.

**Cómo funciona:**

1.  Cuando está habilitado, BunkerWeb establece una conexión con su servidor Redis o Valkey configurado.
2.  Los datos críticos como la información de la sesión, las métricas y los datos relacionados con la seguridad se almacenan en Redis/Valkey.
3.  Múltiples instancias de BunkerWeb pueden compartir estos datos, lo que permite la agrupación en clúster y el equilibrio de carga sin problemas.
4.  El complemento admite varias opciones de implementación de Redis/Valkey, incluidos servidores independientes, autenticación con contraseña, cifrado SSL/TLS y Redis Sentinel para alta disponibilidad.
5.  La reconexión automática y los tiempos de espera configurables garantizan la solidez en los entornos de producción.

### Cómo usar

Siga estos pasos para configurar y usar el complemento de Redis:

1.  **Habilite la función:** Establezca el ajuste `USE_REDIS` en `yes` para habilitar la integración de Redis/Valkey.
2.  **Configure los detalles de la conexión:** Especifique el nombre de host/dirección IP y el puerto de su servidor Redis/Valkey.
3.  **Establezca las opciones de seguridad:** Configure las credenciales de autenticación si su servidor Redis/Valkey las requiere.
4.  **Configure las opciones avanzadas:** Establezca la selección de la base de datos, las opciones de SSL y los tiempos de espera según sea necesario.
5.  **Para alta disponibilidad,** configure los ajustes de Sentinel si está utilizando Redis Sentinel.

### Ajustes de Configuración

| Ajuste                    | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                             |
| ------------------------- | ----------------- | -------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `USE_REDIS`               | `no`              | global   | no       | **Habilitar Redis:** Establezca en `yes` para habilitar la integración de Redis/Valkey para el modo de clúster.         |
| `REDIS_HOST`              |                   | global   | no       | **Servidor Redis/Valkey:** Dirección IP o nombre de host del servidor Redis/Valkey.                                     |
| `REDIS_PORT`              | `6379`            | global   | no       | **Puerto Redis/Valkey:** Número de puerto del servidor Redis/Valkey.                                                    |
| `REDIS_DATABASE`          | `0`               | global   | no       | **Base de datos Redis/Valkey:** Número de base de datos a utilizar en el servidor Redis/Valkey (0-15).                  |
| `REDIS_SSL`               | `no`              | global   | no       | **SSL de Redis/Valkey:** Establezca en `yes` para habilitar el cifrado SSL/TLS para la conexión de Redis/Valkey.        |
| `REDIS_SSL_VERIFY`        | `yes`             | global   | no       | **Verificación SSL de Redis/Valkey:** Establezca en `yes` para verificar el certificado SSL del servidor Redis/Valkey.  |
| `REDIS_TIMEOUT`           | `5`               | global   | no       | **Tiempo de espera de Redis/Valkey:** Tiempo de espera de la conexión en segundos para las operaciones de Redis/Valkey. |
| `REDIS_USERNAME`          |                   | global   | no       | **Nombre de usuario de Redis/Valkey:** Nombre de usuario para la autenticación de Redis/Valkey (Redis 6.0+).            |
| `REDIS_PASSWORD`          |                   | global   | no       | **Contraseña de Redis/Valkey:** Contraseña para la autenticación de Redis/Valkey.                                       |
| `REDIS_SENTINEL_HOSTS`    |                   | global   | no       | **Hosts de Sentinel:** Lista de hosts de Redis Sentinel separados por espacios (nombredehost:puerto).                   |
| `REDIS_SENTINEL_USERNAME` |                   | global   | no       | **Nombre de usuario de Sentinel:** Nombre de usuario para la autenticación de Redis Sentinel.                           |
| `REDIS_SENTINEL_PASSWORD` |                   | global   | no       | **Contraseña de Sentinel:** Contraseña para la autenticación de Redis Sentinel.                                         |
| `REDIS_SENTINEL_MASTER`   | `mymaster`        | global   | no       | **Maestro de Sentinel:** Nombre del maestro en la configuración de Redis Sentinel.                                      |
| `REDIS_KEEPALIVE_IDLE`    | `300`             | global   | no       | **Tiempo de inactividad de keepalive:** Tiempo (en segundos) entre las sondas TCP keepalive para conexiones inactivas.  |
| `REDIS_KEEPALIVE_POOL`    | `3`               | global   | no       | **Grupo de keepalive:** Número máximo de conexiones de Redis/Valkey mantenidas en el grupo.                             |

!!! tip "Alta Disponibilidad con Redis Sentinel"
    Para entornos de producción que requieren alta disponibilidad, configure los ajustes de Redis Sentinel. Esto proporciona capacidades de conmutación por error automática si el servidor Redis principal deja de estar disponible.

!!! warning "Consideraciones de Seguridad"
    Cuando utilice Redis en producción:

    -   Establezca siempre contraseñas seguras tanto para la autenticación de Redis como de Sentinel
    -   Considere habilitar el cifrado SSL/TLS para las conexiones de Redis
    -   Asegúrese de que su servidor Redis no esté expuesto a la Internet pública
    -   Restrinja el acceso al puerto de Redis mediante cortafuegos o segmentación de red

!!! info "Requisitos del Clúster"
    Al implementar BunkerWeb en un clúster:

    -   Todas las instancias de BunkerWeb deben conectarse al mismo servidor Redis o Valkey o al clúster de Sentinel
    -   Configure el mismo número de base de datos en todas las instancias
    -   Asegúrese de que haya conectividad de red entre todas las instancias de BunkerWeb y los servidores Redis/Valkey

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para conectarse a un servidor Redis o Valkey en la máquina local:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "localhost"
    REDIS_PORT: "6379"
    ```

=== "Configuración Segura"

    Configuración con autenticación por contraseña y SSL habilitado:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_SSL: "yes"
    REDIS_SSL_VERIFY: "yes"
    ```

=== "Configuración de Redis Sentinel"

    Configuración para alta disponibilidad utilizando Redis Sentinel:

    ```yaml
    USE_REDIS: "yes"
    REDIS_SENTINEL_HOSTS: "sentinel1:26379 sentinel2:26379 sentinel3:26379"
    REDIS_SENTINEL_MASTER: "mymaster"
    REDIS_SENTINEL_PASSWORD: "sentinel-password"
    REDIS_PASSWORD: "redis-password"
    ```

=== "Ajuste Avanzado"

    Configuración con parámetros de conexión avanzados para la optimización del rendimiento:

    ```yaml
    USE_REDIS: "yes"
    REDIS_HOST: "redis.example.com"
    REDIS_PORT: "6379"
    REDIS_PASSWORD: "your-strong-password"
    REDIS_DATABASE: "3"
    REDIS_TIMEOUT: "3"
    REDIS_KEEPALIVE_IDLE: "60"
    REDIS_KEEPALIVE_POOL: "5"
    ```

### Mejores Prácticas de Redis

Cuando utilice Redis o Valkey con BunkerWeb, considere estas mejores prácticas para garantizar un rendimiento, seguridad y fiabilidad óptimos:

#### Gestión de la Memoria

- **Supervise el uso de la memoria:** Configure Redis con los ajustes `maxmemory` apropiados para evitar errores de falta de memoria
- **Establezca una política de desalojo:** Utilice `maxmemory-policy` (p. ej., `volatile-lru` o `allkeys-lru`) apropiada para su caso de uso
- **Evite claves grandes:** Asegúrese de que las claves individuales de Redis se mantengan en un tamaño razonable para evitar la degradación del rendimiento

#### Persistencia de Datos

- **Habilite las instantáneas RDB:** Configure instantáneas periódicas para la persistencia de datos sin un impacto significativo en el rendimiento
- **Considere AOF:** Para datos críticos, habilite la persistencia AOF (Append-Only File) con una política de `fsync` apropiada
- **Estrategia de copia de seguridad:** Implemente copias de seguridad regulares de Redis como parte de su plan de recuperación de desastres

#### Optimización del Rendimiento

- **Agrupación de conexiones:** BunkerWeb ya implementa esto, pero asegúrese de que otras aplicaciones sigan esta práctica
- **Canalización:** Cuando sea posible, utilice la canalización para operaciones masivas para reducir la sobrecarga de la red
- **Evite operaciones costosas:** Tenga cuidado con comandos como `KEYS` en entornos de producción
- **Compare su carga de trabajo:** Utilice `redis-benchmark` para probar sus patrones de carga de trabajo específicos

### Recursos Adicionales

- [Documentación de Redis](https://redis.io/documentation)
- [Guía de Seguridad de Redis](https://redis.io/topics/security)
- [Alta Disponibilidad de Redis](https://redis.io/topics/sentinel)
- [Persistencia de Redis](https://redis.io/topics/persistence)
