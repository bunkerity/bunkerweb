Le plugin Backup fournit une solution de sauvegarde automatisée pour protéger vos données BunkerWeb. Cette fonctionnalité assure la sécurité et la disponibilité de votre base de données importante en créant des sauvegardes régulières selon la planification choisie. Les sauvegardes sont stockées dans un emplacement dédié et peuvent être gérées facilement par des processus automatisés comme par des commandes manuelles.

**Comment ça marche :**

1. Votre base de données est sauvegardée automatiquement selon la planification définie (`daily`, `weekly`, `monthly` ou `hanoi`).
2. Les sauvegardes sont stockées dans un répertoire précis de votre système.
3. Avant chaque sauvegarde, l'espace disque disponible est vérifié.
4. Chaque ZIP contient le dump SQL et un fichier de somme de contrôle SHA-256 (`.sha256`) pour vérifier l'intégrité.
5. Les anciennes sauvegardes sont automatiquement supprimées selon vos paramètres de rétention. Le mode `hanoi` applique la rotation Tours de Hanoï (24–34 fichiers, 64–85 jours de couverture).
6. Lors d'une restauration, la somme de contrôle est vérifiée avant toute modification de la base active.
7. Vous pouvez créer des sauvegardes, lister, vérifier ou restaurer les sauvegardes manuellement à tout moment.
8. Avant toute opération de restauration, l'état actuel est automatiquement sauvegardé par sécurité.

### Comment l'utiliser

Suivez ces étapes pour configurer et utiliser la fonctionnalité Backup :

1. **Activer la fonctionnalité :** La sauvegarde est activée par défaut. Si nécessaire, vous pouvez la contrôler avec le paramètre `USE_BACKUP`.
2. **Configurer la planification :** Choisissez la fréquence des sauvegardes avec le paramètre `BACKUP_SCHEDULE`.
3. **Définir la politique de rétention :** Indiquez le nombre de sauvegardes à conserver avec le paramètre `BACKUP_ROTATION` (ignoré si `BACKUP_SCHEDULE=hanoi`).
4. **Définir l'emplacement de stockage :** Choisissez où les sauvegardes seront stockées avec le paramètre `BACKUP_DIRECTORY`.
5. **Utiliser les commandes CLI :** Gérez les sauvegardes manuellement avec les commandes `bwcli plugin backup` lorsque c'est nécessaire.

### Paramètres de configuration

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                                                                        |
| ------------------ | ---------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | **Activer Backup :** Mettre à `yes` pour activer les sauvegardes automatiques.                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | **Fréquence de sauvegarde :** Fréquence d'exécution des sauvegardes. Options : `daily`, `weekly`, `monthly` ou `hanoi` (horaire avec rotation Tours de Hanoï, 64–85 jours de couverture). |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | **Rétention des sauvegardes :** Nombre de fichiers de sauvegarde à conserver. Les sauvegardes plus anciennes seront supprimées. Ignoré pour `hanoi` (la rotation est gérée automatiquement par l'algorithme). |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | non      | **Emplacement des sauvegardes :** Répertoire dans lequel les fichiers de sauvegarde seront stockés.                                |
| `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE` | `no` | global | non | Si `yes`, un échec de vérification SHA-256 n'interrompt pas la restauration. À utiliser en dernier recours pour les sauvegardes partiellement corrompues. |

### Interface en ligne de commande

Le plugin Backup fournit plusieurs commandes CLI pour gérer vos sauvegardes :

```bash
# Lister toutes les sauvegardes disponibles
bwcli plugin backup list

# Vérifier les sommes de contrôle SHA-256
bwcli plugin backup check

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

!!! info "Vérification d'intégrité"
    Chaque ZIP contient un fichier SHA-256. La somme est vérifiée automatiquement avant toute restauration. Utilisez `bwcli plugin backup check` pour vérifier tous les backups à tout moment.

!!! warning "Compatibilité des bases de données"
    Le plugin Backup prend en charge les bases SQLite, MySQL/MariaDB et PostgreSQL. Les bases Oracle ne sont pas prises en charge actuellement pour les opérations de sauvegarde et de restauration. Une restauration refuse une sauvegarde issue d'un autre moteur de base de données (MariaDB et MySQL comptent comme deux moteurs différents) avant de modifier quoi que ce soit.

### Exemples de configuration

=== "Sauvegardes quotidiennes avec rétention de 7 jours"

    Configuration par défaut qui crée des sauvegardes quotidiennes et conserve les 7 fichiers les plus récents :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Tours de Hanoï (64–85 jours)"

    Exécution horaire avec rotation Tours de Hanoï. Conserve 24–34 fichiers couvrant 64–85 jours. `BACKUP_ROTATION` est ignoré :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "hanoi"
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
