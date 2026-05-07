Le plugin Backup fournit des sauvegardes automatisées pour protéger vos données BunkerWeb. Il crée des sauvegardes régulières selon une planification définie, stockées dans un emplacement dédié, avec rotation automatique et commandes CLI pour gérer manuellement.

**Comment ça marche :**

1. La base est sauvegardée automatiquement selon la fréquence choisie (`daily`, `weekly`, `monthly` ou `hanoi`).
2. Les sauvegardes sont stockées dans un répertoire dédié.
3. Avant chaque sauvegarde, l'espace disque disponible est vérifié.
4. Chaque ZIP contient le dump SQL et un fichier de somme de contrôle SHA-256 (`.sha256`) pour vérifier l'intégrité.
5. Les anciennes sauvegardes sont supprimées selon la politique de rétention. Le mode `hanoi` applique la rotation Tours de Hanoï (24 fichiers, ~85 jours de couverture).
6. Lors d'une restauration, la somme de contrôle est vérifiée avant toute modification de la base active.
7. Vous pouvez créer, lister, vérifier et restaurer manuellement des sauvegardes.
8. Avant toute restauration, un snapshot de l'état courant est créé automatiquement.

### Comment l'utiliser

1. **Activation :** `USE_BACKUP` (activé par défaut).
2. **Planification :** `BACKUP_SCHEDULE`.
3. **Rétention :** `BACKUP_ROTATION` (ignoré si `BACKUP_SCHEDULE=hanoi`).
4. **Emplacement :** `BACKUP_DIRECTORY`.
5. **CLI :** utilisez `bwcli plugin backup`.

### Paramètres

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                                                                                              |
| ------------------ | ---------------------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | Activer les sauvegardes automatiques.                                                                                                                    |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | Fréquence : `daily`, `weekly`, `monthly` ou `hanoi` (horaire avec rotation Tours de Hanoï, ~85 jours de couverture).                                    |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | Rétention : nombre de fichiers à conserver. Ignoré pour `hanoi` (la rotation est gérée automatiquement par l'algorithme).                                |
| `BACKUP_DIRECTORY` | `/var/lib/bunkerweb/backups` | global   | non      | Répertoire de stockage des sauvegardes.                                                                                                                  |
| `BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE` | `no` | global | non | Si `yes`, un échec de vérification SHA-256 n'interrompt pas la restauration. À utiliser en dernier recours pour les sauvegardes partiellement corrompues. |

### Interface en ligne de commande

```bash
bwcli plugin backup list        # Lister
bwcli plugin backup check       # Vérifier les sommes de contrôle SHA-256
bwcli plugin backup save        # Sauvegarde manuelle
bwcli plugin backup save --directory /chemin/perso   # Emplacement personnalisé
bwcli plugin backup restore     # Restaurer la plus récente
bwcli plugin backup restore /chemin/backup-sqlite-YYYY-MM-DD_HH-MM-SS.zip   # Restaurer via fichier
```

!!! tip "Sécurité"
    Avant toute restauration, un backup de l'état courant est créé automatiquement dans un emplacement temporaire.

!!! info "Vérification d'intégrité"
    Chaque ZIP contient un fichier SHA-256. La somme est vérifiée automatiquement avant toute restauration. Utilisez `bwcli plugin backup check` pour vérifier tous les backups à tout moment.

!!! warning "Compatibilité bases"
    Supporte SQLite, MySQL/MariaDB, PostgreSQL. Oracle non pris en charge pour sauvegarde/restauration.

### Exemples

=== "Quotidien, rétention 7 jours (défaut)"

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Tours de Hanoï (~85 jours)"

    Exécution horaire avec rotation Tours de Hanoï. Conserve 24 fichiers couvrant ~85 jours. `BACKUP_ROTATION` est ignoré :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "hanoi"
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
