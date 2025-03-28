The BunkerNet plugin enables collective threat intelligence sharing between BunkerWeb instances, creating a powerful network of protection against malicious actors. By participating in BunkerNet, your instance both benefits from and contributes to a global database of known threats, enhancing security for the entire BunkerWeb community.

**How it works:**

1. Your BunkerWeb instance automatically registers with the BunkerNet API to receive a unique identifier.
2. When your instance detects and blocks a malicious IP address or behavior, it anonymously reports this threat to BunkerNet.
3. BunkerNet aggregates threat intelligence from all participating instances and distributes the consolidated database.
4. Your instance regularly downloads an updated database of known threats from BunkerNet.
5. This collective intelligence allows your instance to proactively block IPs that have exhibited malicious behavior on other BunkerWeb instances.

!!! success "Key benefits"

      1. **Collective Defense:** Leverage the security findings from thousands of other BunkerWeb instances globally.
      2. **Proactive Protection:** Block malicious actors before they can target your site based on their behavior elsewhere.
      3. **Community Contribution:** Help protect other BunkerWeb users by sharing anonymized threat data about attackers.
      4. **Zero Configuration:** Works out of the box with sensible defaults, requiring minimal setup.
      5. **Privacy Focused:** Only shares necessary threat information without compromising your or your users' privacy.

### How to Use

Follow these steps to configure and use the BunkerNet feature:

1. **Enable the feature:** The BunkerNet feature is enabled by default. If needed, you can control this with the `USE_BUNKERNET` setting.
2. **Initial registration:** Upon first startup, your instance will automatically register with the BunkerNet API and receive a unique identifier.
3. **Automatic updates:** Your instance will automatically download the latest threat database on a regular schedule.
4. **Automatic reporting:** When your instance blocks a malicious IP, it will automatically contribute this data to the community.
5. **Monitor protection:** Check the [web UI](web-ui.md) to see statistics on threats blocked by BunkerNet intelligence.

### Configuration Settings

| Setting            | Default                    | Context   | Multiple | Description                                                                                    |
| ------------------ | -------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------- |
| `USE_BUNKERNET`    | `yes`                      | multisite | no       | **Enable BunkerNet:** Set to `yes` to enable the BunkerNet threat intelligence sharing.        |
| `BUNKERNET_SERVER` | `https://api.bunkerweb.io` | global    | no       | **BunkerNet Server:** The address of the BunkerNet API server for sharing threat intelligence. |

!!! tip "Network Protection"
    When BunkerNet detects that an IP address has been involved in malicious activity across multiple BunkerWeb instances, it adds that IP to a collective blacklist. This provides a proactive defense layer, protecting your site from threats before they can target you directly.

!!! info "Anonymous Reporting"
    When reporting threat information to BunkerNet, your instance only shares the necessary data to identify the threat: the IP address, the reason for blocking, and minimal contextual data. No personal information about your users or sensitive details about your site are shared.

### Example Configurations

=== "Default Configuration (Recommended)"

    The default configuration enables BunkerNet with the official BunkerWeb API server:

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://api.bunkerweb.io"
    ```

=== "Disabled Configuration"

    If you prefer not to participate in the BunkerNet threat intelligence network:

    ```yaml
    USE_BUNKERNET: "no"
    ```

=== "Custom Server Configuration"

    For organizations running their own BunkerNet server (uncommon):

    ```yaml
    USE_BUNKERNET: "yes"
    BUNKERNET_SERVER: "https://bunkernet.example.com"
    ```
