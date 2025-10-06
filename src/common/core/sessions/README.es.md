El complemento de Sesiones proporciona una gestión robusta de sesiones HTTP para BunkerWeb, lo que permite un seguimiento seguro y confiable de las sesiones de usuario entre solicitudes. Esta característica principal es esencial para mantener el estado del usuario, la persistencia de la autenticación y admitir otras funciones que requieren continuidad de la identidad, como la protección [anti-bot](#antibot) y los sistemas de autenticación de usuarios.

**Cómo funciona:**

1.  Cuando un usuario interactúa por primera vez con su sitio web, BunkerWeb crea un identificador de sesión único.
2.  Este identificador se almacena de forma segura en una cookie en el navegador del usuario.
3.  En solicitudes posteriores, BunkerWeb recupera el identificador de sesión de la cookie y lo utiliza para acceder a los datos de la sesión del usuario.
4.  Los datos de la sesión se pueden almacenar localmente o en [Redis](#redis) para entornos distribuidos con múltiples instancias de BunkerWeb.
5.  Las sesiones se gestionan automáticamente con tiempos de espera configurables, lo que garantiza la seguridad y la facilidad de uso.
6.  La seguridad criptográfica de las sesiones se garantiza mediante una clave secreta que se utiliza para firmar las cookies de sesión.

### Cómo usar

Siga estos pasos para configurar y usar la función de Sesiones:

1.  **Configure la seguridad de la sesión:** Establezca un `SESSIONS_SECRET` fuerte y único para garantizar que las cookies de sesión no puedan ser falsificadas. (El valor predeterminado es "random", lo que hace que BunkerWeb genere una clave secreta aleatoria).
2.  **Elija un nombre de sesión:** Opcionalmente, personalice el `SESSIONS_NAME` para definir cómo se llamará su cookie de sesión en el navegador. (El valor predeterminado es "random", lo que hace que BunkerWeb genere un nombre aleatorio).
3.  **Establezca los tiempos de espera de la sesión:** Configure cuánto tiempo permanecen válidas las sesiones con los ajustes de tiempo de espera (`SESSIONS_IDLING_TIMEOUT`, `SESSIONS_ROLLING_TIMEOUT`, `SESSIONS_ABSOLUTE_TIMEOUT`).
4.  **Configure la integración con Redis:** Para entornos distribuidos, establezca `USE_REDIS` en "yes" y configure su [conexión Redis](#redis) para compartir los datos de la sesión entre múltiples nodos de BunkerWeb.
5.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, la gestión de sesiones se realiza automáticamente para su sitio web.

### Ajustes de Configuración

| Ajuste                      | Valor por defecto | Contexto | Múltiple | Descripción                                                                                                                                         |
| --------------------------- | ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SESSIONS_SECRET`           | `random`          | global   | no       | **Secreto de sesión:** Clave criptográfica utilizada para firmar las cookies de sesión. Debe ser una cadena fuerte y aleatoria única para su sitio. |
| `SESSIONS_NAME`             | `random`          | global   | no       | **Nombre de la cookie:** El nombre de la cookie que almacenará el identificador de sesión.                                                          |
| `SESSIONS_IDLING_TIMEOUT`   | `1800`            | global   | no       | **Tiempo de espera por inactividad:** Tiempo máximo (en segundos) de inactividad antes de que la sesión se invalide.                                |
| `SESSIONS_ROLLING_TIMEOUT`  | `3600`            | global   | no       | **Tiempo de espera renovable:** Tiempo máximo (en segundos) antes de que una sesión deba renovarse.                                                 |
| `SESSIONS_ABSOLUTE_TIMEOUT` | `86400`           | global   | no       | **Tiempo de espera absoluto:** Tiempo máximo (en segundos) antes de que una sesión se destruya independientemente de la actividad.                  |
| `SESSIONS_CHECK_IP`         | `yes`             | global   | no       | **Comprobar IP:** Cuando se establece en `yes`, destruye la sesión si la dirección IP del cliente cambia.                                           |
| `SESSIONS_CHECK_USER_AGENT` | `yes`             | global   | no       | **Comprobar User-Agent:** Cuando se establece en `yes`, destruye la sesión si el User-Agent del cliente cambia.                                     |

!!! warning "Consideraciones de Seguridad"
    El ajuste `SESSIONS_SECRET` es fundamental para la seguridad. En entornos de producción:

    1. Use un valor fuerte y aleatorio (al menos 32 caracteres)
    2. Mantenga este valor confidencial
    3. Use el mismo valor en todas las instancias de BunkerWeb en un clúster
    4. Considere usar variables de entorno o gestión de secretos para evitar almacenar esto en texto plano

!!! tip "Entornos en Clúster"
    Si está ejecutando múltiples instancias de BunkerWeb detrás de un balanceador de carga:

    1. Establezca `USE_REDIS` en `yes` y configure su conexión Redis
    2. Asegúrese de que todas las instancias usen exactamente el mismo `SESSIONS_SECRET` y `SESSIONS_NAME`
    3. Esto garantiza que los usuarios mantengan su sesión independientemente de qué instancia de BunkerWeb maneje sus solicitudes

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración simple para una única instancia de BunkerWeb:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesiondemicliente"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    ```

=== "Seguridad Mejorada"

    Configuración con ajustes de seguridad aumentados:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-muy-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesionsegura"
    SESSIONS_IDLING_TIMEOUT: "900"  # 15 minutos
    SESSIONS_ROLLING_TIMEOUT: "1800"  # 30 minutos
    SESSIONS_ABSOLUTE_TIMEOUT: "43200"  # 12 horas
    SESSIONS_CHECK_IP: "yes"
    SESSIONS_CHECK_USER_AGENT: "yes"
    ```

=== "Entorno en Clúster con Redis"

    Configuración para múltiples instancias de BunkerWeb que comparten datos de sesión:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesiondelcluster"
    SESSIONS_IDLING_TIMEOUT: "1800"
    SESSIONS_ROLLING_TIMEOUT: "3600"
    SESSIONS_ABSOLUTE_TIMEOUT: "86400"
    USE_REDIS: "yes"
    # Asegúrese de que la conexión a Redis esté configurada correctamente
    ```

=== "Sesiones de Larga Duración"

    Configuración para aplicaciones que requieren persistencia de sesión extendida:

    ```yaml
    SESSIONS_SECRET: "su-clave-secreta-fuerte-y-aleatoria-aqui"
    SESSIONS_NAME: "sesionpersistente"
    SESSIONS_IDLING_TIMEOUT: "86400"  # 1 día
    SESSIONS_ROLLING_TIMEOUT: "172800"  # 2 días
    SESSIONS_ABSOLUTE_TIMEOUT: "604800"  # 7 días
    ```
