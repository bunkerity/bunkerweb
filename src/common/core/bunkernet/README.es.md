El complemento BunkerNet permite el intercambio colectivo de inteligencia sobre amenazas entre las instancias de BunkerWeb, creando una poderosa red de protección contra actores maliciosos. Al participar en BunkerNet, su instancia se beneficia y contribuye a una base de datos global de amenazas conocidas, mejorando la seguridad para toda la comunidad de BunkerWeb.

**Cómo funciona:**

1.  Su instancia de BunkerWeb se registra automáticamente con la API de BunkerNet para recibir un identificador único.
2.  Cuando su instancia detecta y bloquea una dirección IP o comportamiento malicioso, informa de la amenaza a BunkerNet. Los campos de un informe se enumeran en la nota «Contenido de un informe» más abajo.
3.  BunkerNet agrega la inteligencia sobre amenazas de todas las instancias participantes y distribuye la base de datos consolidada.
4.  Su instancia descarga regularmente una base de datos actualizada de amenazas conocidas desde BunkerNet.
5.  Esta inteligencia colectiva permite que su instancia bloquee proactivamente las direcciones IP que han exhibido comportamiento malicioso en otras instancias de BunkerWeb.

!!! success "Beneficios clave"

      1. **Defensa Colectiva:** Aproveche los hallazgos de seguridad de miles de otras instancias de BunkerWeb a nivel mundial.
      2. **Protección Proactiva:** Bloquee a los actores maliciosos antes de que puedan atacar su sitio basándose en su comportamiento en otros lugares.
      3. **Contribución a la Comunidad:** Ayude a proteger a otros usuarios de BunkerWeb compartiendo datos de amenazas sobre los atacantes.
      4. **Cero Configuración:** Funciona desde el primer momento con valores predeterminados sensatos, requiriendo una configuración mínima.
      5. **Intercambio controlado:** Un informe contiene un conjunto fijo de campos, y `BUNKERNET_FILTER_HEADERS` puede limitar sus cabeceras de petición a una lista corta permitida (véase más abajo).

### Cómo usar

Siga estos pasos para configurar y usar la función BunkerNet:

1.  **Habilite la función:** La función BunkerNet está habilitada por defecto. Si es necesario, puede controlarla con la configuración `USE_BUNKERNET`.
2.  **Registro inicial:** En el primer arranque, su instancia se registrará automáticamente con la API de BunkerNet y recibirá un identificador único.
3.  **Actualizaciones automáticas:** Su instancia descargará automáticamente la última base de datos de amenazas en un horario regular.
4.  **Informes automáticos:** Cuando su instancia bloquee una dirección IP maliciosa, contribuirá automáticamente estos datos a la comunidad.
5.  **Monitoree la protección:** Consulte la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las amenazas bloqueadas por la inteligencia de BunkerNet.

### Ajustes de configuración

| Ajuste                     | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                                                                                                                                                                                         |
| -------------------------- | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`            | `yes`                      | multisite | no       | **Habilitar BunkerNet:** Establezca en `yes` para habilitar el intercambio de inteligencia sobre amenazas de BunkerNet.                                                                                                                                                             |
| `BUNKERNET_FILTER_HEADERS` | `no`                       | multisite | no       | **Filtrar las cabeceras notificadas:** Establezca en `yes` para enviar solo una lista corta de cabeceras de petición y vaciar los valores que ModSecurity encontró en cabeceras y cookies. Con `no`, un informe contiene todas las cabeceras de petición salvo `Cookie`, `Authorization` y `Proxy-Authorization`, y los valores encontrados salvo los hallados en ellas y en las cookies. |
| `BUNKERNET_SERVER`         | `https://api.bunkerweb.io` | global    | no       | **Servidor BunkerNet:** La dirección del servidor de la API de BunkerNet para compartir inteligencia sobre amenazas.                                                                                                                                                                |

!!! tip "Protección de Red"
    Cuando BunkerNet detecta que una dirección IP ha estado involucrada en actividades maliciosas en múltiples instancias de BunkerWeb, añade esa IP a una lista negra colectiva. Esto proporciona una capa de defensa proactiva, protegiendo su sitio de amenazas antes de que puedan atacarlo directamente.

