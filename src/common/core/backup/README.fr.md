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
3. **Définir la politique de rétention :** Indiquez le nombre de sauvegardes à conserver avec le paramètre `BACKUP_ROTATION`. Lesquelles sont conservées est décidé par `BACKUP_ROTATION_STRATEGY`, `hanoi` par défaut.
4. **Définir l'emplacement de stockage :** Choisissez où les sauvegardes seront stockées avec le paramètre `BACKUP_DIRECTORY`.
5. **Utiliser les commandes CLI :** Gérez les sauvegardes manuellement avec les commandes `bwcli plugin backup` lorsque c'est nécessaire.

### Paramètres de configuration

| Paramètre          | Défaut                       | Contexte | Multiple | Description                                                                                                                        |
| ------------------ | ---------------------------- | -------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BACKUP`       | `yes`                        | global   | non      | **Activer Backup :** Mettre à `yes` pour activer les sauvegardes automatiques.                                                     |
| `BACKUP_SCHEDULE`  | `daily`                      | global   | non      | **Fréquence de sauvegarde :** Fréquence d'exécution des sauvegardes. Options : `daily`, `weekly` ou `monthly`.                     |
| `BACKUP_ROTATION`  | `7`                          | global   | non      | **Rétention des sauvegardes :** Nombre de fichiers de sauvegarde à conserver. Les sauvegardes au-delà de ce nombre sont automatiquement supprimées.    |
| `BACKUP_ROTATION_STRATEGY` | `hanoi`              | global   | non      | **Stratégie de rotation :** Comment les sauvegardes sont choisies pour la suppression une fois la limite atteinte. `hanoi` conserve une échelle des tours de Hanoï — fine près du présent, exponentiellement plus grossière en remontant ; `fifo` conserve les plus récentes. Les deux conservent le même nombre de fichiers.    |
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

    Une sauvegarde ne peut être restaurée que dans le moteur de base de données depuis lequel elle a été prise — le moteur fait partie du nom de fichier (`backup-mariadb-…`), et une restauration vers un autre moteur est refusée avant que quoi que ce soit ne soit touché. Si vous avez migré d'un moteur à un autre, les deux jeux de sauvegardes restent dans le répertoire : `restore` sans argument prend le fichier le plus récent, quel que soit son moteur, donc indiquez le chemin explicitement pour restaurer une sauvegarde plus ancienne de votre moteur actuel.

### Retour arrière contrôlé

Revenir à une version antérieure de BunkerWeb n'est **pas** l'inverse d'une mise à niveau. Certaines
tables 1.7 n'ont nulle part où aller en 1.6.x, et sur certains moteurs de base de données la
migration ne peut pas être rejouée à l'envers. Trois commandes rendent la décision vérifiable, et
seule la dernière modifie quoi que ce soit :

```bash
# 1. Cette installation peut-elle revenir en arrière ? Lecture seule : aucun schéma, aucune donnée,
#    aucune base créée.
bwcli plugin backup preflight 1.6.14

# 2. Geler les écritures. Au premier plan : le gel dure jusqu'à ce que vous fassiez Ctrl-C.
bwcli plugin backup quiesce 1.6.14

