# Conceptos

## Arquitectura

<figure markdown>
  ![Descripción general](assets/img/concepts.svg){ align=center, width="600" }
</figure>

Dentro de tu infraestructura, BunkerWeb actúa como un proxy inverso frente a tus servicios web. La arquitectura típica implica acceder a BunkerWeb desde Internet, que luego reenvía las solicitudes al servicio de aplicación apropiado en una red segura.

Usar BunkerWeb de esta manera (arquitectura clásica de proxy inverso) con descarga de TLS y políticas de seguridad centralizadas mejora el rendimiento al reducir la sobrecarga de cifrado en los servidores backend, al tiempo que garantiza un control de acceso consistente, mitigación de amenazas y cumplimiento de normativas en todos los servicios.

## Integraciones

El primer concepto es la integración de BunkerWeb en el entorno de destino. Preferimos usar la palabra "integración" en lugar de "instalación" porque uno de los objetivos de BunkerWeb es integrarse sin problemas en los entornos existentes.

Las siguientes integraciones son oficialmente compatibles:

- [Docker](integrations.md#docker)
- [Linux](integrations.md#linux)
- [Docker autoconf](integrations.md#docker-autoconf)
- [Kubernetes](integrations.md#kubernetes)
- [Swarm](integrations.md#swarm)

Si crees que se debería admitir una nueva integración, no dudes en abrir un [nuevo issue](https://github.com/bunkerity/bunkerweb/issues) en el repositorio de GitHub.

!!! info "Para saber más"

    Los detalles técnicos de todas las integraciones de BunkerWeb están disponibles en la [sección de integraciones](integrations.md) de la documentación.

## Configuraciones

!!! tip "Configuraciones de BunkerWeb PRO"
    Algunos plugins están reservados para la **versión PRO**. ¿Quieres probar rápidamente BunkerWeb PRO durante un mes? Usa el código `freetrial` al realizar tu pedido en el [panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) o haciendo clic [aquí](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) para aplicar directamente el código de promoción (se hará efectivo al finalizar la compra).

Una vez que BunkerWeb esté integrado en tu entorno, necesitarás configurarlo para servir y proteger tus aplicaciones web.

La configuración de BunkerWeb se realiza utilizando lo que llamamos "configuraciones" o "variables". Cada configuración se identifica por un nombre como `AUTO_LETS_ENCRYPT` o `USE_ANTIBOT`. Puedes asignar valores a estas configuraciones para configurar BunkerWeb.

Aquí hay un ejemplo ficticio de una configuración de BunkerWeb:

```conf
SERVER_NAME=www.example.com
AUTO_LETS_ENCRYPT=yes
USE_ANTIBOT=captcha
REFERRER_POLICY=no-referrer
USE_MODSECURITY=no
USE_GZIP=yes
USE_BROTLI=no
```

Ten en cuenta que si estás utilizando la interfaz de usuario web, los nombres de las configuraciones también se muestran además de una etiqueta "fácil de usar":

<figure markdown>
  ![Descripción general](assets/img/settings-ui1.png){ align=center, width="800" }
  <figcaption>Nombre de la configuración en la interfaz de usuario web</figcaption>
</figure>

También puedes usar la barra de búsqueda y especificar directamente el nombre de una configuración:

<figure markdown>
  ![Descripción general](assets/img/settings-ui2.png){ align=center, width="600" }
  <figcaption>Búsqueda de configuraciones en la interfaz de usuario web</figcaption>
</figure>

!!! info "Para saber más"

    La lista completa de configuraciones disponibles con descripciones y posibles valores está disponible en la [sección de características](features.md) de la documentación.

## Modo multisitio {#multisite-mode}

Comprender el modo multisitio es esencial al utilizar BunkerWeb. Como nuestro enfoque principal es proteger las aplicaciones web, nuestra solución está intrínsecamente vinculada al concepto de "hosts virtuales" o "vhosts" (más información [aquí](https://es.wikipedia.org/wiki/Alojamiento_virtual)). Estos hosts virtuales permiten servir múltiples aplicaciones web desde una única instancia o clúster.

Por defecto, BunkerWeb tiene el modo multisitio deshabilitado. Esto significa que solo se servirá una aplicación web, y todas las configuraciones se aplicarán a ella. Esta configuración es ideal cuando tienes una sola aplicación que proteger, ya que no necesitas preocuparte por las configuraciones multisitio.

Sin embargo, cuando el modo multisitio está habilitado, BunkerWeb se vuelve capaz de servir y proteger múltiples aplicaciones web. Cada aplicación web se identifica por un nombre de servidor único y tiene su propio conjunto de configuraciones. Este modo resulta beneficioso cuando tienes múltiples aplicaciones que asegurar y prefieres utilizar una única instancia (o un clúster) de BunkerWeb.

La activación del modo multisitio se controla mediante la configuración `MULTISITE`, que se puede establecer en `yes` para habilitarlo o `no` para mantenerlo deshabilitado (el valor predeterminado).

Cada configuración dentro de BunkerWeb tiene un contexto específico que determina dónde se puede aplicar. Si el contexto se establece en "global", la configuración no se puede aplicar por servidor o sitio, sino que se aplica a toda la configuración en su conjunto. Por otro lado, si el contexto es "multisitio", la configuración se puede aplicar globalmente y por servidor. Para definir una configuración multisitio para un servidor específico, simplemente agrega el nombre del servidor como prefijo al nombre de la configuración. Por ejemplo, `app1.example.com_AUTO_LETS_ENCRYPT` o `app2.example.com_USE_ANTIBOT` son ejemplos de nombres de configuración con prefijos de nombre de servidor. Cuando una configuración multisitio se define globalmente sin un prefijo de servidor, todos los servidores heredan esa configuración. Sin embargo, los servidores individuales aún pueden anular la configuración si la misma configuración se define con un prefijo de nombre de servidor.

Comprender las complejidades del modo multisitio y sus configuraciones asociadas te permite adaptar el comportamiento de BunkerWeb a tus requisitos específicos, garantizando una protección óptima para tus aplicaciones web.

Aquí hay un ejemplo ficticio de una configuración multisitio de BunkerWeb:

```conf
MULTISITE=yes
SERVER_NAME=app1.example.com app2.example.com app3.example.com
AUTO_LETS_ENCRYPT=yes
USE_GZIP=yes
USE_BROTLI=yes
app1.example.com_USE_ANTIBOT=javascript
app1.example.com_USE_MODSECURITY=no
app2.example.com_USE_ANTIBOT=cookie
app2.example.com_WHITELIST_COUNTRY=FR
app3.example.com_USE_BAD_BEHAVIOR=no
```

Ten en cuenta que el modo multisitio es implícito cuando se utiliza la interfaz de usuario web. Tienes la opción de aplicar configuraciones directamente a tus servicios o de establecer ajustes globales que se aplicarán a todos tus servicios (aún puedes aplicar excepciones directamente a servicios específicos):

<figure markdown>
  ![Descripción general](assets/img/ui-multisite.png){ align=center, width="600" }
  <figcaption>Aplicar una configuración a todos los servicios desde la interfaz de usuario web</figcaption>
</figure>

!!! info "Para saber más"

    Encontrarás ejemplos concretos del modo multisitio en los [usos avanzados](advanced.md) de la documentación y en el directorio de [ejemplos](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) del repositorio.

## Configuraciones personalizadas {#custom-configurations}

Para abordar desafíos únicos y satisfacer casos de uso específicos, BunkerWeb ofrece la flexibilidad de las configuraciones personalizadas. Si bien las configuraciones proporcionadas y los [plugins externos](plugins.md) cubren una amplia gama de escenarios, puede haber situaciones que requieran una personalización adicional.

BunkerWeb está construido sobre el reconocido servidor web NGINX, que proporciona un potente sistema de configuración. Esto significa que puedes aprovechar las capacidades de configuración de NGINX para satisfacer tus necesidades específicas. Las configuraciones personalizadas de NGINX se pueden incluir en varios [contextos](https://docs.nginx.com/nginx/admin-guide/basic-functionality/managing-configuration-files/#contexts) como HTTP o servidor, lo que te permite ajustar el comportamiento de BunkerWeb según tus requisitos. Ya sea que necesites personalizar configuraciones globales o aplicar configuraciones a bloques de servidor específicos, BunkerWeb te permite optimizar su comportamiento para alinearse perfectamente con tu caso de uso.

Otro componente integral de BunkerWeb es el Firewall de Aplicaciones Web ModSecurity. Con configuraciones personalizadas, tienes la flexibilidad de abordar falsos positivos o agregar reglas personalizadas para mejorar aún más la protección proporcionada por ModSecurity. Estas configuraciones personalizadas te permiten ajustar el comportamiento del firewall y asegurar que se alinee con los requisitos específicos de tus aplicaciones web.

Al aprovechar las configuraciones personalizadas, desbloqueas un mundo de posibilidades para adaptar el comportamiento y las medidas de seguridad de BunkerWeb precisamente a tus necesidades. Ya sea ajustando las configuraciones de NGINX o afinando ModSecurity, BunkerWeb proporciona la flexibilidad para enfrentar tus desafíos únicos de manera efectiva.

La gestión de configuraciones personalizadas desde la interfaz de usuario web se realiza a través del menú **Configuraciones**:

<figure markdown>
  ![Descripción general](assets/img/configs-ui.png){ align=center, width="800" }
  <figcaption>Gestionar configuraciones personalizadas desde la interfaz de usuario web</figcaption>
</figure>

!!! info "Para saber más"

    Encontrarás ejemplos concretos de configuraciones personalizadas en los [usos avanzados](advanced.md#custom-configurations) de la documentación y en el directorio de [ejemplos](https://github.com/bunkerity/bunkerweb/tree/v1.6.8-rc3/examples) del repositorio.

## Base de datos

BunkerWeb almacena de forma segura su configuración actual en una base de datos de backend, que contiene datos esenciales para un funcionamiento sin problemas. La siguiente información se almacena en la base de datos:

- **Configuraciones para todos los servicios**: La base de datos contiene las configuraciones definidas para todos los servicios proporcionados por BunkerWeb. Esto asegura que tus configuraciones y preferencias se conserven y sean fácilmente accesibles.

- **Configuraciones personalizadas**: Cualquier configuración personalizada que crees también se almacena en la base de datos de backend. Esto incluye configuraciones personalizadas y modificaciones adaptadas a tus requisitos específicos.

- **Instancias de BunkerWeb**: La información sobre las instancias de BunkerWeb, incluida su configuración y detalles relevantes, se almacena en la base de datos. Esto permite una fácil gestión y monitoreo de múltiples instancias si corresponde.

- **Metadatos sobre la ejecución de trabajos**: La base de datos almacena metadatos relacionados con la ejecución de varios trabajos dentro de BunkerWeb. Esto incluye información sobre tareas programadas, procesos de mantenimiento y otras actividades automatizadas.

- **Archivos en caché**: BunkerWeb utiliza mecanismos de almacenamiento en caché para mejorar el rendimiento. La base de datos contiene archivos en caché, lo que garantiza una recuperación y entrega eficientes de los recursos a los que se accede con frecuencia.

Bajo el capó, cada vez que editas una configuración o agregas una nueva, BunkerWeb almacena automáticamente los cambios en la base de datos, garantizando la persistencia y coherencia de los datos. BunkerWeb admite múltiples opciones de bases de datos de backend, como SQLite, MariaDB, MySQL y PostgreSQL.

!!! tip
    Si utilizas la interfaz web para la administración diaria, te recomendamos migrar a un motor de base de datos externo (PostgreSQL o MySQL/MariaDB) en lugar de mantenerte en SQLite. Los motores externos gestionan mejor las solicitudes concurrentes y el crecimiento a largo plazo, especialmente en entornos multiusuario.

Configurar la base de datos es sencillo utilizando la configuración `DATABASE_URI`, que sigue los formatos especificados para cada base de datos compatible:

!!! warning
    Cuando se utiliza la Integración de Docker, debes establecer la variable de entorno `DATABASE_URI` en todos los contenedores de BunkerWeb (excepto el propio contenedor de BunkerWeb), para garantizar que todos los componentes puedan acceder a la base de datos correctamente. Esto es crucial para mantener la integridad y la funcionalidad del sistema.

    En todos los casos, asegúrate de que `DATABASE_URI` esté configurado antes de iniciar BunkerWeb, ya que es necesario para un funcionamiento correcto.

- **SQLite**: `sqlite:///var/lib/bunkerweb/db.sqlite3`
- **MariaDB**: `mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **MySQL**: `mysql+pymysql://bunkerweb:changeme@bw-db:3306/db`
- **PostgreSQL**: `postgresql://bunkerweb:changeme@bw-db:5432/db`

Al especificar el URI de la base de datos apropiado en la configuración, puedes integrar BunkerWeb sin problemas con tu backend de base de datos preferido, garantizando un almacenamiento eficiente y confiable de tus datos de configuración.

### Matriz de compatibilidad de bases de datos

| Integración        | PostgreSQL                                   | MariaDB                  | MySQL                    | SQLite       |
| :----------------- | :------------------------------------------- | :----------------------- | :----------------------- | :----------- |
| **Docker**         | ✅ `v18` y anteriores (all-in-one: ✅ `v17`)  | ✅ `v11` y anteriores     | ✅ `v9` y anteriores      | ✅ Compatible |
| **Kubernetes**     | ✅ `v18` y anteriores                         | ✅ `v11` y anteriores     | ✅ `v9` y anteriores      | ✅ Compatible |
| **Autoconf**       | ✅ `v18` y anteriores                         | ✅ `v11` y anteriores     | ✅ `v9` y anteriores      | ✅ Compatible |
| **Paquetes Linux** | Ver notas a continuación                      | Ver notas a continuación | Ver notas a continuación | ✅ Compatible |

!!! info "Notas"
    - **PostgreSQL**: Los paquetes basados en Alpine ahora incluyen el cliente `v18`, por lo que `v18` y versiones anteriores son compatibles de forma predeterminada; la imagen all-in-one sigue usando el cliente `v17`, por lo que `v18` no es compatible allí.
    - **Linux**: La compatibilidad depende de los paquetes de tu distribución. Si es necesario, puedes instalar los clientes de la base de datos manualmente desde los repositorios del proveedor (esto suele ser necesario en RHEL).
    - **SQLite**: Se entrega con los paquetes y está listo para usar.

Recursos externos útiles para instalar clientes de bases de datos:

- [Guía de descarga y repositorios de PostgreSQL](https://www.postgresql.org/download/)
- [Herramienta de configuración de repositorios de MariaDB](https://mariadb.org/download/?t=repo-config)
- [Guía de configuración del repositorio de MySQL](https://dev.mysql.com/doc/mysql-yum-repo-quick-guide/en/)
- [Página de descargas de SQLite](https://www.sqlite.org/download.html)

<figure markdown>
  ![Descripción general](assets/img/bunkerweb_db.svg){ align=center, width="800" }
  <figcaption>Esquema de la base de datos</figcaption>
</figure>

## Programador {#scheduler}

Para una coordinación y automatización fluidas, BunkerWeb emplea un servicio especializado conocido como el programador. El programador desempeña un papel vital para garantizar un funcionamiento sin problemas al realizar las siguientes tareas:

- **Almacenar configuraciones y configuraciones personalizadas**: El programador es responsable de almacenar todas las configuraciones y configuraciones personalizadas dentro de la base de datos de backend. Esto centraliza los datos de configuración, haciéndolos fácilmente accesibles y manejables.

- **Ejecutar diversas tareas (trabajos)**: El programador se encarga de la ejecución de diversas tareas, conocidas como trabajos. Estos trabajos abarcan una gama de actividades, como el mantenimiento periódico, las actualizaciones programadas o cualquier otra tarea automatizada requerida por BunkerWeb.

- **Generar la configuración de BunkerWeb**: El programador genera una configuración que es fácilmente comprensible por BunkerWeb. Esta configuración se deriva de las configuraciones almacenadas y las configuraciones personalizadas, asegurando que todo el sistema funcione de manera cohesiva.

- **Actuar como intermediario para otros servicios**: El programador actúa como intermediario, facilitando la comunicación y coordinación entre los diferentes componentes de BunkerWeb. Interactúa con servicios como la interfaz de usuario web o la autoconfiguración, asegurando un flujo de información y un intercambio de datos fluidos.

En esencia, el programador sirve como el cerebro de BunkerWeb, orquestando diversas operaciones y asegurando el buen funcionamiento del sistema.

Dependiendo del enfoque de integración, el entorno de ejecución del programador puede diferir. En las integraciones basadas en contenedores, el programador se ejecuta dentro de su contenedor dedicado, proporcionando aislamiento y flexibilidad. Por otro lado, para las integraciones basadas en Linux, el programador está autocontenido dentro del servicio bunkerweb, simplificando el proceso de implementación y gestión.

Al emplear el programador, BunkerWeb agiliza la automatización y coordinación de tareas esenciales, permitiendo un funcionamiento eficiente y confiable de todo el sistema.

Si estás utilizando la interfaz de usuario web, puedes gestionar los trabajos del programador haciendo clic en **Trabajos** en el menú:

<figure markdown>
  ![Descripción general](assets/img/jobs-ui.png){ align=center, width="800" }
  <figcaption>Gestionar trabajos desde la interfaz de usuario web</figcaption>
</figure>

### Comprobación del estado de las instancias

Desde la versión 1.6.0, el programador posee un sistema de comprobación de estado incorporado que monitorea la salud de las instancias. Si una instancia deja de estar saludable, el programador dejará de enviarle la configuración. Si la instancia vuelve a estar saludable, el programador reanudará el envío de la configuración.

El intervalo de comprobación de estado se establece mediante la variable de entorno `HEALTHCHECK_INTERVAL`, con un valor predeterminado de `30`, lo que significa que el programador comprobará la salud de las instancias cada 30 segundos.

## Plantillas {#templates}

BunkerWeb aprovecha el poder de las plantillas para simplificar el proceso de configuración y mejorar la flexibilidad. Las plantillas proporcionan un enfoque estructurado y estandarizado para definir configuraciones y configuraciones personalizadas, garantizando la coherencia y la facilidad de uso.

- **Plantillas predefinidas**: La versión comunitaria ofrece tres plantillas predefinidas que encapsulan configuraciones personalizadas y configuraciones comunes. Estas plantillas sirven como punto de partida para configurar BunkerWeb, permitiendo una configuración y despliegue rápidos. Las plantillas predefinidas son las siguientes:
    - **low**: Una plantilla básica que proporciona configuraciones esenciales para la protección de aplicaciones web.
    - **medium**: Una plantilla equilibrada que ofrece una mezcla de características de seguridad y optimizaciones de rendimiento.
    - **high**: Una plantilla avanzada que se centra en medidas de seguridad robustas y protección integral.

- **Plantillas personalizadas**: Además de las plantillas predefinidas, BunkerWeb permite a los usuarios crear plantillas personalizadas adaptadas a sus requisitos específicos. Las plantillas personalizadas permiten un ajuste fino de las configuraciones y configuraciones personalizadas, asegurando que BunkerWeb se alinee perfectamente con las necesidades del usuario.

Con la interfaz de usuario web, las plantillas están disponibles a través del **modo fácil** cuando agregas o editas un servicio:

<figure markdown>
  ![Descripción general](assets/img/templates-ui.png){ align=center, width="800" }
  <figcaption>Uso de plantillas desde la interfaz de usuario web</figcaption>
</figure>

**Creación de plantillas personalizadas**

Crear una plantilla personalizada es un proceso sencillo que implica definir las configuraciones deseadas, las configuraciones personalizadas y los pasos en un formato estructurado.

* **Estructura de la plantilla**: Una plantilla personalizada consta de un nombre, una serie de configuraciones, configuraciones personalizadas y pasos opcionales. La estructura de la plantilla se define en un archivo JSON que cumple con el formato especificado. Los componentes clave de una plantilla personalizada incluyen:
    * **Configuraciones**: Una configuración se define con un nombre y un valor correspondiente. Este valor anulará el valor predeterminado de la configuración. **Solo se admiten configuraciones multisitio.**
    * **Configuraciones personalizadas**: Una configuración personalizada es una ruta a un archivo de configuración de NGINX que se incluirá como una configuración personalizada. Para saber dónde colocar el archivo de configuración personalizada, consulta el ejemplo del árbol de un plugin a continuación. **Solo se admiten tipos de configuración multisitio.**
    * **Pasos**: Un paso contiene un título, un subtítulo, configuraciones y configuraciones personalizadas. Cada paso representa un paso de configuración que el usuario puede seguir para configurar BunkerWeb de acuerdo con la plantilla personalizada en la interfaz de usuario web.

!!! info "Especificaciones sobre los pasos"

    Si se declaran pasos, **no es obligatorio incluir todas las configuraciones y configuraciones personalizadas en las secciones de configuraciones y configuraciones personalizadas**. Ten en cuenta que cuando una configuración o una configuración personalizada se declara en un paso, al usuario se le permitirá realizar ediciones en la interfaz de usuario web.

* **Archivo de plantilla**: La plantilla personalizada se define en un archivo JSON en una carpeta `templates` dentro del directorio del plugin que se adhiere a la estructura especificada. El archivo de plantilla contiene un nombre, las configuraciones, las configuraciones personalizadas y los pasos necesarios para configurar BunkerWeb de acuerdo con las preferencias del usuario.

* **Selección de una plantilla**: Una vez definida la plantilla personalizada, los usuarios pueden seleccionarla durante el proceso de configuración en modo fácil de un servicio en la interfaz de usuario web. También se puede seleccionar una plantilla con la configuración `USE_TEMPLATE` en la configuración. El nombre del archivo de la plantilla (sin la extensión `.json`) debe especificarse como el valor de la configuración `USE_TEMPLATE`.

Ejemplo de un archivo de plantilla personalizada:
```json
{
    "name": "nombre de la plantilla",
	// opcional
    "settings": {
        "SETTING_1": "valor",
        "SETTING_2": "valor"
    },
	// opcional
    "configs": [
        "modsec/false_positives.conf",
        "modsec/non_editable.conf",
		"modsec-crs/custom_rules.conf"
    ],
	// opcional
    "steps": [
        {
            "title": "Título 1",
            "subtitle": "subtítulo 1",
            "settings": [
                "SETTING_1"
            ],
            "configs": [
                "modsec-crs/custom_rules.conf"
            ]
        },
        {
            "title": "Título 2",
            "subtitle": "subtítulo 2",
            "settings": [
                "SETTING_2"
            ],
            "configs": [
                "modsec/false_positives.conf"
            ]
        }
    ]
}
```

Ejemplo de un árbol de un plugin que incluye plantillas personalizadas:
```tree
.
├── plugin.json
└── templates
    ├── my_other_template.json
    ├── my_template
    │   └── configs
    │       ├── modsec
    │       │   ├── false_positives.conf
    │       │   └── non_editable.conf
    │       └── modsec-crs
    │           └── custom_rules.conf
    └── my_template.json
```
