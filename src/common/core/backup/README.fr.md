Le plugin Backup fournit une solution de sauvegarde automatisée pour protéger vos données BunkerWeb. Cette fonctionnalité assure la sécurité et la disponibilité de votre base de données importante en créant des sauvegardes régulières selon la planification choisie. Les sauvegardes sont stockées dans un emplacement dédié et peuvent être gérées facilement par des processus automatisés comme par des commandes manuelles.

**Comment ça marche :**

1. Votre base de données est sauvegardée automatiquement selon la planification définie (quotidienne, hebdomadaire ou mensuelle).
2. Les sauvegardes sont stockées dans un répertoire précis de votre système.
3. Les anciennes sauvegardes sont automatiquement supprimées selon vos paramètres de rétention.
4. Vous pouvez créer des sauvegardes, lister les sauvegardes existantes ou restaurer une sauvegarde manuellement à tout moment.
5. Avant toute opération de restauration, l'état actuel est automatiquement sauvegardé par sécurité.

### Comment l'utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Backup :

1. **Activer la fonctionnalité :** La sauvegarde est activée par défaut. Si nécessaire, vous pouvez la contrôler avec le paramètre `USE_BACKUP`.
2. **Configurer la planification :** Choisissez la fréquence des sauvegardes avec le paramètre `BACKUP_SCHEDULE`.
3. **Définir la politique de rétention :** Indiquez le nombre de sauvegardes à conserver avec le paramètre `BACKUP_ROTATION`.
4. **Définir l'emplacement de stockage :** Choisissez où les sauvegardes seront stockées avec le paramètre `BACKUP_DIRECTORY`.
5. **Utiliser les commandes CLI :** Gérez les sauvegardes manuellement avec les commandes `bwcli plugin backup` lorsque c'est nécessaire.

### Paramètres de configuration

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                                                                        |
| ------------------ | ---------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | **Activer Backup :** Mettre à `yes` pour activer les sauvegardes automatiques.                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | **Fréquence de sauvegarde :** Fréquence d'exécution des sauvegardes. Options : `daily`, `weekly` ou `monthly`.                     |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | **Rétention des sauvegardes :** Nombre de fichiers de sauvegarde à conserver. Les sauvegardes plus anciennes seront supprimées.    |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | non      | **Emplacement des sauvegardes :** Répertoire dans lequel les fichiers de sauvegarde seront stockés.                                |

### Interface en ligne de commande

Le plugin Backup fournit plusieurs commandes CLI pour gérer vos sauvegardes :

```bash
# Lister toutes les sauvegardes disponibles
bwcli plugin backup list

# Créer une sauvegarde manuelle
bwcli plugin backup save

# Créer une sauvegarde dans un emplacement personnalisé
bwcli plugin backup save --directory /path/to/custom/location

# Restaurer depuis la sauvegarde la plus récente
bwcli plugin backup restore

# Restaurer depuis un fichier de sauvegarde précis
bwcli plugin backup restore /path/to/backup/backup-sqlite-2023-08-15_12-34-56.zip
```

!!! tip "Priorité à la sécurité"
    Avant toute opération de restauration, le plugin Backup crée automatiquement une sauvegarde de l'état actuel de votre base de données dans un emplacement temporaire. Cela fournit une protection supplémentaire si vous devez annuler la restauration.

!!! warning "Compatibilité des bases de données"
    Le plugin Backup prend en charge les bases SQLite, MySQL/MariaDB et PostgreSQL. Les bases Oracle ne sont pas prises en charge actuellement pour les opérations de sauvegarde et de restauration.

### Exemples de configuration

=== "Sauvegardes quotidiennes avec rétention de 7 jours"

    Configuration par défaut qui crée des sauvegardes quotidiennes et conserve les 7 fichiers les plus récents :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Sauvegardes hebdomadaires avec rétention étendue"

    Configuration pour des sauvegardes moins fréquentes avec une rétention plus longue :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Sauvegardes mensuelles vers un emplacement personnalisé"

    Configuration pour des sauvegardes mensuelles stockées dans un emplacement personnalisé :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
