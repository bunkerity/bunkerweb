# Installing CRS

This guide aims to get a CRS installation up and running. This guide assumes that a compatible ModSecurity engine is already present and working. If unsure then refer to the [extended install](https://coreruleset.org/docs/deployment/extended_install/) page for full details.

## Downloading the Rule Set

The first step is to download the CRS itself. The CRS project strongly recommends using a [supported version](https://github.com/coreruleset/coreruleset/security/policy).

Official CRS releases can be found at the following URL: https://github.com/coreruleset/coreruleset/releases.

### Verifying Releases

{{% notice note %}}
Releases are signed using the CRS project's [GPG key](https://coreruleset.org/security.asc) (fingerprint: 3600 6F0E 0BA1 6783 2158 8211 38EE ACA1 AB8A 6E72). Releases can be verified using GPG/PGP compatible tooling.

To retrieve the CRS project's public key from public key servers using `gpg`, execute: `gpg --keyserver pgp.mit.edu --recv 0x38EEACA1AB8A6E72` (this ID should be equal to the last sixteen hex characters in the fingerprint).

It is also possible to use `gpg --fetch-key https://coreruleset.org/security.asc` to retrieve the key directly.
{{% /notice %}}

The following steps assume that a \*nix operating system is being used. Installation is similar on Windows but likely involves using a zip file from the CRS [releases page](https://github.com/coreruleset/coreruleset/releases).

To download the release file and the corresponding signature:

```bash
wget https://github.com/coreruleset/coreruleset/archive/refs/tags/v4.0.0.tar.gz
wget https://github.com/coreruleset/coreruleset/releases/download/v4.0.0/coreruleset-4.0.0.tar.gz.asc
```

To verify the integrity of the release:

```bash
gpg --verify coreruleset-4.0.0.tar.gz.asc v4.0.0.tar.gz
gpg: Signature made Wed Jun 30 10:05:48 2021 -03
gpg:                using RSA key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg: Good signature from "OWASP Core Rule Set <security@coreruleset.org>" [unknown]
gpg: WARNING: This key is not certified with a trusted signature!
gpg:          There is no indication that the signature belongs to the owner.
Primary key fingerprint: 3600 6F0E 0BA1 6783 2158  8211 38EE ACA1 AB8A 6E72
```

If the signature was good then the verification succeeds. If a warning is displayed, like the above, it means the CRS project's public key is *known* but is not *trusted*.

To trust the CRS project's public key:

```bash
gpg --edit-key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg> trust
Your decision: 5 (ultimate trust)
Are you sure: Yes
gpg> quit
```

The result when verifying a release will then look like so:

```bash
gpg --verify coreruleset-4.0.0.tar.gz.asc v4.0.0.tar.gz
gpg: Signature made Wed Jun 30 15:05:48 2021 CEST
gpg:                using RSA key 36006F0E0BA167832158821138EEACA1AB8A6E72
gpg: Good signature from "OWASP Core Rule Set <security@coreruleset.org>" [ultimate]
```

## Installing the Rule Set

### Extracting the Files

Once the rule set has been downloaded and verified, extract the rule set files to a well known location on the server. This will typically be somewhere in the web server directory.

The examples presented below demonstrate using Apache. For information on configuring Nginx or IIS see the [extended install](https://coreruleset.org/docs/deployment/extended_install/) page.

Note that while it's common practice to make a new `modsecurity.d` folder, as outlined below, this isn't strictly necessary. The path scheme outlined is common on RHEL-based operating systems; the Apache path used may need to be adjusted to match the server's installation.

```bash
mkdir /etc/crs4
tar -xzvf v4.0.0.tar.gz --strip-components 1 -C /etc/crs4
```

Now all the CRS files will be located below the `/etc/crs4` directory.

### Setting Up the Main Configuration File

After extracting the rule set files, the next step is to set up the main OWASP CRS configuration file. An example configuration file is provided as part of the release package, located in the main directory: `crs-setup.conf.example`.

{{% notice note %}}
Other aspects of ModSecurity, particularly engine-specific parameters, are controlled by the ModSecurity "recommended" configuration rules, `modsecurity.conf-recommended`. This file comes packaged with ModSecurity itself.
{{% /notice %}}

In many scenarios, the default example CRS configuration will be a good enough starting point. It is, however, a good idea to take the time to look through the example configuration file *before* deploying it to make sure it's right for a given environment.

Once any settings have been changed within the example configuration file, as needed, it should be renamed to remove the .example portion, like so:

```bash
cd /etc/crs4
mv crs-setup.conf.example crs-setup.conf
```

### Include-ing the Rule Files

The last step is to tell the web server where the rules are. This is achieved by `include`-ing the rule configuration files in the `httpd.conf` file. Again, this example demonstrates using Apache, but the process is similar on other systems (see the [extended install](https://coreruleset.org/docs/deployment/extended_install/) page for details).

```bash
echo 'IncludeOptional /etc/crs4/crs-setup.conf' >> /etc/httpd/conf/httpd.conf
echo 'IncludeOptional /etc/crs4/plugins/*-config.conf' >> /etc/httpd/conf/httpd.conf
echo 'IncludeOptional /etc/crs4/plugins/*-before.conf' >> /etc/httpd/conf/httpd.conf
echo 'IncludeOptional /etc/crs4/rules/*.conf' >> /etc/httpd/conf/httpd.conf
echo 'IncludeOptional /etc/crs4/plugins/*-after.conf' >> /etc/httpd/conf/httpd.conf
```

Now that everything has been configured, it should be possible to restart and being using the OWASP CRS. The CRS rules typically require a bit of tuning with rule exclusions, depending on the site and web applications in question. For more information on tuning, see [false positives and tuning](https://coreruleset.org/docs/concepts/false_positives_tuning/).

```bash
systemctl restart httpd.service
```

## Alternative: Using Containers

Another quick option is to use the official CRS [pre-packaged containers](https://coreruleset.org/docs/development/useful_tools/#official-crs-maintained-docker-images). Docker, Podman, or any compatible container engine can be used. The official CRS images are published in the Docker Hub. The image most often deployed is `owasp/modsecurity-crs`: it already has everything needed to get up and running quickly.

The CRS project pre-packages both Apache and Nginx web servers along with the appropriate corresponding ModSecurity engine. More engines, like [Coraza](https://coraza.io/), will be added at a later date.

To protect a running web server, all that's required is to get the appropriate image and set its configuration variables to make the WAF receives requests and proxies them to your backend server.

Below is an example `docker-compose` file that can be used to pull the container images. All that needs to be changed is the `BACKEND` variable so that the WAF points to the backend server in question:

```docker-compose
services:
  modsec2-apache:
    container_name: modsec2-apache
    image: owasp/modsecurity-crs:apache
    environment:
      SERVERNAME: modsec2-apache
      BACKEND: http://<backend server>
      PORT: "80"
      MODSEC_RULE_ENGINE: DetectionOnly
      BLOCKING_PARANOIA: 2
      TZ: "${TZ}"
      ERRORLOG: "/var/log/error.log"
      ACCESSLOG: "/var/log/access.log"
      MODSEC_AUDIT_LOG_FORMAT: Native
      MODSEC_AUDIT_LOG_TYPE: Serial
      MODSEC_AUDIT_LOG: "/var/log/modsec_audit.log"
      MODSEC_TMP_DIR: "/tmp"
      MODSEC_RESP_BODY_ACCESS: "On"
      MODSEC_RESP_BODY_MIMETYPE: "text/plain text/html text/xml application/json"
      COMBINED_FILE_SIZES: "65535"
    volumes:
    ports:
      - "80:80"
```

That's all that needs to be done. Simply starting the container described above will instantly provide the protection of the latest stable CRS release in front of a given backend server or service. There are [lots of additional variables](https://github.com/coreruleset/modsecurity-crs-docker) that can be used to configure the container image and its behavior, so be sure to read the full documentation.

## Verifying that the CRS is active

Always verify that CRS is installed correctly by sending a 'malicious' request to your site or application, for instance:

```bash
curl 'https://www.example.com/?foo=/etc/passwd&bar=/bin/sh'
```

Depending on your configurated thresholds, this should be detected as a malicious request. If you use blocking mode, you should receive an Error 403. The request should also be logged to the audit log, which is usually in `/var/log/modsec_audit.log`.

## Upgrading

### Upgrading from CRS 3.x to CRS 4

The most impactful change is the removal of application exclusion packages in favor of a plugin system. If you had activated the exclusion packages in CRS 3, you should download the plugins for them and place them in the plugins subdirectory. We maintain the list of plugins in our [Plugin Registry](https://github.com/coreruleset/plugin-registry). You can find detailed information on working with plugins in our [plugins documentation]()https://coreruleset.org/docs/concepts/plugins/.

In terms of changes to the detection rules, the amount of changes is smaller than in the CRS 2—3 changeover. Most rules have only evolved slightly, so it is recommended that you keep any existing custom exclusions that you have made under CRS 3.

We recommend to start over by copying our `crs-setup.conf.example` to `crs-setup.conf` with a copy of your old file at hand, and re-do the customizations that you had under CRS 3.

Please note that we added a large number of new detections, and any new detection brings a certain risk of false alarms. Therefore, we recommend to test first before going live.

### Upgrading from CRS 2.x to CRS 3

In general, you can update by unzipping our new release over your older one, and updating the `crs-setup.conf` file with any new settings.  However, CRS 3.0 is a major rewrite, incompatible with CRS 2.x. Key setup variables have changed their name, and new features have been introduced. Your former modsecurity_crs_10_setup.conf file is thus no longer usable. We recommend you to start with a fresh crs-setup.conf file from scratch.

Most rule IDs have been changed to reorganize them into logical sections. This means that if you have written custom configuration with exclusion rules (e.g. `SecRuleRemoveById`, `SecRuleRemoveTargetById`, `ctl:ruleRemoveById` or `ctl:ruleRemoveTargetById`) you must renumber the rule numbers in that configuration. You can do this using the supplied utility util/id_renumbering/update.py or find the changes in util/id_renumbering/IdNumbering.csv.

However, a key feature of the CRS 3 is the reduction of false positives in the default installation, and many of your old exclusion rules may no longer be necessary. Therefore, it is a good option to start fresh without your old exclusion rules.

If you are experienced in writing exclusion rules for CRS 2.x, it may be worthwhile to try running CRS 3 in Paranoia Level 2 (PL2). This is a stricter mode, which blocks additional attack patterns, but brings a higher number of false positives — in many situations the false positives will be comparable with CRS 2.x. This paranoia level however will bring you a higher protection level than CRS 2.x or a CRS 3 default install, so it can be worth the investment.
