El complemento Robots.txt gestiona el archivo [robots.txt](https://www.robotstxt.org/) para su sitio web. Este archivo indica a los rastreadores web y robots qué partes de su sitio pueden o no pueden acceder.

**Cómo funciona:**

Cuando está habilitado, BunkerWeb genera dinámicamente el archivo `/robots.txt` en la raíz de su sitio web. Las reglas dentro de este archivo se agregan de múltiples fuentes en el siguiente orden:

1.  **API de DarkVisitors:** Si se proporciona `ROBOTSTXT_DARKVISITORS_TOKEN`, las reglas se obtienen de la API de [DarkVisitors](https://darkvisitors.com/), lo que permite el bloqueo dinámico de bots maliciosos y rastreadores de IA según los tipos de agentes configurados y los agentes de usuario no permitidos.
2.  **Listas de la Comunidad:** Se incluyen reglas de listas `robots.txt` predefinidas y mantenidas por la comunidad (especificadas por `ROBOTSTXT_COMMUNITY_LISTS`).
3.  **URL personalizadas:** Las reglas se obtienen de las URL proporcionadas por el usuario (especificadas por `ROBOTSTXT_URLS`).
4.  **Reglas manuales:** Se agregan las reglas definidas directamente a través de las variables de entorno `ROBOTSTXT_RULE`.

Todas las reglas de estas fuentes se combinan. Después de la agregación, se aplican `ROBOTSTXT_IGNORE_RULE` para filtrar cualquier regla no deseada utilizando patrones de expresiones regulares PCRE. Finalmente, si no queda ninguna regla después de todo este proceso, se aplica automáticamente una regla predeterminada `User-agent: *` y `Disallow: /` para garantizar un nivel básico de protección. Las URL de mapa de sitio opcionales (especificadas por `ROBOTSTXT_SITEMAP`) también se incluyen en la salida final de `robots.txt`.

### Evasión Dinámica de Bots con la API de DarkVisitors

[DarkVisitors](https://darkvisitors.com/) es un servicio que proporciona un archivo `robots.txt` dinámico para ayudar a bloquear bots maliciosos conocidos y rastreadores de IA. Al integrarse con DarkVisitors, BunkerWeb puede obtener y servir automáticamente un `robots.txt` actualizado que ayuda a proteger su sitio del tráfico automatizado no deseado.

Para habilitar esto, debe registrarse en [darkvisitors.com](https://darkvisitors.com/docs/robots-txt) y obtener un token de portador (bearer token).

### Cómo usar

1.  **Habilite la función:** Establezca el ajuste `USE_ROBOTSTXT` en `yes`.
2.  **Configure las reglas:** Elija uno o más métodos para definir sus reglas de `robots.txt`:
    - **API de DarkVisitors:** Proporcione `ROBOTSTXT_DARKVISITORS_TOKEN` y, opcionalmente, `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` y `ROBOTSTXT_DARKVISITORS_DISALLOW`.
    - **Listas de la Comunidad:** Especifique `ROBOTSTXT_COMMUNITY_LISTS` (IDs separados por espacios).
    - **URL personalizadas:** Proporcione `ROBOTSTXT_URLS` (URLs separadas por espacios).
    - **Reglas manuales:** Use `ROBOTSTXT_RULE` para reglas individuales (se pueden especificar múltiples reglas con `ROBOTSTXT_RULE_N`).
3.  **Filtre las reglas (opcional):** Use `ROBOTSTXT_IGNORE_RULE_N` para excluir reglas específicas por patrón de expresión regular.
4.  **Agregue mapas de sitio (opcional):** Use `ROBOTSTXT_SITEMAP_N` para las URL de los mapas de sitio.
5.  **Obtenga el archivo robots.txt generado:** Una vez que BunkerWeb esté funcionando con los ajustes anteriores, puede acceder al archivo `robots.txt` generado dinámicamente haciendo una solicitud HTTP GET a `http(s)://su-dominio.com/robots.txt`.

### Ajustes de Configuración

| Ajuste                               | Valor por defecto | Contexto  | Múltiple | Descripción                                                                                                                                           |
| ------------------------------------ | ----------------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ROBOTSTXT`                      | `no`              | multisite | No       | Habilita o deshabilita la función `robots.txt`.                                                                                                       |
| `ROBOTSTXT_DARKVISITORS_TOKEN`       |                   | multisite | No       | Token de portador para la API de DarkVisitors.                                                                                                        |
| `ROBOTSTXT_DARKVISITORS_AGENT_TYPES` |                   | multisite | No       | Lista de tipos de agentes separados por comas (por ejemplo, `AI Data Scraper`) para incluir desde DarkVisitors.                                       |
| `ROBOTSTXT_DARKVISITORS_DISALLOW`    | `/`               | multisite | No       | Una cadena que especifica qué URL no están permitidas. Este valor se enviará como el campo de no permitir al contactar con la API de DarkVisitors.    |
| `ROBOTSTXT_COMMUNITY_LISTS`          |                   | multisite | No       | Lista separada por espacios de IDs de conjuntos de reglas mantenidos por la comunidad para incluir.                                                   |
| `ROBOTSTXT_URLS`                     |                   | multisite | No       | Lista separada por espacios de URL para obtener reglas adicionales de `robots.txt`. Admite `file://` y autenticación básica (`http://user:pass@url`). |
| `ROBOTSTXT_RULE`                     |                   | multisite | Sí       | Una sola regla para `robots.txt`.                                                                                                                     |
| `ROBOTSTXT_HEADER`                   |                   | multisite | Sí       | Encabezado para el archivo `robots.txt` (antes de las reglas). Puede estar codificado en Base64.                                                      |
| `ROBOTSTXT_FOOTER`                   |                   | multisite | Sí       | Pie de página para el archivo `robots.txt` (después de las reglas). Puede estar codificado en Base64.                                                 |
| `ROBOTSTXT_IGNORE_RULE`              |                   | multisite | Sí       | Un único patrón de expresión regular PCRE para ignorar reglas.                                                                                        |
| `ROBOTSTXT_SITEMAP`                  |                   | multisite | Sí       | Una única URL de mapa de sitio.                                                                                                                       |

### Configuraciones de Ejemplo

**Reglas Manuales Básicas**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Usando Fuentes Dinámicas (DarkVisitors y Lista de la Comunidad)**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "su-token-de-darkvisitors-aqui"
ROBOTSTXT_DARKVISITORS_AGENT_TYPES: "AI Data Scraper"
ROBOTSTXT_COMMUNITY_LISTS: "robots-disallowed"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
```

**Configuración Combinada**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_DARKVISITORS_TOKEN: "su-token-de-darkvisitors-aqui"
ROBOTSTXT_COMMUNITY_LISTS: "ai-robots-txt"
ROBOTSTXT_URLS: "https://example.com/my-custom-rules.txt"
ROBOTSTXT_RULE: "User-agent: MyOwnBot"
ROBOTSTXT_RULE_1: "Disallow: /admin"
ROBOTSTXT_IGNORE_RULE: "User-agent: Googlebot-Image"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

**Con Encabezado y Pie de Página**

```yaml
USE_ROBOTSTXT: "yes"
ROBOTSTXT_HEADER: "# Este es un encabezado personalizado"
ROBOTSTXT_RULE: "User-agent: *"
ROBOTSTXT_RULE_1: "Disallow: /private"
ROBOTSTXT_FOOTER: "# Este es un pie de página personalizado"
ROBOTSTXT_SITEMAP: "https://example.com/sitemap.xml"
```

---

Para más información, consulte la [documentación de robots.txt](https://www.robotstxt.org/robotstxt.html).