# 3. Dans un autre shell, pendant que l'étape 2 tient : d'abord le rapport, puis l'exécution.
bwcli plugin backup downgrade 1.6.14
bwcli plugin backup downgrade 1.6.14 --execute
```

La possibilité de rétrograder un couple de versions sur place est lue dans un **manifeste de
compatibilité** livré avec la version (`downgrade-manifest.json`, surchargeable via
`DOWNGRADE_MANIFEST`) ; elle n'est jamais déduite du numéro de version. Pour 1.7.0 vers 1.6.14, le
manifeste enregistre, d'après des exécutions de migration mesurées sur de vraies bases :

| Moteur | Retour en place | Pourquoi |
| ------ | --------------- | -------- |
| SQLite | ✅ testé | Le schéma revient exactement à celui que déclare 1.6.14, sans perdre une seule ligne de base. |
| PostgreSQL | ✅ testé | Idem, plus deux types enum inutilisés laissés en place, que 1.6.14 ne regarde jamais. |
| MariaDB | ❌ restauration depuis une sauvegarde | La migration s'interrompt en cours de route (erreurs 1265 et 1553) et laisse un schéma hybride. |
| MySQL | ❌ restauration depuis une sauvegarde | L'erreur 1265 y a été mesurée aussi ; le second blocage est déduit de MariaDB, pas mesuré sur MySQL. |

!!! danger "Un retour en place détruit les données propres à 1.7"
    Tous les certificats stockés de façon centralisée, toutes les ressources attachables
    (redirections, pools d'upstreams, workflows, groupes de ressources), toutes les métriques de
    requêtes et la carte des menaces, toutes les passkeys enregistrées, et tous les identifiants
    d'instance stockés — les instances enrôlées devront être ré-enrôlées ensuite. Les bans sont la
    seule exception : le job `sync-bans` les réapprend, seule leur durée restante est perdue. Le
    preflight compte les tables qu'il sait compter — y compris les groupes de ressources que vous
    avez créés vous-même, mais pas ceux livrés par BunkerWeb — et refuse tant que l'une d'elles
    contient quelque chose. Ce qu'il ne peut pas compter, il l'énonce juste avant la confirmation :
    les colonnes supprimées de tables qui survivent, et les données exclues parce qu'elles ne sont
    jamais vides (métriques de requêtes, préférences d'UI). Lisez cette liste : rien ne refuse à
    votre place pour ces données-là.

!!! tip "Chaque échec laisse un état démarrable"
    `downgrade --execute` refuse tant qu'un gel n'est pas en place pour cette même cible, que le
    preflight qu'il relance lui-même n'est pas au vert, et que le manifeste ne marque pas le couple
    comme testé. Ce preflight relancé interroge la base primaire — celle qu'il s'apprête à migrer — même
    lorsque `DATABASE_URI_READONLY` désigne un réplica en lecture seule : un réplica en retard ne peut
    donc pas répondre à la place des lignes que le retour détruirait. Il prend ensuite sa propre
    sauvegarde juste avant de migrer, et la restaure si quoi que ce soit échoue — un retour raté vous
    ramène donc à votre point de départ plutôt que sur un schéma à moitié migré. Dans le cas rare où la
    restauration elle-même n'aboutit pas, il s'arrête et signale `manual_recovery_required`, en nommant
    le fichier de sauvegarde et la commande `bwcli plugin backup restore` exacte pour terminer à la
    main.

### Exemples de configuration

=== "Sauvegardes quotidiennes avec rétention de 7 fichiers"

    Configuration par défaut : sauvegardes quotidiennes, 7 fichiers conservés, répartis par l'échelle des tours de Hanoï.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_DIRECTORY: "/var/lib/bunkerweb/backups"
    ```

=== "Sauvegardes quotidiennes, 7 derniers jours (FIFO)"

    L'ancien comportement par défaut : les 7 fichiers les plus récents et rien de plus ancien.

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "7"
    BACKUP_ROTATION_STRATEGY: "fifo"
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

