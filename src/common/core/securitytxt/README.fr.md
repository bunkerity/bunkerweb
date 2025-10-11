Le plugin Security.txt met en œuvre le standard [Security.txt](https://securitytxt.org/) ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) sur votre site. Il facilite l’accès aux politiques de sécurité et fournit un moyen standardisé de signaler des vulnérabilités.

Comment ça marche :

1. Une fois activé, BunkerWeb expose `/.well-known/security.txt` à la racine du site.
2. Le fichier contient vos politiques, contacts et informations pertinentes.
3. Les chercheurs en sécurité et outils automatisés le trouvent à l’emplacement standard.
4. Le contenu est défini via des paramètres simples (contacts, clés de chiffrement, politiques, remerciements…).
5. BunkerWeb formate automatiquement selon la RFC 9116.

### Comment l’utiliser

1. Activer : `USE_SECURITYTXT: yes`.
2. Contacts : précisez au moins un moyen de contact via `SECURITYTXT_CONTACT`.
3. Informations additionnelles : configurez expiration, chiffrement, remerciements, URL de politique…

### Paramètres

| Paramètre                      | Défaut                      | Contexte  | Multiple | Description                                                 |
| ------------------------------ | --------------------------- | --------- | -------- | ----------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | non      | Activer le fichier security.txt.                            |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | non      | URI d’accès au fichier.                                     |
| `SECURITYTXT_CONTACT`          |                             | multisite | oui      | Moyens de contact (ex. `mailto:security@example.com`).      |
| `SECURITYTXT_EXPIRES`          |                             | multisite | non      | Date d’expiration (format ISO 8601).                        |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | oui      | URL de clés de chiffrement pour échanges sécurisés.         |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | oui      | URL de remerciements pour les chercheurs.                   |
| `SECURITYTXT_POLICY`           |                             | multisite | oui      | URL de la politique de sécurité (procédure de signalement). |
| `SECURITYTXT_HIRING`           |                             | multisite | oui      | URL d’offres d’emploi sécurité.                             |
| `SECURITYTXT_CANONICAL`        |                             | multisite | oui      | URL canonique du fichier security.txt.                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | non      | Langue préférée (code ISO 639‑1).                           |
| `SECURITYTXT_CSAF`             |                             | multisite | oui      | Lien vers le provider-metadata.json du fournisseur CSAF.    |

!!! warning "Expiration requise"
    Le champ `Expires` est obligatoire. Si absent, BunkerWeb définit par défaut une expiration à un an.

!!! info "Contacts essentiels"
    Fournissez au moins un moyen de contact : email, formulaire, téléphone, etc.

!!! warning "HTTPS obligatoire"
    Toutes les URLs (sauf `mailto:` et `tel:`) DOIVENT utiliser HTTPS. BunkerWeb convertit les URL non‑HTTPS pour la conformité.

### Exemples

=== "Basique"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Complet"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Contacts multiples"

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```
