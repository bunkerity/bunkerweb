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
3.  **Establezca la política de retención:** Especifique cuántas copias de seguridad conservar utilizando el ajuste `BACKUP_ROTATION`. Cuáles se conservan lo decide `BACKUP_ROTATION_STRATEGY`, `hanoi` por defecto.
4.  **Defina la ubicación de almacenamiento:** Elija dónde se almacenarán las copias de seguridad utilizando el ajuste `BACKUP_DIRECTORY`.
5.  **Use los comandos de la CLI:** Gestione las copias de seguridad manualmente con los comandos `bwcli plugin backup` cuando sea necesario.

### Ajustes de configuración

| Ajuste             | Valor por defecto            | Contexto | Múltiple | Descripción                                                                                                                                                                                   |
| ------------------ | ---------------------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | no       | **Habilitar copia de seguridad:** Establezca en `yes` para habilitar las copias de seguridad automáticas.                                                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | no       | **Frecuencia de la copia de seguridad:** Con qué frecuencia se realizan las copias de seguridad. Opciones: `daily`, `weekly` o `monthly`.                                                     |
| `BACKUP_ROTATION`  | `7`                          | global   | no       | **Retención de copias de seguridad:** El número de archivos de copia de seguridad que se deben conservar. Las copias que excedan ese número se eliminan automáticamente. |
| `BACKUP_ROTATION_STRATEGY` | `hanoi`              | global   | no       | **Estrategia de rotación:** Cómo se eligen las copias de seguridad que se eliminan una vez alcanzado el límite. `hanoi` mantiene una escalera de las Torres de Hanói — fina cerca del presente, exponencialmente más gruesa hacia atrás; `fifo` conserva las más recientes. Ambas conservan el mismo número de archivos. |
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

    Una copia de seguridad solo puede restaurarse en el mismo motor de base de datos del que se tomó — el motor forma parte del nombre del archivo (`backup-mariadb-…`), y una restauración en otro distinto se rechaza antes de tocar nada. Si migró entre motores, ambos conjuntos de copias permanecen en el directorio: `restore` sin argumento toma el archivo más reciente de cualquier motor, así que indique la ruta explícitamente para restaurar una copia más antigua de su motor actual.

### Configuraciones de ejemplo

=== "Copias de seguridad diarias con retención de 7 archivos"

    Configuración por defecto: copias diarias, 7 archivos conservados, repartidos por la escalera de las Torres de Hanói.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Copias de seguridad diarias, últimos 7 días (FIFO)"

    El comportamiento anterior por defecto: los 7 archivos más recientes y nada más antiguo.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_ROTATION_STRATEGY: "fifo"
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

=== "Copias de seguridad diarias con una retención más profunda"

    24 archivos repartidos por la escalera por defecto en lugar de cubrir solo los últimos 24 días.
    Las copias más recientes se conservan con granularidad completa y las más antiguas se aclaran
    exponencialmente, de modo que el punto de restauración más antiguo retrocede cada vez que la
    instalación dobla su edad — un problema advertido tarde sigue siendo recuperable:

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "24"
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

!!! info "Qué copias de seguridad se conservan"
    `hanoi` es el valor por defecto. Ambas estrategias eliminan el mismo **número** de archivos —
    `hanoi` nunca elimina más copias de las que habría eliminado `fifo` — pero no eliminan las
    mismas, y la diferencia no está solo en el extremo antiguo. La escalera paga su profundidad
    aclarando también la ventana reciente: con un cronograma diario y el `BACKUP_ROTATION: "7"` por
    defecto, un archivo ya establecido conserva una copia de cada una de las ventanas de
    aproximadamente los últimos 1, 2, 4, 8, 16 y 32 días — edades de alrededor de 0, 1, 2–3, 4–7,
    8–15, 16–31 y 32–63 días, dependiendo las edades exactas de dónde caiga el día actual en la
    rejilla fija de la escalera — mientras que `fifo` conserva los últimos 7 días. **Se renuncia a
    tres o cuatro de los últimos siete días** a cambio de esos puntos de restauración más antiguos.
    La copia más reciente se conserva siempre; con una copia por día y un `BACKUP_ROTATION` de al
    menos 2, también los dos días más recientes. El intercambio es más suave cuanto mayor sea
    `BACKUP_ROTATION` — en `"24"` las últimas tres semanas aproximadamente siguen siendo contiguas,
    un intervalo que se reduce lentamente a medida que el archivo envejece.

    **Varias copias del mismo día cuentan como un único punto de restauración, y las sobrantes son
    los primeros archivos que una rotación abandona** — antes que cualquier cosa más antigua. Solo
    la copia más reciente de cada día sobrevive una vez agotado el presupuesto de archivos. Así, una
    copia manual tomada antes de un cambio arriesgado solo está a salvo hasta la siguiente copia de
    ese mismo día y, al convertirse en la más reciente del día, desplaza a la copia programada del
    día, que es entonces la que se elimina. Con `fifo` habría conservado ambas.

    Nada de lo que ya está en disco lo elimina la propia actualización — el cambio surte efecto en
    la siguiente rotación. Establezca `BACKUP_ROTATION_STRATEGY: "fifo"` para recuperar el
    comportamiento anterior. Cada eliminación se registra con el motivo por el que se eligió el
    archivo.

!!! info "Cómo se construye la escalera"
    La escalera cuenta en **periodos**, y un periodo es un `BACKUP_SCHEDULE`: un día para `daily`,
    siete para `weekly`, veintiocho (cuatro semanas, no un mes natural) para `monthly`. Todas las
    copias tomadas dentro de un mismo periodo son el mismo punto de restauración, y la más reciente
    de ellas es la que lo representa.

    `BACKUP_ROTATION` es a la vez el presupuesto de archivos y la profundidad de la escalera:
    construye `BACKUP_ROTATION - 1` niveles, donde el nivel `k` corta la línea temporal en bloques
    fijos de `2^k` periodos y conserva la copia más antigua de sus dos bloques no vacíos más
    recientes, con la copia más reciente siempre fijada por encima. Cada nivel cuesta como mucho un
    archivo más que el de debajo, de modo que toda la escalera cabe en el presupuesto — mientras su
    alcance se duplica en cada nivel. Sus bloques más profundos miden `2^(BACKUP_ROTATION - 2)`
    periodos, así que con un cronograma diario el punto de restauración más antiguo se sitúa entre
    **32 y 63 días** atrás con el `BACKUP_ROTATION: "7"` por defecto, y entre **1024 y 2047 días**
    en `"12"` — el número de archivos crece linealmente, la profundidad exponencialmente. Con el
    mismo presupuesto, `fifo` nunca llega más atrás de `BACKUP_ROTATION` periodos.

    Los bloques descansan sobre una rejilla absoluta y no sobre ventanas medidas desde hoy, y eso es
    lo que hace segura una eliminación: una copia que la escalera deja marchar no podrá volver a
    hacer falta, por lo que los niveles profundos no se vacían con el tiempo. También significa que
    la escalera **se va llenando a medida que el archivo envejece** — alcanzar el nivel `k` requiere
    `2^k` periodos, así que una instalación joven conserva todo lo que tiene y los puntos de
    restauración profundos aparecen con la edad. Hasta entonces, el presupuesto no gastado va a las
    copias más recientes, con granularidad completa.

!!! info "Cómo se fechan las copias de seguridad"
    La rotación lee la marca de tiempo del nombre de cada archivo. Un archivo cuyo nombre no lleve
    una utilizable — un fichero copiado a mano, o renombrado — se fecha por su hora de modificación,
    bajo ambas estrategias.
