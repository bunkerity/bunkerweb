El complemento de Base de Datos proporciona una integración robusta de base de datos para BunkerWeb al habilitar el almacenamiento y la gestión centralizados de datos de configuración, registros y otra información esencial.

Este componente principal admite múltiples motores de base de datos, incluidos SQLite, PostgreSQL, MySQL/MariaDB y Oracle, lo que le permite elegir la solución de base de datos que mejor se adapte a su entorno y requisitos.

**Cómo funciona:**

1.  BunkerWeb se conecta a su base de datos configurada utilizando el URI proporcionado en el formato SQLAlchemy.
2.  Los datos críticos de configuración, la información en tiempo de ejecución y los registros de trabajos se almacenan de forma segura en la base de datos.
3.  Los procesos de mantenimiento automático optimizan su base de datos al gestionar el crecimiento de los datos y limpiar los registros sobrantes.
4.  Para escenarios de alta disponibilidad, puede configurar un URI de base de datos de solo lectura que sirva tanto como respaldo (failover) como método para descargar las operaciones de lectura.
5.  Las operaciones de la base de datos se registran según el nivel de registro especificado, proporcionando una visibilidad adecuada de las interacciones con la base de datos.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de Base de Datos:

1.  **Elija un motor de base de datos:** Seleccione entre SQLite (predeterminado), PostgreSQL, MySQL/MariaDB u Oracle según sus requisitos.
2.  **Configure el URI de la base de datos:** Establezca el `DATABASE_URI` para conectarse a su base de datos principal utilizando el formato SQLAlchemy.
3.  **Base de datos de solo lectura opcional:** Para configuraciones de alta disponibilidad, configure un `DATABASE_URI_READONLY` como respaldo o para operaciones de lectura.

### Ajustes de Configuración

| Ajuste                          | Valor por defecto                         | Contexto | Múltiple | Descripción                                                                                                                                                           |
| ------------------------------- | ----------------------------------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URI`                    | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global   | no       | **URI de la Base de Datos:** La cadena de conexión de la base de datos principal en formato SQLAlchemy.                                                                                              |
| `DATABASE_URI_READONLY`           |                                           | global   | no       | **URI de Solo Lectura:** Base de datos opcional para operaciones de solo lectura o como respaldo si la principal está caída.                                                                         |
| `DATABASE_LOG_LEVEL`              | `warning`                                 | global   | no       | **Nivel de Registro:** El nivel de verbosidad para los registros de la base de datos. Opciones: `debug`, `info`, `warn`, `warning` o `error`.                                                       |
| `DATABASE_MAX_JOBS_RUNS`          | `10000`                                   | global   | no       | **Máximo de Ejecuciones:** El número máximo de registros de ejecución de trabajos a conservar antes de la limpieza automática.                                                                       |
| `DATABASE_MAX_SESSION_AGE_DAYS`   | `14`                                      | global   | no       | **Retención de Sesiones:** La edad máxima (en días) de las sesiones de usuarios de la UI antes de que se purguen automáticamente.                                                                    |
| `DATABASE_POOL_SIZE`              | `40`                                      | global   | no       | **Tamaño del Pool:** El número de conexiones a mantener en el pool de conexiones de la base de datos.                                                                                                |
| `DATABASE_POOL_MAX_OVERFLOW`      | `20`                                      | global   | no       | **Desbordamiento Máximo del Pool:** El número máximo de conexiones adicionales por encima del tamaño del pool. `-1` para ilimitado.                                                                  |
| `DATABASE_POOL_TIMEOUT`           | `5`                                       | global   | no       | **Tiempo de Espera del Pool:** El número de segundos a esperar antes de abandonar la obtención de una conexión del pool.                                                                             |
| `DATABASE_POOL_RECYCLE`           | `1800`                                    | global   | no       | **Reciclaje del Pool:** El número de segundos tras los cuales una conexión se recicla automáticamente. `-1` para desactivar.                                                                         |
| `DATABASE_POOL_PRE_PING`          | `yes`                                     | global   | no       | **Pre-Ping del Pool:** Si se prueba la conexión al extraerla del pool.                                                                                                                               |
| `DATABASE_POOL_RESET_ON_RETURN`   |                                           | global   | no       | **Reinicio al Devolver:** Cómo se reinician las conexiones al devolverlas al pool. Vacío = auto (`none` para MySQL/MariaDB, `rollback` para otros). Opciones: `rollback`, `commit`, `none`.          |
| `DATABASE_RETRY_TIMEOUT`          | `60`                                      | global   | no       | **Tiempo de Reintento:** El número máximo de segundos a esperar la disponibilidad de la base de datos al iniciar.                                                                                    |
| `DATABASE_REQUEST_RETRY_ATTEMPTS` | `2`                                       | global   | no       | **Intentos de Reintento:** El número de reintentos en caso de errores transitorios durante las operaciones.                                                                                          |
| `DATABASE_REQUEST_RETRY_DELAY`    | `0.25`                                    | global   | no       | **Retraso entre Reintentos:** El retraso en segundos entre reintentos en caso de errores transitorios.                                                                                               |

!!! tip "Selección de Base de Datos" - **SQLite** (predeterminado): Ideal para implementaciones de un solo nodo o entornos de prueba debido a su simplicidad y naturaleza basada en archivos. - **PostgreSQL**: Recomendado para entornos de producción con múltiples instancias de BunkerWeb debido a su robustez y soporte de concurrencia. - **MySQL/MariaDB**: Una buena alternativa a PostgreSQL con capacidades similares de nivel de producción. - **Oracle**: Adecuado para entornos empresariales donde Oracle ya es la plataforma de base de datos estándar.

!!! info "Formato de URI de SQLAlchemy"
    El URI de la base de datos sigue el formato de SQLAlchemy:

    -   SQLite: `sqlite:////ruta/a/database.sqlite3`
    -   PostgreSQL: `postgresql://usuario:contraseña@hostname:puerto/basededatos`
    -   MySQL/MariaDB: `mysql://usuario:contraseña@hostname:puerto/basededatos` o `mariadb://usuario:contraseña@hostname:puerto/basededatos`
    -   Oracle: `oracle://usuario:contraseña@hostname:puerto/basededatos`

!!! warning "Mantenimiento de la Base de Datos"
    El complemento ejecuta automáticamente trabajos de mantenimiento diarios:

- **Limpiar Ejecuciones de Trabajos en Exceso:** Purga el historial que supera el límite `DATABASE_MAX_JOBS_RUNS`.
- **Limpiar Sesiones de UI Caducadas:** Elimina las sesiones de usuarios de la UI que superan `DATABASE_MAX_SESSION_AGE_DAYS`.

Estas tareas evitan el crecimiento ilimitado de la base de datos mientras conservan un historial operativo útil.
