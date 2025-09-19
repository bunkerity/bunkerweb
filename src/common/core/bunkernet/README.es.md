El complemento BunkerNet permite el intercambio colectivo de inteligencia sobre amenazas entre las instancias de BunkerWeb, creando una poderosa red de protección contra actores maliciosos. Al participar en BunkerNet, su instancia se beneficia y contribuye a una base de datos global de amenazas conocidas, mejorando la seguridad para toda la comunidad de BunkerWeb.

**Cómo funciona:**

1.  Su instancia de BunkerWeb se registra automáticamente con la API de BunkerNet para recibir un identificador único.
2.  Cuando su instancia detecta y bloquea una dirección IP o comportamiento malicioso, informa anónimamente la amenaza a BunkerNet.
3.  BunkerNet agrega la inteligencia sobre amenazas de todas las instancias participantes y distribuye la base de datos consolidada.
4.  Su instancia descarga regularmente una base de datos actualizada de amenazas conocidas desde BunkerNet.
5.  Esta inteligencia colectiva permite que su instancia bloquee proactivamente las direcciones IP que han exhibido comportamiento malicioso en otras instancias de BunkerWeb.

!!! success "Beneficios clave"

      1. **Defensa Colectiva:** Aproveche los hallazgos de seguridad de miles de otras instancias de BunkerWeb a nivel mundial.
      2. **Protección Proactiva:** Bloquee a los actores maliciosos antes de que puedan atacar su sitio basándose en su comportamiento en otros lugares.
      3. **Contribución a la Comunidad:** Ayude a proteger a otros usuarios de BunkerWeb compartiendo datos de amenazas anónimos sobre los atacantes.
      4. **Cero Configuración:** Funciona desde el primer momento con valores predeterminados sensatos, requiriendo una configuración mínima.
      5. **Enfoque en la Privacidad:** Solo comparte la información de amenazas necesaria sin comprometer su privacidad ni la de sus usuarios.

### Cómo usar

Siga estos pasos para configurar y usar la función BunkerNet:

1.  **Habilite la función:** La función BunkerNet está habilitada por defecto. Si es necesario, puede controlarla con la configuración `USE_BUNKERNET`.
2.  **Registro inicial:** En el primer arranque, su instancia se registrará automáticamente con la API de BunkerNet y recibirá un identificador único.
3.  **Actualizaciones automáticas:** Su instancia descargará automáticamente la última base de datos de amenazas en un horario regular.
4.  **Informes automáticos:** Cuando su instancia bloquee una dirección IP maliciosa, contribuirá automáticamente estos datos a la comunidad.
5.  **Monitoree la protección:** Consulte la [interfaz de usuario web](web-ui.md) para ver estadísticas sobre las amenazas bloqueadas por la inteligencia de BunkerNet.

### Ajustes de configuración

| Ajuste             | Valor por defecto          | Contexto  | Múltiple | Descripción                                                                                                             |
| ------------------ | -------------------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Habilitar BunkerNet:** Establezca en `yes` para habilitar el intercambio de inteligencia sobre amenazas de BunkerNet. |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **Servidor BunkerNet:** La dirección del servidor de la API de BunkerNet para compartir inteligencia sobre amenazas.    |

!!! tip "Protección de Red"
Cuando BunkerNet detecta que una dirección IP ha estado involucrada en actividades maliciosas en múltiples instancias de BunkerWeb, añade esa IP a una lista negra colectiva. Esto proporciona una capa de defensa proactiva, protegiendo su sitio de amenazas antes de que puedan atacarlo directamente.

!!! info "Informes Anónimos"
Al informar sobre amenazas a BunkerNet, su instancia solo comparte los datos necesarios para identificar la amenaza: la dirección IP, el motivo del bloqueo y datos contextuales mínimos. No se comparte información personal sobre sus usuarios ni detalles sensibles sobre su sitio.

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

Es importante destacar que no es necesario instalar CrowdSec para esta integración (aunque recomendamos encarecidamente probarlo con el [complemento de CrowdSec para BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) para mejorar aún más la seguridad de sus servicios web). Además, puede inscribir sus Motores de Seguridad de CrowdSec en la misma cuenta de la Consola para una sinergia aún mayor.

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
