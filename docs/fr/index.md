# Introduction

## Aperçu

<figure markdown>
  ![Vue d'ensemble](assets/img/intro-overview.svg){ align=center, width="800 » }
  <figcaption>Sécurisez vos services web par défaut !</figcaption>
</figure>

BunkerWeb est un pare-feu applicatif (WAF) open-source de nouvelle génération.

En tant que serveur Web complet (basé sur [NGINX](https://nginx.org/) sous le capot), il protège vos services Web pour les rendre "sécurisés par défaut". BunkerWeb s'intègre parfaitement à vos environnements existants ([Linux](integrations.md#linux), [Docker](integrations.md#docker), [Swarm](integrations.md#swarm), [Kubernetes](integrations.md#kubernetes), ...) en tant que proxy inverse et est entièrement configurable (pas de panique, il y a une [interface utilisateur web géniale](web-ui.md) si vous n'aimez pas la CLI) pour répondre à vos cas d'utilisation spécifiques. En d'autres termes, la cybersécurité n'est plus un problème.

BunkerWeb inclut  des [fonctionnalités de sécurité primaires ](advanced.md#security-tuning) dans le cadre du noyau, mais peut être facilement étendu avec des fonctionnalités supplémentaires grâce à un système de [plugins](plugins.md).

## Pourquoi BunkerWeb ?

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/oybLtyhWJIo" title="BunkerWeb overview" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

- **Intégration facile dans les environnements existants**: Intégrez de manière transparente BunkerWeb dans divers environnements tels que Linux, Docker, Swarm, Kubernetes, etc. Profitez d'une transition en douceur et d'une mise en œuvre sans tracas.

- **Hautement personnalisable**: Adaptez facilement BunkerWeb à vos besoins spécifiques. Activez, désactivez et configurez des fonctionnalités sans effort, ce qui vous permet de personnaliser les paramètres de sécurité en fonction de votre cas d'utilisation unique.

- **Sécurisé par défaut**: BunkerWeb fournit une sécurité minimale prête à l'emploi et sans tracas pour vos services Web. Faites l'expérience de la tranquillité d'esprit et d'une protection renforcée dès le départ.

- **Interface utilisateur Web impressionnante**: Prenez le contrôle de BunkerWeb plus efficacement grâce à l'interface utilisateur Web (UI) exceptionnelle. Naviguez sans effort dans les paramètres et les configurations grâce à une interface graphique conviviale, éliminant ainsi le besoin d'une interface de ligne de commande (CLI).

- **Système de plugins**: Étendez les capacités de BunkerWeb pour répondre à vos propres cas d'utilisation. Intégrez de manière transparente des mesures de sécurité supplémentaires et personnalisez les fonctionnalités de BunkerWeb en fonction de vos besoins spécifiques.

- **Libre comme dans "liberté"**: BunkerWeb est sous la [licence gratuite AGPLv3](https://www.gnu.org/licenses/agpl-3.0.fr.html), embrassant les principes de liberté et d'ouverture. Profitez de la liberté d'utiliser, de modifier et de distribuer le logiciel, avec le soutien d'une communauté qui vous soutient.

- **Services professionnels**: Obtenez une assistance technique, des conseils sur mesure et un développement personnalisé directement auprès des responsables de BunkerWeb. Visitez le [panel BunkerWeb](https://panel.bunkerweb.io/?language=french&utm_campaign=self&utm_source=doc) pour plus d'informations.

## Caractéristiques de sécurité

Explorez l'impressionnante gamme de fonctionnalités de sécurité offertes par BunkerWeb. Bien qu'ils ne soient pas exhaustifs, voici quelques faits saillants notables:

- Prise en charge **HTTPS** avec l'automatisation transparente de **Let's Encrypt**: Sécurisez facilement vos services Web grâce à l'intégration automatisée de Let's Encrypt, qui garantit une communication cryptée entre les clients et votre serveur.

- **Sécurité Web de pointe**: bénéficiez de mesures de sécurité Web de pointe, notamment des en-têtes de sécurité HTTP complets, la prévention des fuites de données et les techniques de renforcement TLS.

- Le **WAF ModSecurity** intégré avec l'**ensemble de règles de base OWASP**: Profitez d'une protection renforcée contre les attaques d'applications Web grâce à l'intégration de ModSecurity, renforcée par le célèbre ensemble de règles de base OWASP.

- **Bannissement automatique** des comportements étranges sur la base de codes d'état HTTP: BunkerWeb identifie et bloque intelligemment les activités suspectes en bannissant automatiquement les comportements qui déclenchent des codes d'état HTTP anormaux.

- Appliquer des **limites de connexion et de demande** pour les clients: Fixez des limites au nombre de connexions et de demandes des clients, afin d'éviter l'épuisement des ressources et de garantir une utilisation équitable des ressources du serveur.

- **Bloquez les bots** grâce à la **vérification basée sur les défis**: tenez les bots malveillants à distance en les mettant au défi de résoudre des énigmes telles que les cookies, les tests JavaScript, les captchas, les hCaptcha, les reCAPTCHA ou les tourniquets, bloquant ainsi efficacement les accès non autorisés.

- **Bloquez les adresses IP malveillantes connues** à l'aide de listes noires externes et de **DNSBL**: utilisez des listes noires externes et des listes de trous noirs basées sur DNS (DNSBL) pour bloquer de manière proactive les adresses IP malveillantes connues, renforçant ainsi votre défense contre les menaces potentielles.

- **Et bien plus encore...**: BunkerWeb regorge d'une pléthore de fonctionnalités de sécurité supplémentaires qui vont au-delà de cette liste, vous offrant une protection complète et une tranquillité d'esprit.

Pour en savoir plus sur les principales fonctionnalités de sécurité, nous vous invitons à explorer la [ section sur le réglage](advanced.md#security-tuning) de la sécurité de la documentation. Découvrez comment BunkerWeb vous permet d'affiner et d'optimiser les mesures de sécurité en fonction de vos besoins spécifiques.

## Démonstration

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/ZhYV-QELzA4" title="Fooling automated tools and scanners" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

Un site web de démonstration protégé par BunkerWeb est disponible à l'adresse [demo.bunkerweb.io](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc). N'hésitez pas à le visiter et à effectuer quelques tests de sécurité.

## Interface utilisateur Web

<p align="center">
    <iframe style="display: block;" width="560" height="315" data-src="https://www.youtube-nocookie.com/embed/tGS3pzquEjY" title="BunkerWeb web UI" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
</p>

BunkerWeb propose une [interface utilisateur optionnelle ](web-ui.md) pour gérer vos instances et leurs configurations. Une démo en ligne en lecture seule est disponible à l'adresse [demo-ui.bunkerweb.io](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc). N'hésitez pas à le tester vous-même.

## BunkerWeb Cloud

<figure markdown>
  ![Vue d'ensemble](assets/img/bunkerweb-cloud.webp){ align=center, width="600" }
  <figcaption>BunkerWeb Cloud</figcaption>
</figure>

Vous ne voulez pas auto-héberger et gérer votre propre instance BunkerWeb ? Vous pourriez être intéressé par BunkerWeb Cloud, notre offre SaaS entièrement gérée pour BunkerWeb.

Commandez votre [instance BunkerWeb Cloud](https://panel.bunkerweb.io/store/bunkerweb-cloud?utm_campaign=self&utm_source=doc) et accédez à :

- Une instance BunkerWeb entièrement gérée et hébergée dans notre cloud
- Toutes les fonctionnalités de BunkerWeb, y compris les fonctionnalités PRO
- Une plateforme de surveillance avec tableaux de bord et alertes
- Support technique pour vous aider dans la configuration

Si vous êtes intéressé par l'offre BunkerWeb Cloud, n'hésitez pas à [nous contacter](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) afin que nous puissions discuter de vos besoins.

## Version PRO

!!! tip "BunkerWeb PRO essai gratuit"
    Vous souhaitez tester rapidement BunkerWeb PRO pendant un mois ? Utilisez le code `freetrial` lors de votre commande sur le [Panel BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc) ou en cliquant [ici](https://panel.bunkerweb.io/cart.php?language=french&a=add&pid=19&promocode=freetrial&utm_campaign=self&utm_source=doc) pour appliquer directement le code promo (sera effectif à la caisse).

Lorsque vous utilisez BunkerWeb, vous avez le choix de la version que vous souhaitez utiliser : open-source ou PRO.

Qu'il s'agisse d'une sécurité renforcée, d'une expérience utilisateur enrichie ou d'une surveillance technique, la version BunkerWeb PRO vous permet de profiter pleinement de BunkerWeb et de répondre à vos besoins professionnels.

Dans la documentation ou l'interface utilisateur, les fonctionnalités PRO sont annotées d'une couronne <img src="../../assets/img/pro-icon.svg" alt="crown pro icon" height="32px" width="32px"> pour les distinguer de celles intégrées dans la version open-source.

Vous pouvez passer de la version open-source à la version PRO facilement et à tout moment. Le processus est simple :

- Réclamez votre [essai gratuit sur le panneau BunkerWeb](https://panel.bunkerweb.io/store/bunkerweb-pro?language=french&utm_campaign=self&utm_source=doc) en utilisant le `freetrial` code promo à la caisse
- Une fois connecté à l'espace client, copiez votre clé de licence PRO
- Collez votre clé privée dans BunkerWeb à l'aide de l'[interface utilisateur Web](web-ui.md#upgrade-to-pro) ou [d'un paramètre spécifique](features.md#pro)

N'hésitez pas à visiter le [panel BunkerWeb](https://panel.bunkerweb.io/knowledgebase?language=french&utm_campaign=self&utm_source=doc) ou  à [nous contacter](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) si vous avez des questions concernant la version PRO.

## Services professionnels

Tirez le meilleur parti de BunkerWeb en accédant aux services professionnels directement des responsables du projet. De l'assistance technique au conseil et au développement sur mesure, nous sommes là pour vous aider à sécuriser vos services web.

Vous trouverez plus d'informations en visitant le [Panel BunkerWeb](https://panel.bunkerweb.io/?language=french&utm_campaign=self&utm_source=doc), notre plateforme dédiée aux services professionnels.

N'hésitez pas à [nous contacter](https://panel.bunkerweb.io/contact.php?language=french&utm_campaign=self&utm_source=doc) si vous avez des questions. Nous serons plus qu'heureux de répondre à vos besoins.

## Écosystème, communauté et ressources

Sites officiels, outils et ressources sur BunkerWeb :

- [**Site Web**](https://www.bunkerweb.io/?utm_campaign=self&utm_source=doc) : Obtenez plus d'informations, de nouvelles et d'articles sur BunkerWeb.
- [**Panel**](https://panel.bunkerweb.io/?language=french&utm_campaign=self&utm_source=doc): Une plate-forme dédiée pour commander et gérer des services professionnels (par exemple, le support technique) autour de BunkerWeb.
- [**Documentation**](https://docs.bunkerweb.io/fr/) : Documentation technique de la solution BunkerWeb.
- [**Démo**](https://demo.bunkerweb.io/?utm_campaign=self&utm_source=doc): Site de démonstration de BunkerWeb. N'hésitez pas à tenter des attaques pour tester la robustesse de la solution.
- [**Web UI**](https://demo-ui.bunkerweb.io/?utm_campaign=self&utm_source=doc): Démo en ligne en lecture seule de l'interface web de BunkerWeb.
- [**Carte des menaces**](https://www.bunkerweb.io/threatmap/?utm_campaign=self&utm_source=doc): Cyberattaques en direct bloquées par les instances BunkerWeb dans le monde entier.
- [**Statut**](https://status.bunkerweb.io/?utm_campaign=self&utm_source=doc): Suivi en direct de l'état et de la disponibilité des services BunkerWeb.

Communauté et réseaux sociaux :

- [**Discord**](https://discord.com/invite/fTf46FmtyD)
- [**Lien LinkedIn**](https://www.linkedin.com/company/bunkerity/)
- [**X (anciennement Twitter)**](https://x.com/bunkerity)
- [**Reddit**](https://www.reddit.com/r/BunkerWeb/)
