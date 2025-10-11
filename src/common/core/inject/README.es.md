El complemento de Inyección de HTML le permite agregar sin problemas código HTML personalizado a las páginas de su sitio web antes de las etiquetas de cierre `</body>` o `</head>`. Esta función es particularmente útil para agregar scripts de análisis, píxeles de seguimiento, JavaScript personalizado, estilos CSS u otras integraciones de terceros sin modificar el código fuente de su sitio web.

**Cómo funciona:**

1.  Cuando se sirve una página de su sitio web, BunkerWeb examina la respuesta HTML.
2.  Si ha configurado la inyección en el cuerpo (body), BunkerWeb inserta su código HTML personalizado justo antes de la etiqueta de cierre `</body>`.
3.  Si ha configurado la inyección en la cabecera (head), BunkerWeb inserta su código HTML personalizado justo antes de la etiqueta de cierre `</head>`.
4.  La inserción se realiza automáticamente para todas las páginas HTML servidas por su sitio web.
5.  Esto le permite agregar scripts, estilos u otros elementos sin modificar el código de su aplicación.

### Cómo usar

Siga estos pasos para configurar y usar la función de Inyección de HTML:

1.  **Prepare su HTML personalizado:** Decida qué código HTML desea inyectar en sus páginas.
2.  **Elija las ubicaciones de inyección:** Determine si necesita inyectar código en la sección `<head>`, en la sección `<body>`, o en ambas.
3.  **Configure los ajustes:** Agregue su HTML personalizado a los ajustes apropiados (`INJECT_HEAD` y/o `INJECT_BODY`).
4.  **Deje que BunkerWeb se encargue del resto:** Una vez configurado, el HTML se inyectará automáticamente en todas las páginas HTML servidas.

### Ajustes de Configuración

| Ajuste        | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                  |
| ------------- | ----------------- | --------- | -------- | -------------------------------------------------------------------------------------------- |
| `INJECT_HEAD` |                   | multisite | no       | **Código HTML de la Cabecera:** El código HTML para inyectar antes de la etiqueta `</head>`. |
| `INJECT_BODY` |                   | multisite | no       | **Código HTML del Cuerpo:** El código HTML para inyectar antes de la etiqueta `</body>`.     |

!!! tip "Mejores Prácticas" - Por razones de rendimiento, coloque los archivos de JavaScript al final del cuerpo para evitar el bloqueo del renderizado. - Coloque CSS y JavaScript crítico en la sección de la cabecera para evitar un "destello" de contenido sin estilo (FOUC). - Tenga cuidado con el contenido inyectado que podría potencialmente romper la funcionalidad de su sitio.

!!! info "Casos de Uso Comunes" - Agregar scripts de análisis (como Google Analytics, Matomo) - Integrar widgets de chat o herramientas de soporte al cliente - Incluir píxeles de seguimiento para campañas de marketing - Agregar estilos CSS personalizados o funcionalidad de JavaScript - Incluir bibliotecas de terceros sin modificar el código de su aplicación

### Configuraciones de Ejemplo

=== "Google Analytics"

    Agregar el seguimiento de Google Analytics a su sitio web:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Estilos Personalizados"

    Agregar estilos CSS personalizados a su sitio web:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Múltiples Integraciones"

    Agregar tanto estilos personalizados como JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Banner de Consentimiento de Cookies"

    Agregar un banner simple de consentimiento de cookies:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">Este sitio web utiliza cookies para garantizar que obtenga la mejor experiencia. <button onclick=\"acceptCookies()\">Aceptar</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```
