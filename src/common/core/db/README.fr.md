Le plugin Base de données fournit une intégration robuste pour BunkerWeb en permettant le stockage centralisé et la gestion des données de configuration, des journaux et d’autres informations essentielles.

Ce composant cœur prend en charge plusieurs moteurs : SQLite, PostgreSQL, MySQL/MariaDB et Oracle, afin de choisir la solution la mieux adaptée à votre environnement et à vos besoins.

Comment ça marche :

1. BunkerWeb se connecte à la base configurée via une URI au format SQLAlchemy.
2. Les données de configuration critiques, les informations d’exécution et les journaux des jobs sont stockés de manière sécurisée en base.
3. Des tâches de maintenance automatiques optimisent la base en gérant la croissance et en purgeant les enregistrements excédentaires.
4. Pour la haute disponibilité, vous pouvez configurer une URI en lecture seule servant de bascule et/ou pour délester les lectures.
5. Les opérations base de données sont journalisées selon le niveau de log spécifié, offrant la visibilité adaptée.

### Comment l’utiliser

Étapes pour configurer la base de données :

1. Choisir un moteur : SQLite (par défaut), PostgreSQL, MySQL/MariaDB ou Oracle.
2. Configurer l’URI : renseignez `DATABASE_URI` (format SQLAlchemy) pour la base principale.
3. Optionnel : `DATABASE_URI_READONLY` pour les opérations en lecture seule ou en secours.

### Paramètres

| Paramètre                       | Défaut                                    | Contexte | Multiple | Description                                                                    |
| ------------------------------- | ----------------------------------------- | -------- | -------- | ------------------------------------------------------------------------------ |
| `DATABASE_URI`                  | `sqlite:////var/lib/bunkerweb/db.sqlite3` | global   | non      | URI principale de connexion (format SQLAlchemy).                               |
| `DATABASE_URI_READONLY`         |                                           | global   | non      | URI optionnelle en lecture seule (offload/HA).                                 |
| `DATABASE_LOG_LEVEL`            | `warning`                                 | global   | non      | Niveau de verbosité des logs DB : `debug`, `info`, `warn`, `warning`, `error`. |
| `DATABASE_MAX_JOBS_RUNS`        | `10000`                                   | global   | non      | Nombre max d’entrées de runs de jobs conservées avant purge automatique.       |
| `DATABASE_MAX_SESSION_AGE_DAYS` | `14`                                      | global   | non      | Durée max de conservation des sessions UI (en jours) avant purge automatique.  |

!!! tip "Choix du moteur" - SQLite (défaut) : simple et fichier unique, idéal mono‑nœud/tests. - PostgreSQL : recommandé en production multi‑instances (robustesse, concurrence). - MySQL/MariaDB : alternative solide aux capacités proches de PostgreSQL. - Oracle : adapté aux environnements d’entreprise standardisés sur Oracle.

!!! info "Format SQLAlchemy" - SQLite : `sqlite:////chemin/vers/database.sqlite3` - PostgreSQL : `postgresql://user:password@hôte:port/base` - MySQL/MariaDB : `mysql://user:password@hôte:port/base` ou `mariadb://user:password@hôte:port/base` - Oracle : `oracle://user:password@hôte:port/base`

!!! warning "Maintenance"
    Des tâches quotidiennes assurent la maintenance automatique :

- **Purge des runs de jobs excédentaires** : supprime l’historique au-delà de `DATABASE_MAX_JOBS_RUNS`.
- **Purge des sessions UI expirées** : enlève les sessions plus anciennes que `DATABASE_MAX_SESSION_AGE_DAYS`.

Ces jobs évitent la croissance illimitée tout en conservant un historique d’exploitation pertinent.
