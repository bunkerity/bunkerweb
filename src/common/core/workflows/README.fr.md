Le plugin Workflows ajoute une couche de politiques entre les paramètres individuels et les protections Lua : des règles réutilisables et ordonnées, attachées aux services, associant chacune un arbre de conditions à une action.

Une règle exprime une condition que les paramètres individuels ne peuvent pas représenter seuls :

> **Si** la requête vient de France **et** cible `/login`, **et** dépasse 10 requêtes par minute, **alors** afficher un défi hCaptcha.

Les workflows **orchestrent** les protections existantes. Une action `challenge` confie la requête à Antibot ; un seuil de débit utilise le même compteur que Limit. Vos paramètres existants continuent de fonctionner.

### Évaluation d'une règle

Les workflows attachés à un service sont évalués dans l'ordre d'attachement, puis leurs règles dans l'ordre choisi. **La première règle qui correspond effectivement l'emporte** et exécute son unique action ; les suivantes ne sont pas évaluées.

Une condition est un arbre de nœuds `ALL` / `ANY` / `NOT` portant sur :

| Condition | Critère |
| --------- | ------- |
| IP / CIDR | IP effective du client après résolution Real-IP |
| Pays | Pays ISO obtenu depuis GeoIP |
| ASN | Numéro de système autonome de l'IP du client |
| URI | Chemin normalisé : exact, préfixe ou expression régulière |
| Méthode HTTP | Méthode de la requête |
| Groupe de ressources | Groupe d'IP, de pays ou d'ASN maintenu séparément et référencé par son identifiant |
| Verdict CrowdSec | Décision de CrowdSec : source (`appsec` ou `lapi`) et remédiation demandée (`ban` ou `captcha`) |

Les conditions ont **trois valeurs** : vrai, faux ou *inconnu* si l'information nécessaire manque, par exemple si GeoIP est indisponible. Une règle ne correspond que lorsque son arbre vaut vrai : une base défaillante cesse de produire des correspondances au lieu d'en créer accidentellement.

Une condition **verdict CrowdSec** est indéterminée si CrowdSec n'a pas évalué le service, et fausse si CrowdSec a évalué la requête sans rien lui reprocher. Aucun de ces cas ne correspond. Pour qu'un workflow réponde *à la place* de CrowdSec, définissez `CROWDSEC_DEFER_TO_WORKFLOWS=yes` sur le service : CrowdSec transmet son verdict sans l'appliquer. Si aucune règle ne correspond, ce verdict est appliqué tel quel.

### Les seuils de débit conditionnent la correspondance

Une règle peut porter un seuil. Il décide **si la règle correspond**, sans être une action de limitation. Sous le seuil, l'évaluation continue avec la règle suivante.

Deux règles ordonnées avec les mêmes conditions permettent ainsi d'exprimer « au-delà de 10 requêtes par minute, répondre 429 ; sinon afficher un défi » : la première porte le seuil et bloque, la deuxième n'a pas de seuil.

Le compteur est propre au service, à la règle et à l'IP du client ; il n'interfère pas avec les compteurs `LIMIT_REQ_*`.

### Actions

- **challenge** — afficher un fournisseur Antibot précis (`captcha`, `hcaptcha`, `turnstile`, …), même avec `USE_ANTIBOT=no`. Cette action ignore les listes d'exclusion d'Antibot : placez les exceptions dans les conditions de la règle. Les identifiants du fournisseur doivent déjà être configurés sur le service.
- **block** — répondre avec le code de refus de l'instance, ou `429` pour une règle limitant le débit.
- **redirect** — rediriger le client vers une URL fixe avec un code 301/302/303/307/308.

### Mode détection

`SECURITY_MODE=detect` évalue les mêmes arbres, dans le même ordre et avec les mêmes compteurs, sans appliquer d'action. L'action qui *aurait* été appliquée figure dans les rapports, afin de mesurer une politique sur du trafic réel avant son activation.

### Comportement en cas d'échec

Une instance qui n'a pas reçu la politique compilée (premier démarrage ou envoi manquant) journalise une erreur et conserve ses protections ordinaires. Une politique que le plan de contrôle ne peut pas compiler n'est jamais distribuée : l'envoi est abandonné et les instances conservent leur politique précédente. La suppression d'un groupe de ressources référencé par une règle est refusée tant que cette règle existe.

### Budget d'expressions régulières

| Paramètre | Défaut | Contexte | Multiple | Description |
| --------- | ------ | -------- | -------- | ----------- |
| `WORKFLOWS_REGEX_BUDGET` | `512` | global | no | **Budget regex :** nombre maximal d'expressions régulières distinctes compilées pour toutes les règles. Le cache regex de NGINX étant partagé entre plugins, les règles dépassant ce budget sont désactivées pour éviter de dégrader silencieusement toute l'instance. |

La compilation parcourt les workflows par identifiant trié et consomme le budget progressivement. Si celui-ci est épuisé au milieu d'un artefact, les règles restantes sont désactivées, selon un ordre déterministe : deux instances chargeant le même artefact désactivent les mêmes règles.

### Gestion des workflows

Utilisez la page **Workflows** de l'interface Web ou les routes API `/workflows`. Les règles sont stockées de manière centralisée puis compilées en un artefact unique, distribué aux instances avec la configuration habituelle.
