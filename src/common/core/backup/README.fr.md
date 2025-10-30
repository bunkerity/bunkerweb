Le plugin Backup fournit des sauvegardes automatisées pour protéger vos données BunkerWeb. Il crée des sauvegardes régulières selon une planification définie, stockées dans un emplacement dédié, avec rotation automatique et commandes CLI pour gérer manuellement.

Comment ça marche :

1. La base est sauvegardée automatiquement selon la fréquence (quotidienne, hebdomadaire, mensuelle).
2. Les sauvegardes sont stockées dans un répertoire dédié.
3. Les anciennes sauvegardes sont supprimées selon la politique de rétention.
4. Vous pouvez créer, lister et restaurer manuellement des sauvegardes.
5. Avant toute restauration, un snapshot de l’état courant est créé automatiquement.

### Comment l’utiliser

1. Activation : `USE_BACKUP` (activé par défaut).
2. Planification : `BACKUP_SCHEDULE`.
3. Rétention : `BACKUP_ROTATION`.
4. Emplacement : `BACKUP_DIRECTORY`.
5. CLI : utilisez `bwcli plugin backup`.

### Paramètres

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                   |
| ------------------ | ---------------------------- | -------- | -------- | ----------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | Activer les sauvegardes automatiques.                                         |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | Fréquence : `daily`, `weekly`, `monthly`.                                     |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | Rétention : nombre de fichiers à conserver. Au‑delà, suppression automatique. |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | non      | Répertoire de stockage des sauvegardes.                                       |

### Interface en ligne de commande

```bash
bwcli plugin backup list        # Lister
bwcli plugin backup save        # Sauvegarde manuelle
bwcli plugin backup save --directory /chemin/perso   # Emplacement personnalisé
bwcli plugin backup restore     # Restaurer la plus récente
bwcli plugin backup restore /chemin/backup-sqlite-YYYY-MM-DD_HH-MM-SS.zip   # Restaurer via fichier
```

!!! tip "Sécurité"
    Avant toute restauration, un backup de l’état courant est créé automatiquement dans un emplacement temporaire.

!!! warning "Compatibilité bases"
    Supporte SQLite, MySQL/MariaDB, PostgreSQL. Oracle non pris en charge pour sauvegarde/restauration.

### Exemples

=== "Quotidien, rétention 7 jours" (défaut)

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Hebdomadaire, rétention étendue"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "weekly"
    BACKUP_ROTATION: "12"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Mensuel, emplacement personnalisé"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "monthly"
    BACKUP_ROTATION: "24"
    BACKUP_DIRECTORY: "/mnt/backup-drive/bunkerweb-backups"
    ```
