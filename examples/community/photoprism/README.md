Photoprism app configuration example for bunkerweb. The app works and synchronization with the android PhotoSync app also works for every funtion that was tested.

# Procedure:

Start with the photoprism [docker compose file][PhotoprismComposeFile]. The basic file (https://dl.photoprism.app/docker/docker-compose.yml) is taken from [photoprism documentation][PhotoprismDockerDocs]
Bunkerweb specific changes are noted with *"#For bunkerweb"* at the end of the line

Check and adapt the bunkerweb configuration. Use the example [docker compose file][BunkerwebComposeFile]. 
Photoprism specific changes are noted with *"#photoprism specific config"*.
Adapt the rest as needed for your configurations.

Start services with `docker-compose up -d`

Configure the bunkerweb ui (https://docs.bunkerweb.io/latest/web-ui/#setup-wizard).
Use the bunkerweb ui to upload the [modsec override file][AllowmediaConfig] to configs->modsec-crs->photos.example.com app specific folder.
If prefered, copy the file manually to a folder as described in the guide (https://docs.bunkerweb.io/latest/quickstart-guide/#custom-configurations). Place it under configs/modsec-crs/.

If using the provided configuration with autoconf enabled, the photoprism app should now be working without further intervention

[PhotoprismDockerDocs]: https://docs.photoprism.app/getting-started/docker-compose/
[PhotoprismComposeFile]: photoprism-compose.yml
[BunkerwebComposeFile]: docker-compose.yml
[AllowmediaConfig]: allowmedia.conf