El complemento ModSecurity integra el potente Firewall de Aplicaciones Web (WAF) [ModSecurity](https://modsecurity.org) en BunkerWeb. Esta integración ofrece una protección robusta contra una amplia gama de ataques web al aprovechar el [OWASP Core Rule Set (CRS)](https://coreruleset.org) para detectar y bloquear amenazas como la inyección de SQL, el cross-site scripting (XSS), la inclusión de archivos locales y más.

**Cómo funciona:**

1.  Cuando se recibe una solicitud, ModSecurity la evalúa con el conjunto de reglas activo.
2.  El OWASP Core Rule Set inspecciona las cabeceras, las cookies, los parámetros de la URL y el contenido del cuerpo.
3.  Cada violación detectada contribuye a una puntuación de anomalía general.
4.  Si esta puntuación excede el umbral configurado, la solicitud se bloquea.
5.  Se crean registros detallados para ayudar a diagnosticar qué reglas se activaron y por qué.

!!! success "Beneficios clave"

      1. **Protección estándar de la industria:** Utiliza el firewall de código abierto ModSecurity, ampliamente utilizado.
      2. **OWASP Core Rule Set:** Emplea reglas mantenidas por la comunidad que cubren el OWASP Top Ten y más.
      3. **Niveles de seguridad configurables:** Ajuste los niveles de paranoia para equilibrar la seguridad con los posibles falsos positivos.
      4. **Registro detallado:** Proporciona registros de auditoría exhaustivos para el análisis de ataques.
      5. **Soporte de complementos:** Amplíe la protección con complementos CRS opcionales adaptados a sus aplicaciones.

### Cómo usar

Siga estos pasos para configurar y usar ModSecurity:

1.  **Habilite la función:** ModSecurity está habilitado por defecto. Esto se puede controlar usando el ajuste `USE_MODSECURITY`.
2.  **Seleccione una versión de CRS:** Elija una versión del OWASP Core Rule Set (v3, v4 o nightly).
3.  **Añada complementos:** Opcionalmente, active los complementos de CRS para mejorar la cobertura de las reglas.
4.  **Supervise y ajuste:** Utilice los registros y la [interfaz de usuario web](web-ui.md) para identificar falsos positivos y ajustar la configuración.

### Ajustes de Configuración

| Ajuste                                | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                    |
| ------------------------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MODSECURITY`                     | `yes`             | multisite | no       | **Habilitar ModSecurity:** Active la protección del Firewall de Aplicaciones Web ModSecurity.                                                                                                                                                  |
| `USE_MODSECURITY_CRS`                 | `yes`             | multisite | no       | **Usar Core Rule Set:** Habilite el OWASP Core Rule Set para ModSecurity.                                                                                                                                                                      |
| `MODSECURITY_CRS_VERSION`             | `4`               | multisite | no       | **Versión de CRS:** La versión del OWASP Core Rule Set a utilizar. Opciones: `3`, `4` o `nightly`.                                                                                                                                             |
| `MODSECURITY_SEC_RULE_ENGINE`         | `On`              | multisite | no       | **Motor de Reglas:** Controle si se aplican las reglas. Opciones: `On`, `DetectionOnly` u `Off`.                                                                                                                                               |
| `MODSECURITY_SEC_AUDIT_ENGINE`        | `RelevantOnly`    | multisite | no       | **Motor de Auditoría:** Controle cómo funciona el registro de auditoría. Opciones: `On`, `Off` o `RelevantOnly`.                                                                                                                               |
| `MODSECURITY_SEC_AUDIT_LOG_PARTS`     | `ABIJDEFHZ`       | multisite | no       | **Partes del Registro de Auditoría:** Qué partes de las solicitudes/respuestas incluir en los registros de auditoría.                                                                                                                          |
| `MODSECURITY_REQ_BODY_NO_FILES_LIMIT` | `131072`          | multisite | no       | **Límite del Cuerpo de la Solicitud (Sin Archivos):** Tamaño máximo para los cuerpos de las solicitudes sin carga de archivos. Acepta bytes simples o sufijos legibles por humanos (`k`, `m`, `g`), por ejemplo, `131072`, `256k`, `1m`, `2g`. |
| `USE_MODSECURITY_CRS_PLUGINS`         | `yes`             | multisite | no       | **Habilitar Complementos de CRS:** Habilite conjuntos de reglas de complementos adicionales para el Core Rule Set.                                                                                                                             |
| `MODSECURITY_CRS_PLUGINS`             |                   | multisite | no       | **Lista de Complementos de CRS:** Lista de complementos separados por espacios para descargar e instalar (`nombre-plugin[/etiqueta]` o URL).                                                                                                   |
| `USE_MODSECURITY_GLOBAL_CRS`          | `no`              | global    | no       | **CRS Global:** Cuando está habilitado, aplica las reglas de CRS globalmente a nivel HTTP en lugar de por servidor.                                                                                                                            |

!!! warning "ModSecurity y el OWASP Core Rule Set"
    **Recomendamos encarecidamente mantener habilitados tanto ModSecurity como el OWASP Core Rule Set (CRS)** para proporcionar una protección robusta contra las vulnerabilidades web comunes. Aunque pueden ocurrir falsos positivos ocasionales, se pueden resolver con un poco de esfuerzo ajustando las reglas o utilizando exclusiones predefinidas.

    El equipo de CRS mantiene activamente una lista de exclusiones para aplicaciones populares como WordPress, Nextcloud, Drupal y Cpanel, lo que facilita la integración sin afectar la funcionalidad. Los beneficios de seguridad superan con creces el mínimo esfuerzo de configuración necesario para solucionar los falsos positivos.

### Versiones de CRS Disponibles

Seleccione una versión de CRS que se ajuste mejor a sus necesidades de seguridad:

- **`3`**: Estable [v3.3.8](https://github.com/coreruleset/coreruleset/releases/tag/v3.3.8).
- **`4`**: Estable [v4.22.0](https://github.com/coreruleset/coreruleset/releases/tag/v4.22.0) (**predeterminada**).
- **`nightly`**: [Compilación nocturna](https://github.com/coreruleset/coreruleset/releases/tag/nightly) que ofrece las últimas actualizaciones de reglas.

!!! example "Compilación Nocturna"
    La **compilación nocturna** contiene las reglas más actualizadas, ofreciendo las últimas protecciones contra amenazas emergentes. Sin embargo, dado que se actualiza diariamente y puede incluir cambios experimentales o no probados, se recomienda utilizar primero la compilación nocturna en un **entorno de preproducción** antes de implementarla en producción.

!!! tip "Niveles de Paranoia"
    El OWASP Core Rule Set utiliza "niveles de paranoia" (PL) para controlar la rigurosidad de las reglas:

    -   **PL1 (predeterminado):** Protección básica con mínimos falsos positivos
    -   **PL2:** Seguridad más estricta con una coincidencia de patrones más rigurosa
    -   **PL3:** Seguridad mejorada con una validación más estricta
    -   **PL4:** Máxima seguridad con reglas muy estrictas (puede causar muchos falsos positivos)

    Puede establecer el nivel de paranoia agregando un archivo de configuración personalizado en `/etc/bunkerweb/configs/modsec-crs/`.

### Configuraciones Personalizadas {#custom-configurations}

El ajuste de ModSecurity y el OWASP Core Rule Set (CRS) se puede lograr a través de configuraciones personalizadas. Estas configuraciones le permiten personalizar el comportamiento en etapas específicas del procesamiento de las reglas de seguridad:

- **`modsec-crs`**: Se aplica **antes** de que se cargue el OWASP Core Rule Set.
- **`modsec`**: Se aplica **después** de que se haya cargado el OWASP Core Rule Set. También se utiliza si el CRS no se carga en absoluto.
- **`crs-plugins-before`**: Se aplica **antes** de que se carguen los complementos de CRS.
- **`crs-plugins-after`**: Se aplica **después** de que se hayan cargado los complementos de CRS.

Esta estructura proporciona flexibilidad, permitiéndole ajustar la configuración de ModSecurity y CRS para adaptarse a las necesidades específicas de su aplicación mientras mantiene un flujo de configuración claro.

#### Agregar Exclusiones de CRS con `modsec-crs`

Puede usar una configuración personalizada de tipo `modsec-crs` para agregar exclusiones para casos de uso específicos, como habilitar exclusiones predefinidas para WordPress:

```conf
SecAction \
 "id:900130,\
  phase:1,\
  nolog,\
  pass,\
  t:none,\
  setvar:tx.crs_exclusions_wordpress=1"
```

En este ejemplo:

- La acción se ejecuta en la **Fase 1** (temprano en el ciclo de vida de la solicitud).
- Habilita las exclusiones de CRS específicas de WordPress estableciendo la variable `tx.crs_exclusions_wordpress`.

#### Actualizar las Reglas de CRS con `modsec`

Para ajustar las reglas de CRS cargadas, puede usar una configuración personalizada de tipo `modsec`. Por ejemplo, puede eliminar reglas o etiquetas específicas para ciertas rutas de solicitud:

```conf
SecRule REQUEST_FILENAME "/wp-admin/admin-ajax.php" "id:1,ctl:ruleRemoveByTag=attack-xss,ctl:ruleRemoveByTag=attack-rce"
SecRule REQUEST_FILENAME "/wp-admin/options.php" "id:2,ctl:ruleRemoveByTag=attack-xss"
SecRule REQUEST_FILENAME "^/wp-json/yoast" "id:3,ctl:ruleRemoveById=930120"
```

En este ejemplo:

- **Regla 1**: Elimina las reglas etiquetadas como `attack-xss` y `attack-rce` para las solicitudes a `/wp-admin/admin-ajax.php`.
- **Regla 2**: Elimina las reglas etiquetadas como `attack-xss` para las solicitudes a `/wp-admin/options.php`.
- **Regla 3**: Elimina una regla específica (ID `930120`) para las solicitudes que coinciden con `/wp-json/yoast`.

!!! info "Orden de ejecución"
    El orden de ejecución de ModSecurity en BunkerWeb es el siguiente, asegurando una progresión clara y lógica de la aplicación de reglas:

    1.  **Configuración de OWASP CRS**: Configuración base para el OWASP Core Rule Set.
    2.  **Configuración de Complementos Personalizados (`crs-plugins-before`)**: Ajustes específicos de los complementos, aplicados antes de cualquier regla de CRS.
    3.  **Reglas de Complementos Personalizados (Antes de las Reglas de CRS) (`crs-plugins-before`)**: Reglas personalizadas para los complementos ejecutadas antes de las reglas de CRS.
    4.  **Configuración de Complementos Descargados**: Configuración para los complementos descargados externamente.
    5.  **Reglas de Complementos Descargados (Antes de las Reglas de CRS)**: Reglas para los complementos descargados ejecutadas antes de las reglas de CRS.
    6.  **Reglas de CRS Personalizadas (`modsec-crs`)**: Reglas definidas por el usuario aplicadas antes de cargar las reglas de CRS.
    7.  **Reglas de OWASP CRS**: El conjunto principal de reglas de seguridad proporcionado por OWASP.
    8.  **Reglas de Complementos Personalizados (Después de las Reglas de CRS) (`crs-plugins-after`)**: Reglas de complementos personalizadas ejecutadas después de las reglas de CRS.
    9.  **Reglas de Complementos Descargados (Después de las Reglas de CRS)**: Reglas para los complementos descargados ejecutadas después de las reglas de CRS.
    10. **Reglas Personalizadas (`modsec`)**: Reglas definidas por el usuario aplicadas después de todas las reglas de CRS y de los complementos.

    **Notas Clave**:

    -   Las personalizaciones **pre-CRS** (`crs-plugins-before`, `modsec-crs`) le permiten definir excepciones o reglas preparatorias antes de que se carguen las reglas principales de CRS.
    -   Las personalizaciones **post-CRS** (`crs-plugins-after`, `modsec`) son ideales para anular o ampliar las reglas después de que se hayan aplicado las reglas de CRS y de los complementos.
    -   Esta estructura proporciona la máxima flexibilidad, permitiendo un control preciso sobre la ejecución y personalización de las reglas mientras se mantiene una sólida línea de base de seguridad.

### Complementos de OWASP CRS

El OWASP Core Rule Set también admite una gama de **complementos** diseñados para ampliar su funcionalidad y mejorar la compatibilidad con aplicaciones o entornos específicos. Estos complementos pueden ayudar a ajustar el CRS para su uso con plataformas populares como WordPress, Nextcloud y Drupal, o incluso con configuraciones personalizadas. Para obtener más información y una lista de los complementos disponibles, consulte el [registro de complementos de OWASP CRS](https://github.com/coreruleset/plugin-registry).

!!! tip "Descarga de complementos"
    El ajuste `MODSECURITY_CRS_PLUGINS` le permite descargar e instalar complementos para ampliar la funcionalidad del OWASP Core Rule Set (CRS). Este ajuste acepta una lista de nombres de complementos con etiquetas o URL opcionales, lo que facilita la integración de funciones de seguridad adicionales adaptadas a sus necesidades específicas.

    Aquí hay una lista no exhaustiva de valores aceptados para el ajuste `MODSECURITY_CRS_PLUGINS`:

    *   `fake-bot` - Descargar la última versión del complemento.
    *   `wordpress-rule-exclusions/v1.0.0` - Descargar la versión 1.0.0 del complemento.
    *   `https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip` - Descargar el complemento directamente desde la URL.

!!! warning "Falsos Positivos"
    Una configuración de seguridad más alta puede bloquear el tráfico legítimo. Comience con la configuración predeterminada y supervise los registros antes de aumentar los niveles de seguridad. Esté preparado para agregar reglas de exclusión para las necesidades específicas de su aplicación.

### Configuraciones de Ejemplo

=== "Configuración Básica"

    Una configuración estándar con ModSecurity y CRS v4 habilitados:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "Modo de Solo Detección"

    Configuración para monitorear amenazas potenciales sin bloquear:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "DetectionOnly"
    MODSECURITY_SEC_AUDIT_ENGINE: "On"
    MODSECURITY_SEC_AUDIT_LOG_PARTS: "ABIJDEFHZ"
    ```

=== "Configuración Avanzada con Complementos"

    Configuración con CRS v4 y complementos habilitados para protección adicional:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions fake-bot"
    MODSECURITY_REQ_BODY_NO_FILES_LIMIT: "262144"
    ```

=== "Configuración Heredada"

    Configuración que utiliza CRS v3 para compatibilidad con configuraciones más antiguas:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "3"
    MODSECURITY_SEC_RULE_ENGINE: "On"
    ```

=== "ModSecurity Global"

    Configuración que aplica ModSecurity globalmente a todas las conexiones HTTP:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "4"
    USE_MODSECURITY_GLOBAL_CRS: "yes"
    ```

=== "Compilación Nocturna con Complementos Personalizados"

    Configuración que utiliza la compilación nocturna de CRS con complementos personalizados:

    ```yaml
    USE_MODSECURITY: "yes"
    USE_MODSECURITY_CRS: "yes"
    MODSECURITY_CRS_VERSION: "nightly"
    USE_MODSECURITY_CRS_PLUGINS: "yes"
    MODSECURITY_CRS_PLUGINS: "wordpress-rule-exclusions/v1.0.0 https://github.com/coreruleset/dos-protection-plugin-modsecurity/archive/refs/heads/main.zip"
    ```

!!! note "Valores de tamaño legibles por humanos"
    Para los ajustes de tamaño como `MODSECURITY_REQ_BODY_NO_FILES_LIMIT`, se admiten los sufijos `k`, `m` y `g` (sin distinción entre mayúsculas y minúsculas) y representan kibibytes, mebibytes y gibibytes (múltiplos de 1024). Ejemplos: `256k` = 262144, `1m` = 1048576, `2g` = 2147483648.
