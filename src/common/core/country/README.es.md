El complemento de País habilita la funcionalidad de bloqueo geográfico para su sitio web, permitiéndole restringir el acceso según la ubicación geográfica de sus visitantes. Esta función le ayuda a cumplir con las regulaciones regionales, prevenir actividades fraudulentas a menudo asociadas con regiones de alto riesgo e implementar restricciones de contenido basadas en límites geográficos.

**Cómo funciona:**

1.  Cuando un visitante accede a su sitio web, BunkerWeb determina su país basándose en su dirección IP.
2.  Su configuración especifica una lista blanca (países permitidos) o una lista negra (países bloqueados).
3.  Si ha configurado una lista blanca, solo los visitantes de los países de esa lista tendrán acceso.
4.  Si ha configurado una lista negra, se denegará el acceso a los visitantes de los países de esa lista.
5.  El resultado se almacena en caché para mejorar el rendimiento de los visitantes recurrentes de la misma dirección IP.

### Cómo usar

Siga estos pasos para configurar y utilizar la función de País:

1.  **Defina su estrategia:** Decida si desea utilizar un enfoque de lista blanca (permitir solo países específicos) o un enfoque de lista negra (bloquear países específicos).
2.  **Configure países o grupos:** Añada códigos ISO 3166-1 alfa-2 (dos letras como US, GB, FR) y/o tokens de grupo compatibles (como `@EU`, `@SCHENGEN`) en `WHITELIST_COUNTRY` o `BLACKLIST_COUNTRY`.
3.  **Aplique la configuración:** Una vez configuradas, las restricciones basadas en el país se aplicarán a todos los visitantes de su sitio.
4.  **Supervise la eficacia:** Consulte la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las solicitudes bloqueadas por país.

### Ajustes de configuración

| Ajuste              | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                             |
| ------------------- | ----------------- | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `WHITELIST_COUNTRY` |                   | multisite | no       | **Lista Blanca de Países:** Lista de códigos de país y/o tokens de grupo separados por espacios. Solo se permiten estos países. |
| `BLACKLIST_COUNTRY` |                   | multisite | no       | **Lista Negra de Países:** Lista de códigos de país y/o tokens de grupo separados por espacios. Estos países están bloqueados.  |

### Grupos de países compatibles

Puede usar tokens de grupo con prefijo `@`. Se expanden del lado del servidor a sus países miembros:

- `@EU`: Estados miembros de la Unión Europea.
- `@SCHENGEN`: países del espacio Schengen.
- `@EEA`: Espacio Económico Europeo (`@EU` + Islandia, Liechtenstein y Noruega).
- `@BENELUX`: Bélgica, Países Bajos y Luxemburgo.
- `@DACH`: región núcleo germanoparlante (Alemania, Austria y Suiza).
- `@NORDICS`: países nórdicos (Dinamarca, Finlandia, Islandia, Noruega y Suecia).
- `@USMCA`: área del tratado USMCA (Estados Unidos, Canadá y México).
- `@FIVE_EYES`: países de la alianza de inteligencia Five Eyes.
- `@ASEAN`: Estados miembros de ASEAN en el Sudeste Asiático.
- `@GCC`: Estados miembros del Consejo de Cooperación del Golfo.
- `@G7`: países del Grupo de los Siete.
- `@LATAM`: conjunto de América Latina usado por este complemento.

!!! tip "Lista Blanca vs. Lista Negra"
    Elija el enfoque que mejor se adapte a sus necesidades:

    -   Use la lista blanca cuando quiera restringir el acceso a un pequeño número de países.
    -   Use la lista negra cuando quiera bloquear el acceso desde regiones problemáticas específicas mientras permite a todos los demás.

!!! warning "Regla de Precedencia"
    Si se configuran tanto la lista blanca como la lista negra, la lista blanca tiene prioridad. Esto significa que el sistema primero comprueba si un país está en la lista blanca; si no, se deniega el acceso independientemente de la configuración de la lista negra.

!!! info "Detección de País"
    BunkerWeb utiliza la [base de datos mmdb lite de db-ip](https://db-ip.com/db/download/ip-to-country-lite) para determinar el país de origen basándose en las direcciones IP.

### Configuraciones de Ejemplo

=== "Solo Lista Blanca"

    Permitir el acceso solo desde Estados Unidos, Canadá y el Reino Unido:

    ```yaml
    WHITELIST_COUNTRY: "US CA GB"
    ```

=== "Solo Lista Negra"

    Bloquear el acceso desde países específicos mientras se permite a todos los demás:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP"
    ```

=== "Acceso Solo para la UE"

    Permitir el acceso solo desde los estados miembros de la Unión Europea:

    ```yaml
    WHITELIST_COUNTRY: "@EU"
    ```

=== "Grupo + países explícitos"

    ```yaml
    WHITELIST_COUNTRY: "@SCHENGEN GB"
    ```

=== "Bloqueo de Países de Alto Riesgo"

    Bloquear el acceso desde países a menudo asociados con ciertas ciberamenazas:

    ```yaml
    BLACKLIST_COUNTRY: "RU CN KP IR SY"
    ```
