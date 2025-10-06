Le plugin Pro regroupe des fonctionnalités avancées pour les déploiements entreprise de BunkerWeb. Il déverrouille des capacités supplémentaires, des plugins premium et des extensions qui complètent la plateforme BunkerWeb, pour plus de sécurité, de performance et d’options de gestion.

Comment ça marche :

1. Avec une clé de licence Pro valide, BunkerWeb contacte l’API Pro pour valider votre abonnement.
2. Une fois authentifié, le plugin télécharge et installe automatiquement les plugins et extensions exclusifs Pro.
3. Le statut Pro est vérifié périodiquement afin d’assurer l’accès continu aux fonctionnalités premium.
4. Les plugins premium s’intègrent de façon transparente à votre configuration existante.
5. Les fonctionnalités Pro complètent le cœur open‑source, elles ne le remplacent pas.

!!! success "Bénéfices clés"

      1. Extensions premium : accès à des plugins et fonctions exclusives.
      2. Performances accrues : configurations optimisées et mécanismes avancés de cache.
      3. Support entreprise : assistance prioritaire et canaux dédiés.
      4. Intégration fluide : cohabite avec l’édition communautaire sans conflits.
      5. Mises à jour automatiques : plugins premium téléchargés et tenus à jour automatiquement.

### Comment l’utiliser

1. Obtenir une licence : achetez une licence Pro depuis le [BunkerWeb Panel](https://panel.bunkerweb.io/store/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2. Configurer la licence : définissez `PRO_LICENSE_KEY` avec votre clé.
3. Laissez BunkerWeb faire le reste : les plugins Pro sont téléchargés et activés automatiquement.
4. Surveiller le statut Pro : vérifiez les indicateurs de santé dans l’interface [web UI](web-ui.md).

### Paramètres

| Paramètre         | Défaut | Contexte | Multiple | Description                                      |
| ----------------- | ------ | -------- | -------- | ------------------------------------------------ |
| `PRO_LICENSE_KEY` |        | global   | non      | Clé de licence BunkerWeb Pro (authentification). |

!!! tip "Gestion de licence"
    La licence est liée à votre environnement de déploiement. Pour un transfert ou une question d’abonnement, contactez le support via le [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Fonctionnalités Pro"
    Le périmètre des fonctionnalités peut évoluer. Le plugin Pro gère automatiquement l’installation et la configuration des capacités disponibles.

!!! warning "Accès réseau"
    Le plugin Pro requiert un accès Internet sortant pour contacter l’API BunkerWeb (vérification de licence) et télécharger les plugins premium. Autorisez les connexions HTTPS vers `api.bunkerweb.io:443`.

### FAQ

Q : Que se passe‑t‑il si ma licence Pro expire ?

R : L’accès aux fonctionnalités premium est désactivé, mais votre installation continue de fonctionner avec l’édition communautaire. Pour réactiver les fonctionnalités Pro, renouvelez la licence.

Q : Les fonctionnalités Pro peuvent‑elles perturber ma configuration existante ?

R : Non. Elles sont conçues pour s’intégrer sans modifier votre configuration actuelle.

Q : Puis‑je essayer Pro avant achat ?

R : Oui. Deux offres existent :

- BunkerWeb PRO Standard : accès complet, sans support technique.
- BunkerWeb PRO Enterprise : accès complet, avec support dédié.

Un essai gratuit d’1 mois est disponible avec le code `freetrial`. Rendez‑vous sur le [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) pour l’activer.
