Le plugin Bad Behavior protège votre site en détectant et bannissant automatiquement les IP qui génèrent trop d’erreurs (codes HTTP « mauvais ») sur une période donnée. Utile contre la force brute, les scrapers, scanners et activités malveillantes.

Les attaquants déclenchent fréquemment des codes « suspects » lors de sondes ou d’exploitation — bien plus qu’un utilisateur normal sur une même période. En détectant ce comportement, BunkerWeb bannit l’IP fautive.

Comment ça marche :

1. Le plugin surveille les réponses HTTP.
2. À chaque code « mauvais » (400, 401, 403, 404, …), le compteur de l’IP augmente.
3. Au‑delà du seuil et dans la fenêtre configurée, l’IP est bannie.
4. Le bannissement peut être au niveau service (site) ou global (tous les sites).
5. Les bans expirent après la durée configurée (ou sont permanents avec `0`).

### Comment l’utiliser

1. Activation : `USE_BAD_BEHAVIOR` (activé par défaut).
2. Codes à compter : `BAD_BEHAVIOR_STATUS_CODES`.
3. Seuil : `BAD_BEHAVIOR_THRESHOLD`.
4. Fenêtre et durée de ban : `BAD_BEHAVIOR_COUNT_TIME`, `BAD_BEHAVIOR_BAN_TIME`.
5. Portée : `BAD_BEHAVIOR_BAN_SCOPE` (`service` ou `global`).

!!! tip "Mode stream"
En mode stream, seul `444` est considéré comme « mauvais ».

### Paramètres

| Paramètre                   | Défaut                        | Contexte  | Multiple | Description                                                    |
| --------------------------- | ----------------------------- | --------- | -------- | -------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | non      | Activer la détection et le bannissement.                       |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | non      | Codes HTTP considérés « mauvais ».                             |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | non      | Seuil de réponses « mauvaises » avant bannissement.            |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | non      | Fenêtre de comptage (secondes).                                |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | non      | Durée du ban en secondes (`0` = permanent).                    |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | non      | Portée du ban : site courant (`service`) ou global (`global`). |

!!! warning "Faux positifs"
Un seuil/fenêtre trop bas peut bannir des utilisateurs légitimes. Démarrez conservateur et ajustez.

### Exemples

=== "Défaut"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strict"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"
    BAD_BEHAVIOR_BAN_SCOPE: "global"
    ```

=== "Tolérant"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Ban permanent"

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"
    BAD_BEHAVIOR_BAN_SCOPE: "global"
    ```
