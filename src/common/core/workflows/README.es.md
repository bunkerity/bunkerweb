El plugin Workflows añade una capa de políticas entre los ajustes individuales y las protecciones
Lua: reglas reutilizables y ordenadas que se adjuntan a servicios, cada una con un árbol de
condiciones y una acción.

Una regla responde a una pregunta que los ajustes individuales no pueden expresar por sí solos:

> **Si** la petición viene de Francia **y** apunta a `/login` **y** supera 10 peticiones por minuto,
> **entonces** muestra un desafío hCaptcha.

Los workflows **coordinan** las protecciones existentes. La acción `challenge` entrega la petición
a Antibot y un umbral de frecuencia usa el mismo contador que Limit. Los ajustes existentes siguen funcionando.

### Cómo se evalúa una regla

En cada servicio se evalúan los workflows en el orden de asociación, y sus reglas en el orden
configurado. **Gana la primera regla que coincide efectivamente**: ejecuta su única acción y no
se evalúa nada posterior.

Una condición es un árbol de nodos `ALL` / `ANY` / `NOT` sobre:

| Condición | Dato comparado |
| --------- | -------------- |
| IP / CIDR | IP efectiva del cliente, tras la resolución Real IP |
| País | País ISO resuelto desde la base GeoIP |
| ASN | Número de sistema autónomo de la IP del cliente |
| URI | Ruta normalizada: exacta, prefijo o expresión regular |
| Método HTTP | Método de la petición |
| Grupo de recursos | Grupo de IP, países o ASN mantenido aparte y referenciado por ID |
| Veredicto CrowdSec | Decisión de CrowdSec: fuente (`appsec` o `lapi`) y acción solicitada (`ban` o `captcha`) |

Las condiciones tienen **tres valores**: verdadero, falso o *desconocido* cuando falta el dato,
por ejemplo la base GeoIP. Una regla solo coincide si el árbol resulta verdadero: una base averiada
hace que deje de coincidir, no que coincida por accidente.

Una condición de **veredicto CrowdSec** es indeterminada si CrowdSec no evaluó el servicio, y falsa
si lo evaluó y no encontró nada: son casos distintos y ninguno coincide. Para que un workflow
responda *en lugar de* CrowdSec, establece `CROWDSEC_DEFER_TO_WORKFLOWS` en `yes` en el servicio.
CrowdSec entrega su veredicto sin aplicarlo; si ninguna regla coincide, se aplica sin cambios.

### Los umbrales de frecuencia son una condición, no una acción

Una regla puede tener un umbral que decide **si coincide**, no una acción de limitación. Por debajo
del umbral se continúa con la siguiente regla.

Así se expresa «por encima de 10 peticiones por minuto responde 429; si no, muestra un desafío»
con dos reglas ordenadas con las mismas condiciones: la primera con umbral y bloqueo, la segunda sin umbral.

El contador se limita a servicio + regla + IP del cliente y no interfiere con `LIMIT_REQ_*`.

### Acciones

- **challenge**: muestra un proveedor Antibot concreto (`captcha`, `hcaptcha`, `turnstile`, …).
  Funciona incluso con `USE_ANTIBOT` en `no` y prevalece sobre sus listas de exclusión: expresa las
  exclusiones en las condiciones de la regla. El servicio debe tener las credenciales del proveedor.
- **block**: responde con el estado de denegación de la instancia o `429` para una regla de frecuencia.
- **redirect**: envía al cliente a una URL fija con 301/302/303/307/308.

### Modo de detección

`SECURITY_MODE=detect` ejecuta los mismos árboles en el mismo orden y con los mismos contadores,
pero no aplica acciones. Los informes registran lo que *habría* ocurrido para medir la política
con tráfico real antes de activarla.

### Comportamiento ante fallos

Una instancia sin política compilada — primer arranque o envío no recibido — registra un error y
sirve tráfico con sus protecciones habituales. Una política que el plano de control no puede
compilar no se distribuye: se abandona el envío y las instancias conservan la anterior. No se
puede eliminar un grupo de recursos mientras una regla lo referencie.

### Presupuesto de expresiones regulares

| Ajuste | Predeterminado | Contexto | Múltiple | Descripción |
| ------ | -------------- | -------- | -------- | ----------- |
| `WORKFLOWS_REGEX_BUDGET` | `512` | global | no | **Presupuesto regex:** Máximo de expresiones regulares distintas compiladas entre todas las reglas. NGINX comparte una caché regex entre plugins; las reglas que superan este límite se deshabilitan para evitar degradar silenciosamente toda la instancia. |

La compilación recorre los workflows por ID ordenado y consume el presupuesto a medida que avanza.
Si se agota durante un artefacto, desactiva las reglas restantes de forma determinista: dos
instancias con el mismo artefacto desactivan las mismas reglas.

### Gestión de workflows

Se gestionan desde **Workflows** en la interfaz o los endpoints `/workflows`. Las reglas se guardan
centralmente y se compilan en un único artefacto distribuido a todas las instancias con el envío
habitual de configuración.
