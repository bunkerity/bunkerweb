El complemento de copia de seguridad proporciona una solución de respaldo automatizada para proteger sus datos de BunkerWeb. Esta función garantiza la seguridad y disponibilidad de su importante base de datos mediante la creación de copias de seguridad periódicas según el cronograma que prefiera. Las copias de seguridad se almacenan en una ubicación designada y se pueden gestionar fácilmente a través de procesos automatizados y comandos manuales.

**Cómo funciona:**

1.  Su base de datos se respalda automáticamente según el cronograma que establezca (`daily`, `weekly`, `monthly` o `hanoi`).
2.  Las copias de seguridad se almacenan en un directorio específico de su sistema.
3.  Antes de cada copia de seguridad se verifica el espacio libre en disco disponible.
4.  Cada ZIP contiene el volcado SQL y un archivo de suma de verificación SHA-256 (`.sha256`) para verificar la integridad.
5.  Las copias de seguridad antiguas se rotan automáticamente. El modo `hanoi` aplica la rotación Torres de Hanói (24 archivos, ~85 días de cobertura).
6.  Al restaurar, la suma de verificación se comprueba antes de modificar la base de datos activa.
7.  Puede crear, listar, verificar y restaurar copias de seguridad manualmente en cualquier momento.
8.  Antes de cualquier operación de restauración, el estado actual se respalda automáticamente como medida de seguridad.

### Cómo usar

1.  **Habilite la función:** La función de copia de seguridad está habilitada por defecto. Si es necesario, puede controlarla con el ajuste `USE_BACKUP`.
2.  **Configure el cronograma:** Elija la frecuencia con la que deben realizarse las copias de seguridad estableciendo el parámetro `BACKUP_SCHEDULE`.
3.  **Establezca la política de retención:** Especifique cuántas copias conservar con `BACKUP_ROTATION` (se ignora si `BACKUP_SCHEDULE=hanoi`).
4.  **Defina la ubicación:** Elija dónde se almacenarán las copias con `BACKUP_DIRECTORY`.
5.  **Use los comandos de la CLI:** Gestione las copias manualmente con los comandos `bwcli plugin backup`.

### Ajustes de configuración

| Ajuste             | Valor por defecto            | Contexto | Múltiple | Descripción                                                                                                                                                              |
| ------------------ | ---------------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `USE_BACKUP`       | `yes`                        | global   | no       | **Habilitar copia de seguridad:** Establezca en `yes` para habilitar las copias automáticas.                                                                             |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | no       | **Frecuencia:** `daily`, `weekly`, `monthly` o `hanoi` (horaria con rotación Torres de Hanói, ~85 días de cobertura).                                                   |
| `BACKUP_ROTATION`  | `7`                          | global   | no       | **Retención:** Número de archivos a conservar. Se ignora con `hanoi` (la rotación se gestiona automáticamente).                                                          |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | no       | **Ubicación:** El directorio donde se almacenarán los archivos de copia de seguridad.                                                                                    |
| `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE` | `no` | global | no | **Ignorar error de suma de verificación:** Si `yes`, un error SHA-256 no cancelará la restauración. Úselo solo como último recurso para backups parcialmente corruptos. |

### Interfaz de línea de comandos

```bash
# Listar todas las copias de seguridad disponibles
bwcli plugin backup list

# Verificar las sumas SHA-256 de todas las copias
bwcli plugin backup check

# Crear una copia de seguridad manual
bwcli plugin backup save

# Crear una copia en una ubicación personalizada
bwcli plugin backup save --directory /ruta/a/ubicacion/personalizada

# Restaurar desde la copia más reciente
bwcli plugin backup restore

# Restaurar desde un archivo específico
bwcli plugin backup restore /ruta/a/copia/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "La seguridad es lo primero"
    Antes de cualquier restauración, el complemento crea automáticamente una copia del estado actual en una ubicación temporal.

!!! info "Verificación de integridad"
    Cada ZIP contiene un archivo SHA-256. La suma se verifica automáticamente antes de cualquier restauración. Use `bwcli plugin backup check` para comprobar todas las copias en cualquier momento.

!!! warning "Compatibilidad de la base de datos"
    El complemento es compatible con SQLite, MySQL/MariaDB y PostgreSQL. Las bases de datos Oracle no son compatibles actualmente.

### Configuraciones de ejemplo

=== "Copias diarias con retención de 7 días"

    Configuración por defecto:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Torres de Hanói (~85 días)"

    Ejecución horaria con rotación Torres de Hanói. Conserva 24 archivos con ~85 días de cobertura. `BACKUP_ROTATION` se ignora:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "hanoi"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias semanales con retención extendida"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias mensuales en ubicación personalizada"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