!!! info "Contenido de un informe"
    Cada informe enviado a BunkerNet contiene estos campos y nada más:

    - los metadatos de la instancia enviados con cada petición: el ID de la instancia BunkerNet, la versión de BunkerWeb, la integración, y el nombre, la versión, el ID de versión, el nombre en clave, el ID y la arquitectura del sistema operativo;
    - la dirección IP del cliente, el motivo del bloqueo y la fecha;
    - el método HTTP, la URL **incluida su cadena de consulta** y el nombre del servicio (`server_name`);
    - las cabeceras de petición, con sus valores: todas las recibidas (hasta `MAX_HEADERS`) salvo `Cookie`, `Authorization` y `Proxy-Authorization`, o, si `BUNKERNET_FILTER_HEADERS` es `yes`, solo `User-Agent`, `Accept`, `Accept-Encoding`, `Accept-Language`, `Content-Type` y `Content-Length`;
    - los detalles asociados al motivo del bloqueo. Según el plugin que bloqueó al cliente, pueden incluir los ID y mensajes de las reglas de ModSecurity que coincidieron junto con los valores de la petición que las activaron (partes de argumentos, cuerpo, cabeceras o cookies, cada una recortada a 512 bytes; los valores hallados en cookies y en las cabeceras `Cookie`, `Authorization` y `Proxy-Authorization` se vacían siempre, y con `BUNKERNET_FILTER_HEADERS` en `yes` también los hallados en cualquier otra cabecera; solo se envía el nombre de la variable) o, para Bad Behavior, el método y la URL de las peticiones recientes que provocaron el bloqueo.

    De forma predeterminada (`BUNKERNET_FILTER_HEADERS` en `no`), un informe contiene todas las cabeceras de petición recibidas (hasta `MAX_HEADERS`) salvo `Cookie`, `Authorization` y `Proxy-Authorization`, que nunca se envían, y los valores encontrados por ModSecurity salvo los hallados en las cookies y en esas cabeceras. Establezca `BUNKERNET_FILTER_HEADERS` en `yes` para enviar solo las seis cabeceras indicadas arriba y vaciar los valores hallados en cabeceras y cookies. Los informes aún sin enviar se depuran igual antes de enviarse (las credenciales siempre, la lista permitida cuando vale `yes`).

    La URL y los valores coincidentes proceden de la petición, por lo que contienen todo lo que envió el cliente. Establezca `USE_BUNKERNET` en `no` en los servicios cuyas URL contengan valores sensibles.

### Configuraciones de Ejemplo

=== "Configuración por Defecto (Recomendada)"

    La configuración por defecto habilita BunkerNet con el servidor oficial de la API de BunkerWeb:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Configuración Deshabilitada"

    Si prefiere no participar en la red de inteligencia sobre amenazas de BunkerNet:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Configuración de Servidor Personalizado"

    Para organizaciones que ejecutan su propio servidor BunkerNet (poco común):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```

### Integración con la Consola de CrowdSec

Si aún no está familiarizado con la integración de la Consola de CrowdSec, [CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) aprovecha la inteligencia colectiva para combatir las ciberamenazas. Piense en ello como el "Waze de la ciberseguridad": cuando un servidor es atacado, otros sistemas en todo el mundo son alertados y protegidos de los mismos atacantes. Puede obtener más información al respecto [aquí](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

A través de nuestra asociación con CrowdSec, puede inscribir sus instancias de BunkerWeb en su [Consola de CrowdSec](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). Esto significa que los ataques bloqueados por BunkerWeb serán visibles en su Consola de CrowdSec junto con los ataques bloqueados por los Motores de Seguridad de CrowdSec, brindándole una vista unificada de las amenazas.

Es importante destacar que no es necesario instalar CrowdSec para esta integración (aunque recomendamos encarecidamente probarlo con el [complemento de CrowdSec para BunkerWeb](https://docs.bunkerweb.io/1.6/features/#crowdsec) para mejorar aún más la seguridad de sus servicios web). Además, puede inscribir sus Motores de Seguridad de CrowdSec en la misma cuenta de la Consola para una sinergia aún mayor.

**Paso #1: Cree su cuenta en la Consola de CrowdSec**

Vaya a la [Consola de CrowdSec](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) y regístrese si aún no tiene una cuenta. Una vez hecho esto, anote la clave de inscripción que se encuentra en "Security Engines" después de hacer clic en "Add Security Engine":

<figure markdown>
  ![Descripción general](assets/img/crowdity1.png){ align=center }
  <figcaption>Obtenga su clave de inscripción de la Consola de CrowdSec</figcaption>
</figure>

**Paso #2: Obtenga su ID de BunkerNet**

Activar la función BunkerNet (habilitada por defecto) es obligatorio si desea inscribir su(s) instancia(s) de BunkerWeb en su Consola de CrowdSec. Habilítela estableciendo `USE_BUNKERNET` en `yes`.

Para Docker, obtenga su ID de BunkerNet usando:

```shell
docker exec mi-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

Para Linux, use:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

**Paso #3: Inscriba su instancia usando el Panel**

Una vez que tenga su ID de BunkerNet y la clave de inscripción de la Consola de CrowdSec, [solicite el producto gratuito "BunkerNet / CrowdSec" en el Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). Es posible que se le pida que cree una cuenta si aún no lo ha hecho.

Ahora puede seleccionar el servicio "BunkerNet / CrowdSec" y completar el formulario pegando su ID de BunkerNet y la clave de inscripción de la Consola de CrowdSec:

<figure markdown>
  ![Descripción general](assets/img/crowdity2.png){ align=center }
  <figcaption>Inscriba su instancia de BunkerWeb en la Consola de CrowdSec</figcaption>
</figure>

**Paso #4: Acepte el nuevo motor de seguridad en la Consola**

Luego, vuelva a su Consola de CrowdSec y acepte el nuevo Motor de Seguridad:

<figure markdown>
  ![Descripción general](assets/img/crowdity3.png){ align=center }
  <figcaption>Acepte la inscripción en la Consola de CrowdSec</figcaption>
</figure>

**¡Felicitaciones, su instancia de BunkerWeb ahora está inscrita en su Consola de CrowdSec!**

Consejo profesional: Al ver sus alertas, haga clic en la opción "columnas" y marque la casilla "contexto" para acceder a datos específicos de BunkerWeb.

<figure markdown>
  ![Descripción general](assets/img/crowdity4.png){ align=center }
  <figcaption>Datos de BunkerWeb mostrados en la columna de contexto</figcaption>
</figure>
