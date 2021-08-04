# ClamAV plugin

Automatically scan files with ClamAV when they are uploaded and deny the upload if the file is detected. See the [bunkerized-nginx-clamav](https://github.com/bunkerity/bunkerized-nginx-clamav) repository for more information.

## Preamble

This example uses a bunkerized-nginx plugin, you can have a look at the [documentation](https://bunkerized-nginx.readthedocs.io/en/latest/plugins.html) to get more information about plugins.

## Architecture

<img src="https://github.com/bunkerity/bunkerized-nginx/blob/dev/examples/clamav/architecture.png?raw=true" />

## Configuration

You will need to clone the bunkerized-nginx-clamav plugin and edit the **plugin.json** file.

## Docker

See [docker-compose.yml](https://github.com/bunkerity/bunkerized-nginx/blob/master/examples/clamav/docker-compose.yml).