=== "Sauvegardes quotidiennes avec une rétention plus profonde"

    24 fichiers répartis par l'échelle par défaut au lieu de ne couvrir que les 24 derniers jours.
    Les sauvegardes les plus récentes sont conservées à pleine granularité et les plus anciennes
    sont éclaircies exponentiellement, de sorte que le point de restauration le plus ancien recule
    à chaque fois que l'installation double d'âge — un problème remarqué tardivement reste
    récupérable :

    ```yaml
    USE_BACKUP: "yes"
    BACKUP_SCHEDULE: "daily"
    BACKUP_ROTATION: "24"
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

!!! info "Quelles sauvegardes sont conservées"
    `hanoi` est la valeur par défaut. Les deux stratégies suppriment le même **nombre** de fichiers
    — `hanoi` n'en supprime jamais plus que `fifo` ne l'aurait fait — mais elles ne suppriment pas
    les mêmes, et la différence ne se situe pas seulement du côté ancien. L'échelle paie sa
    profondeur en éclaircissant aussi la fenêtre récente : avec une planification quotidienne et le
    `BACKUP_ROTATION: "7"` par défaut, une archive établie conserve une sauvegarde dans chacune des
    fenêtres d'environ 1, 2, 4, 8, 16 et 32 jours — soit des âges d'environ 0, 1, 2–3, 4–7, 8–15,
    16–31 et 32–63 jours, les âges exacts dépendant de l'endroit où le jour courant tombe sur la
    grille fixe de l'échelle — là où `fifo` conserve les 7 derniers jours. **Trois ou quatre des
    sept derniers jours sont abandonnés** en échange de ces points de restauration plus anciens.
    La sauvegarde la plus récente est toujours conservée ; avec une sauvegarde par jour et un
    `BACKUP_ROTATION` d'au moins 2, les deux jours les plus récents le sont aussi. Le compromis est
    plus doux à mesure que `BACKUP_ROTATION` grandit — à `"24"`, les trois dernières semaines
    environ restent contiguës, une durée qui rétrécit lentement à mesure que l'archive vieillit.

    **Plusieurs sauvegardes prises le même jour comptent pour un seul point de restauration, et les
    surnuméraires sont les premiers fichiers qu'une rotation abandonne** — avant tout ce qui est
    plus ancien. Seule la sauvegarde la plus récente de chaque jour survit une fois le budget de
    fichiers épuisé. Ainsi, une sauvegarde manuelle prise avant un changement risqué n'est à l'abri
    que jusqu'à la sauvegarde suivante du même jour et, en devenant la plus récente de ce jour, elle
    évince la sauvegarde planifiée du jour, qui est alors celle qui est supprimée. Avec `fifo`, vous
    auriez conservé les deux.

    Rien de ce qui est déjà sur le disque n'est supprimé par la mise à niveau elle-même — le
    changement prend effet à la rotation suivante. Mettez `BACKUP_ROTATION_STRATEGY: "fifo"` pour
    retrouver le comportement précédent. Chaque suppression est journalisée avec la raison pour
    laquelle le fichier a été choisi.

!!! info "Comment l'échelle est construite"
    L'échelle compte en **périodes**, et une période vaut un `BACKUP_SCHEDULE` : un jour pour
    `daily`, sept pour `weekly`, vingt-huit (quatre semaines, pas un mois calendaire) pour
    `monthly`. Toutes les sauvegardes prises dans une même période constituent le même point de
    restauration, et c'est la plus récente d'entre elles qui le représente.

    `BACKUP_ROTATION` est à la fois le budget de fichiers et la profondeur de l'échelle : elle
    construit `BACKUP_ROTATION - 1` niveaux, le niveau `k` découpant la ligne du temps en blocs
    fixes de `2^k` périodes et conservant la sauvegarde la plus ancienne de ses deux blocs non vides
    les plus récents, la sauvegarde la plus récente étant toujours épinglée par-dessus. Chaque
    niveau coûte au plus un fichier de plus que celui du dessous, si bien que toute l'échelle tient
    dans le budget — tandis que sa portée double à chaque niveau. Ses blocs les plus profonds font
    `2^(BACKUP_ROTATION - 2)` périodes de large : sur une planification quotidienne, le point de
    restauration le plus ancien se situe donc entre **32 et 63 jours** en arrière avec le
    `BACKUP_ROTATION: "7"` par défaut, et entre **1024 et 2047 jours** à `"12"` — le nombre de
    fichiers croît linéairement, la profondeur exponentiellement. À budget égal, `fifo` ne remonte
    jamais au-delà de `BACKUP_ROTATION` périodes.

    Les blocs reposent sur une grille absolue plutôt que sur des fenêtres mesurées depuis
    aujourd'hui, et c'est ce qui rend une suppression sûre : une sauvegarde que l'échelle laisse
    partir ne pourra jamais être redemandée, donc les niveaux profonds ne se vident pas avec le
    temps. Cela signifie aussi que l'échelle **se remplit à mesure que l'archive vieillit** —
    atteindre le niveau `k` demande `2^k` périodes, donc une installation jeune conserve tout ce
    qu'elle a et les points de restauration profonds apparaissent en vieillissant. En attendant, le
    budget non dépensé va aux sauvegardes les plus récentes, à pleine granularité.

!!! info "Comment les sauvegardes sont datées"
    La rotation lit l'horodatage présent dans le nom de chaque archive. Une archive dont le nom n'en
    porte pas d'utilisable — un fichier copié à la main, ou renommé — est datée par sa date de
    modification, sous les deux stratégies.
