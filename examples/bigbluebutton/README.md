# BigBlueButton behind BunkerWeb

This Docker example adds BunkerWeb in front of the [BigBlueButton Docker stack](https://github.com/bigbluebutton/docker). The accompanying [docker-compose.yml](docker-compose.yml) is an integration template with `...` placeholders: merge its changes into the upstream generated Compose file before starting the stack.

## Docker integration

1. Generate the upstream BigBlueButton stack with its setup script. Include Greenlight, disable its automatic HTTPS proxy, and set your domain.
2. In the generated Compose file, remove `network_mode: host` from the `nginx` service and attach it to `bbb-net` with address `10.7.7.253`, as shown in the template. Check that this address is available on the upstream network.
3. Add the `bunkerweb` and `bw-scheduler` services from the template. BunkerWeb joins `bbb-net` at `10.7.7.254` and the shared `bw-universe` network; the scheduler joins `bw-universe`. Keep the API whitelist consistent with that network's subnet.
4. Add the `bw-storage` volume and `bw-universe` network definitions, preserving the other upstream services, volumes, and networks. Replace every placeholder with the corresponding upstream content.
5. Set `DOMAIN` to your public domain. The scheduler enables HTTPS certificates, proxies to the upstream NGINX service at `http://10.7.7.253:8080`, and enables WebSocket forwarding. Point DNS at the BunkerWeb host and make ports 80 and 443 reachable for web traffic and the HTTP certificate challenge.
6. Start the merged stack using the upstream Docker procedure. Check the web interface and a meeting's audio/video connectivity; the template only changes the web proxy and does not configure BigBlueButton's media networking.

Review the upstream deployment requirements for your chosen BigBlueButton version before using this integration.
