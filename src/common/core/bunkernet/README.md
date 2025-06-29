# BunkerNet Plugin

The BunkerNet plugin enables collective threat intelligence sharing between 
BunkerWeb instances, creating a powerful network of protection against 
malicious actors. By participating in BunkerNet, your instance both benefits 
from and contributes to a global database of known threats, enhancing 
security for the entire BunkerWeb community.

## How it works

1. Your BunkerWeb instance automatically registers with the BunkerNet API to 
   receive a unique identifier.
2. When your instance detects and blocks a malicious IP address or behavior, 
   it anonymously reports the threat to BunkerNet.
3. BunkerNet aggregates threat intelligence from all participating instances 
   and distributes the consolidated database.
4. Your instance regularly downloads an updated database of known threats 
   from BunkerNet.
5. This collective intelligence allows your instance to proactively block IP 
   addresses that have exhibited malicious behavior on other BunkerWeb 
   instances.

!!! success "Key benefits"

      1. **Collective Defense:** Leverage the security findings from thousands 
         of other BunkerWeb instances globally.
      2. **Proactive Protection:** Block malicious actors before they can 
         target your site based on their behavior elsewhere.
      3. **Community Contribution:** Help protect other BunkerWeb users by 
         sharing anonymized threat data about attackers.
      4. **Zero Configuration:** Works out of the box with sensible defaults, 
         requiring minimal setup.
      5. **Privacy Focused:** Only shares necessary threat information without 
         compromising your or your users' privacy.

## How to Use

Follow these steps to configure and use the BunkerNet feature:

1. **Enable the feature:** The BunkerNet feature is enabled by default. If 
   needed, you can control this with the `USE_BUNKERNET` setting.
2. **Initial registration:** Upon first startup, your instance will 
   automatically register with the BunkerNet API and receive a unique 
   identifier.
3. **Automatic updates:** Your instance will automatically download the 
   latest threat database on a regular schedule.
4. **Automatic reporting:** When your instance blocks a malicious IP address, 
   it will automatically contribute this data to the community.
5. **Monitor protection:** Check the [web UI](web-ui.md) to see statistics on 
   threats blocked by BunkerNet intelligence.

## Configuration Settings

| Setting            | Default                    | Context   | Multiple | Description                                                                                    |
| ------------------ | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Enable BunkerNet:** Set to `yes` to enable the BunkerNet threat intelligence sharing.        |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **BunkerNet Server:** The address of the BunkerNet API server for sharing threat intelligence. |

!!! tip "Network Protection"
    When BunkerNet detects that an IP address has been involved in malicious 
    activity across multiple BunkerWeb instances, it adds that IP to a 
    collective blacklist. This provides a proactive defense layer, protecting 
    your site from threats before they can target you directly.

!!! info "Anonymous Reporting"
    When reporting threat information to BunkerNet, your instance only shares 
    the necessary data to identify the threat: the IP address, the reason for 
    blocking, and minimal contextual data. No personal information about your 
    users or sensitive details about your site is shared.

## Example Configurations

### Default Configuration (Recommended)

The default configuration enables BunkerNet with the official BunkerWeb API 
server:

```yaml
USE_BUNKERNET: "yes"
BUNKERNET_SERVER: "https://api.bunkerweb.io"
```

### Disabled Configuration

If you prefer not to participate in the BunkerNet threat intelligence 
network:

```yaml
USE_BUNKERNET: "no"
```

### Custom Server Configuration

For organizations running their own BunkerNet server (uncommon):

```yaml
USE_BUNKERNET: "yes"
BUNKERNET_SERVER: "https://bunkernet.example.com"
```

## CrowdSec Console Integration

If you aren't already familiar with CrowdSec Console integration, 
[CrowdSec](https://www.crowdsec.net/?utm_campaign=bunkerweb&utm_source=doc) 
leverages crowdsourced intelligence to combat cyber threats. Think of it as 
the "Waze of cybersecurity"—when one server is attacked, other systems 
worldwide are alerted and protected from the same attackers. You can learn 
more about it [here](https://www.crowdsec.net/about?utm_campaign=bunkerweb&utm_source=blog).

Through our partnership with CrowdSec, you can enroll your BunkerWeb 
instances into your [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration). 
This means that attacks blocked by BunkerWeb will be visible in your CrowdSec 
Console alongside attacks blocked by CrowdSec Security Engines, giving you a 
unified view of threats.

Importantly, CrowdSec does not need to be installed for this integration 
(though we highly recommend trying it out with the 
[CrowdSec plugin for BunkerWeb](https://github.com/bunkerity/bunkerweb-plugins/tree/main/crowdsec) 
to further enhance the security of your web services). Additionally, you can 
enroll your CrowdSec Security Engines into the same Console account for even 
greater synergy.

### Step #1: Create your CrowdSec Console account

Go to the [CrowdSec Console](https://app.crowdsec.net/signup?utm_source=external-blog&utm_medium=cta&utm_campaign=bunker-web-integration) 
and register if you don't already have an account. Once done, note the enroll 
key found under "Security Engines" after clicking on "Add Security Engine":

<figure markdown>
  ![Overview](assets/img/crowdity1.png){ align=center }
  <figcaption>Get your Crowdsec Console enroll key</figcaption>
</figure>

### Step #2: Get your BunkerNet ID

Activating the BunkerNet feature (enabled by default) is mandatory if you 
want to enroll your BunkerWeb instance(s) in your CrowdSec Console. Enable 
it by setting `USE_BUNKERNET` to `yes`.

For Docker, get your BunkerNet ID using:

```shell
docker exec my-bw-scheduler cat /var/cache/bunkerweb/bunkernet/instance.id
```

For Linux, use:

```shell
cat /var/cache/bunkerweb/bunkernet/instance.id
```

### Step #3: Enroll your instance using the Panel

Once you have your BunkerNet ID and CrowdSec Console enroll key, 
[order the free product "BunkerNet / CrowdSec" on the Panel](https://panel.bunkerweb.io/store/bunkernet?utm_campaign=self&utm_source=doc). 
You may be prompted to create an account if you haven't already.

You can now select the "BunkerNet / CrowdSec" service and fill out the form 
by pasting your BunkerNet ID and CrowdSec Console enroll key:

<figure markdown>
  ![Overview](assets/img/crowdity2.png){ align=center }
  <figcaption>Enroll your BunkerWeb instance into the CrowdSec Console</figcaption>
</figure>

### Step #4: Accept the new security engine on the Console

Then, go back to your CrowdSec Console and accept the new Security Engine:

<figure markdown>
  ![Overview](assets/img/crowdity3.png){ align=center }
  <figcaption>Accept enroll into the CrowdSec Console</figcaption>
</figure>

**Congratulations, your BunkerWeb instance is now enrolled in your CrowdSec 
Console!**

Pro tip: When viewing your alerts, click the "columns" option and check the 
"context" checkbox to access BunkerWeb-specific data.

<figure markdown>
  ![Overview](assets/img/crowdity4.png){ align=center }
  <figcaption>BunkerWeb data shown in the context column</figcaption>
</figure>
