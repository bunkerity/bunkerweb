El complemento de Mal Comportamiento protege su sitio web al detectar y bloquear automáticamente las direcciones IP que generan demasiados errores o códigos de estado HTTP "malos" dentro de un período de tiempo específico. Esto ayuda a defenderse contra ataques de fuerza bruta, raspadores web, escáneres de vulnerabilidades y otras actividades maliciosas que podrían generar numerosas respuestas de error.

Los atacantes a menudo generan códigos de estado HTTP "sospechosos" al sondear o explotar vulnerabilidades, códigos que un usuario típico es poco probable que active en un período de tiempo determinado. Al detectar este comportamiento, BunkerWeb puede bloquear automáticamente la dirección IP infractora, obligando al atacante a usar una nueva dirección IP para continuar sus intentos.

**Cómo funciona:**

1.  El complemento supervisa las respuestas HTTP de su sitio.
2.  Cuando un visitante recibe un código de estado HTTP "malo" (como 400, 401, 403, 404, etc.), el contador para esa dirección IP se incrementa.
3.  Si una dirección IP excede el umbral configurado de códigos de estado malos dentro del período de tiempo especificado, la IP se bloquea automáticamente.
4.  Las IP bloqueadas pueden ser bloqueadas a nivel de servicio (solo para el sitio específico) o globalmente (en todos los sitios), dependiendo de su configuración.
5.  Los bloqueos expiran automáticamente después de la duración de bloqueo configurada, o permanecen permanentes si se configuran con `0`.

!!! success "Beneficios clave"

    1.  **Protección automática:** Detecta y bloquea clientes potencialmente maliciosos sin requerir intervención manual.
    2.  **Reglas personalizables:** Ajuste con precisión lo que constituye un "mal comportamiento" según sus necesidades específicas.
    3.  **Conservación de recursos:** Evita que los actores maliciosos consuman recursos del servidor con repetidas solicitudes no válidas.
    4.  **Ámbito flexible:** Elija si los bloqueos deben aplicarse solo al servicio actual o globalmente a todos los servicios.
    5.  **Control de la duración del bloqueo:** Establezca bloqueos temporales que expiran automáticamente después de la duración configurada, o bloqueos permanentes que permanecen hasta que se eliminan manualmente.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Mal Comportamiento:

1.  **Habilite la función:** La función de Mal Comportamiento está habilitada por defecto. Si es necesario, puede controlarla con la configuración `USE_BAD_BEHAVIOR`.
2.  **Configure los códigos de estado:** Defina qué códigos de estado HTTP deben considerarse "malos" utilizando la configuración `BAD_BEHAVIOR_STATUS_CODES`.
3.  **Establezca los valores de umbral:** Determine cuántas respuestas "malas" deben desencadenar un bloqueo utilizando la configuración `BAD_BEHAVIOR_THRESHOLD`.
4.  **Configure los períodos de tiempo:** Especifique la duración para contar las respuestas malas y la duración del bloqueo utilizando las configuraciones `BAD_BEHAVIOR_COUNT_TIME` y `BAD_BEHAVIOR_BAN_TIME`.
5.  **Elija el ámbito del bloqueo:** Decida si los bloqueos deben aplicarse solo al servicio actual o globalmente a todos los servicios utilizando la configuración `BAD_BEHAVIOR_BAN_SCOPE`.

!!! tip "Modo Stream"
En **modo stream**, solo el código de estado `444` se considera "malo" y activará este comportamiento.

### Ajustes de configuración

| Ajuste                      | Valor por defecto             | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                           |
| --------------------------- | ----------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | no       | **Habilitar Mal Comportamiento:** Establezca en `yes` para habilitar la función de detección y bloqueo de mal comportamiento.                                                                                                         |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | no       | **Códigos de estado malos:** Lista de códigos de estado HTTP que se contarán como comportamiento "malo" cuando se devuelvan a un cliente.                                                                                             |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | no       | **Umbral:** El número de códigos de estado "malos" que una IP puede generar dentro del período de conteo antes de ser bloqueada.                                                                                                      |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | no       | **Período de conteo:** La ventana de tiempo (en segundos) durante la cual se cuentan los códigos de estado malos para alcanzar el umbral.                                                                                             |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | no       | **Duración del bloqueo:** Cuánto tiempo (en segundos) permanecerá bloqueada una IP después de exceder el umbral. El valor por defecto es de 24 horas (86400 segundos). Establezca en `0` para bloqueos permanentes que nunca expiran. |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | no       | **Ámbito del bloqueo:** Determina si los bloqueos se aplican solo al servicio actual (`service`) o a todos los servicios (`global`).                                                                                                  |

!!! warning "Falsos positivos"
Tenga cuidado al establecer el umbral y el tiempo de conteo. Establecer estos valores demasiado bajos puede bloquear inadvertidamente a usuarios legítimos que encuentren errores mientras navegan por su sitio.

!!! tip "Ajuste de su configuración"
Comience con configuraciones conservadoras (umbral más alto, tiempo de bloqueo más corto) y ajústelas según sus necesidades específicas y patrones de tráfico. Supervise sus registros para asegurarse de que los usuarios legítimos no sean bloqueados por error.

### Configuraciones de ejemplo

=== "Configuración por defecto"

    La configuración por defecto proporciona un enfoque equilibrado adecuado para la mayoría de los sitios web:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Configuración estricta"

    Para aplicaciones de alta seguridad donde se desea ser más agresivo al bloquear amenazas potenciales:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 días
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Bloquear en todos los servicios
    ```

=== "Configuración permisiva"

    Para sitios con alto tráfico legítimo donde se desea evitar falsos positivos:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Solo contar no autorizados, prohibidos y con límite de velocidad
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 hora
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Configuración de bloqueo permanente"

    Para escenarios donde desea que los atacantes detectados sean bloqueados permanentemente hasta que se desbloqueen manualmente:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Bloqueo permanente (nunca expira)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Bloquear en todos los servicios
    ```
