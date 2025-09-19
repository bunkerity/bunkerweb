# Introducción

## Descripción general

<figure markdown>
  ![Descripción general](assets/img/intro-overview.svg){ align=center, width="800" }
  <figcaption>¡Haz que tus servicios web sean seguros por defecto!</figcaption>
</figure>

BunkerWeb es un Firewall de Aplicaciones Web (WAF) de código abierto y de última generación.

Como un servidor web con todas las funciones (basado en [NGINX](https://nginx.org/) internamente), protege tus servicios web para hacerlos "seguros por defecto". BunkerWeb se integra sin problemas en tus entornos existentes ([Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), …) como un proxy inverso y es totalmente configurable (no te preocupes, hay una [impresionante interfaz de usuario web](web-ui.md) si no te gusta la CLI) para satisfacer tus casos de uso específicos. En otras palabras, la ciberseguridad ya no es una molestia.

BunkerWeb incluye [características de seguridad](advanced.md#security-tuning) principales como parte del núcleo, pero se puede ampliar fácilmente con otras adicionales gracias a un [sistema de plugins](plugins.md).

## ¿Por qué BunkerWeb?

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/oybLtyhWJIo" title="Descripción general de BunkerWeb" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

- **Fácil integración en entornos existentes**: Integra sin problemas BunkerWeb en diversos entornos como Linux, Docker, Swarm, Kubernetes y más. Disfruta de una transición fluida y una implementación sin complicaciones.

- **Altamente personalizable**: Adapta BunkerWeb a tus requisitos específicos con facilidad. Habilita, deshabilita y configura características sin esfuerzo, lo que te permite personalizar la configuración de seguridad según tu caso de uso único.

- **Seguro por defecto**: BunkerWeb proporciona seguridad mínima lista para usar y sin complicaciones para tus servicios web. Experimenta tranquilidad y protección mejorada desde el principio.

- **Impresionante interfaz de usuario web**: Toma el control de BunkerWeb de manera más eficiente con la excepcional interfaz de usuario web (UI). Navega por la configuración y las opciones sin esfuerzo a través de una interfaz gráfica fácil de usar, eliminando la necesidad de la interfaz de línea de comandos (CLI).

- **Sistema de plugins**: Amplía las capacidades de BunkerWeb para satisfacer tus propios casos de uso. Integra sin problemas medidas de seguridad adicionales y personaliza la funcionalidad de BunkerWeb según tus requisitos específicos.

- **Libre como en "libertad"**: BunkerWeb está licenciado bajo la licencia libre [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html), abrazando los principios de libertad y apertura. Disfruta de la libertad de usar, modificar y distribuir el software, respaldado por una comunidad de apoyo.

- **Servicios profesionales**: Obtén soporte técnico, consultoría a medida y desarrollo personalizado directamente de los mantenedores de BunkerWeb. Visita el [Panel de BunkerWeb](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) para más información.

## Características de seguridad

Explora la impresionante gama de características de seguridad que ofrece BunkerWeb. Aunque no es exhaustiva, aquí hay algunos puntos destacados:

- Soporte **HTTPS** con automatización transparente de **Let's Encrypt**: Asegura fácilmente tus servicios web con la integración automatizada de Let's Encrypt, garantizando la comunicación cifrada entre los clientes y tu servidor.

- **Seguridad web de última generación**: Benefíciate de medidas de seguridad web de vanguardia, incluyendo cabeceras de seguridad HTTP completas, prevención de fugas de datos y técnicas de fortalecimiento de TLS.

- **WAF ModSecurity** integrado con el **OWASP Core Rule Set**: Disfruta de una protección mejorada contra ataques a aplicaciones web con la integración de ModSecurity, fortalecida por el reconocido OWASP Core Rule Set.

- **Baneo automático** de comportamientos extraños basados en códigos de estado HTTP: BunkerWeb identifica y bloquea inteligentemente actividades sospechosas al banear automáticamente los comportamientos que desencadenan códigos de estado HTTP anómalos.

- Aplica **límites de conexión y de solicitudes** para los clientes: Establece límites en el número de conexiones y solicitudes de los clientes, previniendo el agotamiento de recursos y asegurando un uso justo de los recursos del servidor.

- **Bloquea bots** con **verificación basada en desafíos**: Mantén a raya a los bots maliciosos desafiándolos a resolver acertijos como cookies, pruebas de JavaScript, captchas, hCaptcha, reCAPTCHA o Turnstile, bloqueando eficazmente el acceso no autorizado.

- **Bloquea IPs maliciosas conocidas** con listas negras externas y **DNSBL**: Utiliza listas negras externas y listas negras basadas en DNS (DNSBL) para bloquear proactivamente direcciones IP maliciosas conocidas, reforzando tu defensa contra posibles amenazas.

- **Y mucho más...**: BunkerWeb está repleto de una plétora de características de seguridad adicionales que van más allá de esta lista, brindándote una protección integral y tranquilidad.

Para profundizar en las características de seguridad principales, te invitamos a explorar la sección de [ajuste de seguridad](advanced.md#security-tuning) de la documentación. Descubre cómo BunkerWeb te permite ajustar y optimizar las medidas de seguridad según tus necesidades específicas.

## Demo

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="Engañando a herramientas y escáneres automatizados" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Un sitio web de demostración protegido con BunkerWeb está disponible en [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc). Siéntete libre de visitarlo y realizar algunas pruebas de seguridad.

## Interfaz de usuario web

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="Interfaz de usuario web de BunkerWeb" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

BunkerWeb ofrece una [interfaz de usuario](web-ui.md) opcional para gestionar tus instancias y sus configuraciones. Una demostración en línea de solo lectura está disponible en [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc). Siéntete libre de probarla tú mismo.

## BunkerWeb Cloud

<figure markdown>
  ![Descripción general](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

¿No quieres autohospedar y gestionar tu(s) propia(s) instancia(s) de BunkerWeb? Podría interesarte BunkerWeb Cloud, nuestra oferta SaaS totalmente gestionada para BunkerWeb.

Prueba nuestra [oferta de BunkerWeb Cloud](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) y obtén acceso a:

- Una instancia de BunkerWeb totalmente gestionada alojada en nuestra nube
- Todas las características de BunkerWeb, incluidas las PRO
- Una plataforma de monitorización con paneles y alertas
- Soporte técnico para ayudarte con la configuración

Si estás interesado en la oferta de BunkerWeb Cloud, no dudes en [contactarnos](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) para que podamos discutir tus necesidades.

## Versión PRO

!!! tip "Prueba gratuita de BunkerWeb PRO"
    ¿Quieres probar rápidamente BunkerWeb PRO durante un mes? Usa el código `freetrial` al realizar tu pedido en el [Panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) o haciendo clic [aquí](https://panel.bunkerweb.io/cart.php?a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) para aplicar directamente el código de promoción (se hará efectivo al finalizar la compra).

Al usar BunkerWeb, tienes la opción de elegir la versión que deseas utilizar: de código abierto o PRO.

Ya sea para una seguridad mejorada, una experiencia de usuario enriquecida o un seguimiento técnico, la versión BunkerWeb PRO te permite beneficiarte plenamente de BunkerWeb y satisfacer tus necesidades profesionales.

En la documentación o en la interfaz de usuario, las características PRO están anotadas con una corona <img src="assets/img/pro-icon.svg" alt="icono de corona pro" height="32px" width="32px"> para distinguirlas de las integradas en la versión de código abierto.

Puedes actualizar de la versión de código abierto a la PRO fácilmente y en cualquier momento. El proceso es sencillo:

- Reclama tu [prueba gratuita en el panel de BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc) usando el código de promoción `freetrial` al finalizar la compra
- Una vez conectado al área de cliente, copia tu clave de licencia PRO
- Pega tu clave privada en BunkerWeb usando la [interfaz de usuario web](web-ui.md#upgrade-to-pro) o la [configuración específica](features.md#pro)

No dudes en visitar el [panel de BunkerWeb](https://panel.bunkerweb.io/knowledgebase?utm_campaign=self&utm_source=doc) o [contactarnos](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) si tienes alguna pregunta sobre la versión PRO.

## Servicios profesionales

Aprovecha al máximo BunkerWeb accediendo a servicios profesionales directamente de los mantenedores del proyecto. Desde soporte técnico hasta consultoría y desarrollo a medida, estamos aquí para ayudarte a proteger tus servicios web.

Encontrarás más información visitando el [Panel de BunkerWeb](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc), nuestra plataforma dedicada a los servicios profesionales.

No dudes en [contactarnos](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc) si tienes alguna pregunta. Estaremos encantados de responder a tus necesidades.

## Ecosistema, comunidad y recursos

Sitios web, herramientas y recursos oficiales sobre BunkerWeb:

- [**Sitio web**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc): Obtén más información, noticias y artículos sobre BunkerWeb.
- [**Panel**](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc): Una plataforma dedicada para solicitar y gestionar servicios profesionales (p. ej., soporte técnico) en torno a BunkerWeb.
- [**Documentación**](https://docs.bunkerweb.io): Documentación técnica de la solución BunkerWeb.
- [**Demo**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc): Sitio web de demostración de BunkerWeb. No dudes en intentar ataques para probar la robustez de la solución.
- [**Interfaz de usuario web**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc): Demostración en línea de solo lectura de la interfaz de usuario web de BunkerWeb.
- [**Mapa de amenazas**](https://threatmap.bunkerweb.io/?utm_campaign=self&utm_source=doc): Ciberataques en vivo bloqueados por instancias de BunkerWeb en todo el mundo.

Comunidad y redes sociales:

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**X (Anteriormente Twitter)**](https://x.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)
