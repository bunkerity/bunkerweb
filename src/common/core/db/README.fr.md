Le plugin Base de données fournit une intégration robuste pour BunkerWeb en permettant le stockage centralisé et la gestion des données de configuration, des journaux et d'autres informations essentielles.

Ce composant cœur prend en charge plusieurs moteurs : SQLite, PostgreSQL, MySQL/MariaDB et Oracle, afin de choisir la solution la mieux adaptée à votre environnement et à vos besoins.

Comment ça marche :

1. BunkerWeb se connecte à la base configurée via une URI au format SQLAlchemy.
2. Les données de configuration critiques, les informations d'exécution et les journaux des jobs sont stockés de manière sécurisée en base.
3. Des tâches de maintenance automatiques optimisent la base en gérant la croissance et en purgeant les enregistrements excédentaires.
4. Pour la haute disponibilité, vous pouvez configurer une URI en lecture seule servant de bascule et/ou pour délester les lectures.
5. Les opérations base de données sont journalisées selon le niveau de log spécifié, offrant la visibilité adaptée.

### Comment l'utiliser

Étapes pour configurer la base de données :

1. Choisir un moteur : SQLite (par défaut), PostgreSQL, MySQL/MariaDB ou Oracle.
2. Configurer l'URI : renseignez `DATABASE_URI` (format SQLAlchemy) pour la base principale.
3. Optionnel : `DATABASE_URI_READONLY` pour les opérations en lecture seule ou en secours.

### Paramètres

| Paramètre                         | Défaut                                    | Contexte | Multiple | Description                                                                                                                                                                    |
| --------------------------------- | ----------------------------------------- | -------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `DATABASE_URI`                    | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global   | non      | URI principale de connexion (format SQLAlchemy).                                                                                                                               |
| `DATABASE_URI_READONLY`           |                                           | global   | non      | URI optionnelle en lecture seule (offload/HA).                                                                                                                                 |
| `DATABASE_LOG_LEVEL`              | `warning`                                 | global   | non      | Niveau de verbosité des logs DB : `debug`, `info`, `warn`, `warning`, `error`.                                                                                                 |
| `DATABASE_MAX_JOBS_RUNS`          | `10000`                                   | global   | non      | Nombre max d'entrées de runs de jobs conservées avant purge automatique.                                                                                                       |
| `DATABASE_MAX_SESSION_AGE_DAYS`   | `14`                                      | global   | non      | Durée max de conservation des sessions UI (en jours) avant purge automatique.                                                                                                  |
| `DATABASE_POOL_SIZE`              | `40`                                      | global   | non      | **Taille du pool :** Nombre de connexions maintenues dans le pool de connexions.                                                                                               |
| `DATABASE_POOL_MAX_OVERFLOW`      | `20`                                      | global   | non      | **Dépassement max du pool :** Nombre max de connexions supplémentaires au-delà de la taille du pool. `-1` pour illimité.                                                       |
| `DATABASE_POOL_TIMEOUT`           | `5`                                       | global   | non      | **Délai d'attente du pool :** Nombre de secondes d'attente avant d'abandonner l'obtention d'une connexion du pool.                                                             |
| `DATABASE_POOL_RECYCLE`           | `1800`                                    | global   | non      | **Recyclage du pool :** Nombre de secondes avant le recyclage automatique d'une connexion. `-1` pour désactiver.                                                               |
| `DATABASE_POOL_PRE_PING`          | `yes`                                     | global   | non      | **Pré-ping du pool :** Tester la vivacité des connexions à chaque extraction du pool.                                                                                          |
| `DATABASE_POOL_RESET_ON_RETURN`   |                                           | global   | non      | **Réinitialisation au retour :** Comment les connexions sont réinitialisées au retour dans le pool. Vide = auto (`none` pour MySQL/MariaDB, `rollback` sinon). Options : `rollback`, `commit`, `none`. |
| `DATABASE_RETRY_TIMEOUT`          | `60`                                      | global   | non      | **Délai de reconnexion :** Nombre max de secondes d'attente de disponibilité de la base au démarrage.                                                                          |
| `DATABASE_REQUEST_RETRY_ATTEMPTS` | `2`                                       | global   | non      | **Tentatives de réessai :** Nombre de tentatives en cas d'erreurs transitoires lors des opérations.                                                                            |
| `DATABASE_REQUEST_RETRY_DELAY`    | `0.25`                                    | global   | non      | **Délai entre réessais :** Délai en secondes entre les tentatives de réessai en cas d'erreurs transitoires.                                                                    |

!!! tip "Choix du moteur" - SQLite (défaut) : simple et fichier unique, idéal mono‑nœud/tests. - PostgreSQL : recommandé en production multi‑instances (robustesse, concurrence). - MySQL/MariaDB : alternative solide aux capacités proches de PostgreSQL. - Oracle : adapté aux environnements d'entreprise standardisés sur Oracle.

!!! info "Format SQLAlchemy" - SQLite : `sqlite:////chemin/vers/database.sqlite3` - PostgreSQL : `postgresql://user:password@hôte:port/base` - MySQL/MariaDB : `mysql://user:password@hôte:port/base` ou `mariadb://user:password@hôte:port/base` - Oracle : `oracle://user:password@hôte:port/base`

!!! warning "Maintenance"
    Des tâches quotidiennes assurent la maintenance automatique :

- **Purge des runs de jobs excédentaires** : supprime l'historique au-delà de `DATABASE_MAX_JOBS_RUNS`.
- **Purge des sessions UI expirées** : enlève les sessions plus anciennes que `DATABASE_MAX_SESSION_AGE_DAYS`.

Ces jobs évitent la croissance illimitée tout en conservant un historique d'exploitation pertinent.
