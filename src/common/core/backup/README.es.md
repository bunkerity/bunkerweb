El complemento de copia de seguridad proporciona una solución de respaldo automatizada para proteger sus datos de BunkerWeb. Esta función garantiza la seguridad y disponibilidad de su importante base de datos mediante la creación de copias de seguridad periódicas según el cronograma que prefiera. Las copias de seguridad se almacenan en una ubicación designada y se pueden gestionar fácilmente a través de procesos automatizados y comandos manuales.

**Cómo funciona:**

1.  Su base de datos se respalda automáticamente según el cronograma que establezca (diario, semanal o mensual).
2.  Las copias de seguridad se almacenan en un directorio específico de su sistema.
3.  Las copias de seguridad antiguas se rotan automáticamente según su configuración de retención.
4.  Puede crear copias de seguridad manualmente, enumerar las copias de seguridad existentes o restaurar desde una copia de seguridad en cualquier momento.
5.  Antes de cualquier operación de restauración, el estado actual se respalda automáticamente como medida de seguridad.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de copia de seguridad:

1.  **Habilite la función:** La función de copia de seguridad está habilitada por defecto. Si es necesario, puede controlarla con el ajuste `USE_BACKUP`.
2.  **Configure el cronograma de copia de seguridad:** Elija la frecuencia con la que deben realizarse las copias de seguridad estableciendo el parámetro `BACKUP_SCHEDULE`.
3.  **Establezca la política de retención:** Especifique cuántas copias de seguridad conservar utilizando el ajuste `BACKUP_ROTATION`.
4.  **Defina la ubicación de almacenamiento:** Elija dónde se almacenarán las copias de seguridad utilizando el ajuste `BACKUP_DIRECTORY`.
5.  **Use los comandos de la CLI:** Gestione las copias de seguridad manualmente con los comandos `bwcli plugin backup` cuando sea necesario.

### Ajustes de configuración

| Ajuste             | Valor por defecto            | Contexto | Múltiple | Descripción                                                                                                                                                                                   |
| ------------------ | ---------------------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | no       | **Habilitar copia de seguridad:** Establezca en `yes` para habilitar las copias de seguridad automáticas.                                                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | no       | **Frecuencia de la copia de seguridad:** Con qué frecuencia se realizan las copias de seguridad. Opciones: `daily`, `weekly` o `monthly`.                                                     |
| `BACKUP_ROTATION`  | `7`                          | global   | no       | **Retención de copias de seguridad:** El número de archivos de copia de seguridad que se deben conservar. Las copias de seguridad más antiguas que este número se eliminarán automáticamente. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | no       | **Ubicación de la copia de seguridad:** El directorio donde se almacenarán los archivos de copia de seguridad.                                                                                |

### Interfaz de línea de comandos

El complemento de copia de seguridad proporciona varios comandos de la CLI para gestionar sus copias de seguridad:

```bash
# Listar todas las copias de seguridad disponibles
bwcli plugin backup list

# Crear una copia de seguridad manual
bwcli plugin backup save

# Crear una copia de seguridad en una ubicación personalizada
bwcli plugin backup save --directory /ruta/a/ubicacion/personalizada

# Restaurar desde la copia de seguridad más reciente
bwcli plugin backup restore

# Restaurar desde un archivo de copia de seguridad específico
bwcli plugin backup restore /ruta/a/copia/de/seguridad/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "La seguridad es lo primero"
Antes de cualquier operación de restauración, el complemento de copia de seguridad crea automáticamente una copia de seguridad del estado actual de su base de datos en una ubicación temporal. Esto proporciona una protección adicional en caso de que necesite revertir la operación de restauración.

!!! warning "Compatibilidad de la base de datos"
El complemento de copia de seguridad es compatible con las bases de datos SQLite, MySQL/MariaDB y PostgreSQL. Las bases de datos de Oracle no son compatibles actualmente para las operaciones de copia de seguridad y restauración.

### Configuraciones de ejemplo

=== "Copias de seguridad diarias con retención de 7 días"

    Configuración por defecto que crea copias de seguridad diarias y conserva los 7 archivos más recientes:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias de seguridad semanales con retención extendida"

    Configuración para copias de seguridad menos frecuentes con una retención más prolongada:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias de seguridad mensuales en una ubicación personalizada"

    Configuración para copias de seguridad mensuales almacenadas en una ubicación personalizada:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
