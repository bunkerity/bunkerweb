Das Mutual-TLS-Plugin (mTLS) schützt sensible Anwendungen, indem nur Clients mit Zertifikaten akzeptiert werden, die von Ihren vertrauenswürdigen Zertifizierungsstellen ausgestellt wurden. Mit aktivem Plugin authentifiziert BunkerWeb jede Anfrage bereits an der Perimeter-Grenze und hält interne Tools sowie Partner-Integrationen abgeschirmt.

BunkerWeb bewertet jeden TLS-Handshake anhand des von Ihnen bereitgestellten CA-Bundles und Ihrer Richtlinien. Clients, die diese Vorgaben nicht erfüllen, werden abgeblockt, während konforme Verbindungen ihre Zertifikatsdetails an nachgelagerte Anwendungen weitergeben können.

**Funktionsweise:**

1. Das Plugin überwacht die HTTPS-Handshakes der ausgewählten Site.
2. Während des TLS-Austauschs prüft BunkerWeb das Client-Zertifikat und vergleicht die Kette mit Ihrem Vertrauensspeicher.
3. Der gewählte Verifizierungsmodus entscheidet, ob nicht authentifizierte Clients abgewiesen, durchgelassen oder zu Diagnosezwecken zugelassen werden. Siehe unten "Was jeder Modus schützt".
4. (Optional) BunkerWeb stellt die Ergebnisse über `X-SSL-Client-*`-Header bereit, damit Ihre Anwendungen eigene Autorisierungsregeln anwenden können.

!!! success "Wesentliche Vorteile"

      1. **Starker Perimeterschutz:** Nur authentifizierte Maschinen und Benutzer erreichen Ihre sensiblen Routen.
      2. **Flexible Vertrauensrichtlinien:** Kombinieren Sie strikte und optionale Modi passend zu Ihrem Onboarding.
      3. **Transparenz für Anwendungen:** Geben Sie Fingerabdrücke und Identitäten an Downstream-Services weiter.
      4. **Geschichtete Sicherheit:** Ergänzen Sie mTLS mit weiteren BunkerWeb-Plugins wie Rate Limiting oder IP-Filterung.

### Schritt-für-Schritt

Gehen Sie diese Schritte durch, um Mutual TLS kontrolliert einzuführen:

1. **Funktion aktivieren:** Setzen Sie `USE_MTLS` auf `yes` für die Site, die Zertifikatsauthentifizierung benötigt.
2. **CA-Bundle bereitstellen:** Verweisen Sie mit `MTLS_CA_CERTIFICATE` auf eine PEM-Datei, die für den Scheduler lesbar ist, oder übergeben Sie das Bundle direkt als base64/PEM-Daten mit `MTLS_CA_CERTIFICATE_DATA`. Der Scheduler validiert, cached und verteilt das Bundle an jede Instanz, sodass keine Einbindung pro Instanz nötig ist.
3. **Verifizierungsmodus wählen:** Nutzen Sie `on` für verpflichtende Zertifikate, `optional`, um Clients ohne Zertifikat durchzulassen (und ein Zertifikat nur auf den in `MTLS_URL` aufgeführten Pfaden zu verlangen), oder `optional_no_ca` kurzfristig zur Diagnose.
4. **Kettentiefe anpassen:** Erhöhen oder verringern Sie `MTLS_VERIFY_DEPTH`, falls Ihre PKI mehrere Zwischenstellen nutzt.
5. **Ergebnisse weiterreichen (optional):** Belassen Sie `MTLS_FORWARD_CLIENT_HEADERS` auf `yes`, wenn nachgelagerte Anwendungen Zertifikatsinformationen benötigen.
6. **Revokationslisten pflegen:** Setzen Sie `MTLS_CRL` (oder `MTLS_CRL_DATA`), sobald Sie eine CRL publizieren, damit BunkerWeb widerrufene Zertifikate ablehnt.
7. **Verhalten bei einfachem HTTP festlegen:** `MTLS_HTTP_POLICY` (standardmäßig `redirect`) bestimmt, was mit einfachen HTTP-Anfragen geschieht, die mTLS hätte schützen sollen.
8. **Festlegen, ob Zertifikatsfehler zu Sperren zählen (optional):** Mit `MTLS_COUNT_BAD_BEHAVIOR` (standardmäßig `no`) zählt Bad Behavior sie mit.

Der Scheduler prüft das vollständige neue CA-Bundle sowie jede CRL, bevor eine der Cache-Dateien ersetzt wird. Eine CRL wird abgelehnt, wenn sie nicht gelesen werden kann oder wenn ihr Aussteller Teil des Bundles ist und die Signatur nicht dagegen verifiziert; eine CRL, die von einer CA außerhalb des Bundles signiert wurde, wird mit einer Warnung veröffentlicht, da NGINX die Kette aus den vom Client gesendeten Zwischenzertifikaten aufbaut. Bei unlesbaren, ungültigen oder nicht zusammenpassenden Daten bleibt das bisherige CA/CRL-Paar erhalten und ein Fehler wird protokolliert. Erneuern Sie CA und CRL gemeinsam und korrigieren Sie ungültige Quellen zeitnah, insbesondere vor Ablauf einer CRL. Wenn sowohl `MTLS_CRL` als auch `MTLS_CRL_DATA` geleert werden, wird die Sperrlistenprüfung bewusst entfernt. Das Entfernen der CA-Konfiguration, das Deaktivieren von mTLS oder das Löschen des Dienstes entfernt dessen Cache-Dateien; solange `USE_MTLS` auf `yes` bleibt und der Modus nicht `optional_no_ca` ist, gilt `ssl_verify_client` dann gegen eine eingebaute Platzhalter-CA: mit `on` erhält jeder Client eine 400, mit `optional` jeder Client, der ein Zertifikat vorlegt, bis wieder eine CA konfiguriert ist. Tatsächliche Entfernungen lösen eine Neuladung aus.

Der Job `client-cert` läuft stündlich, sodass eine auf dem Datenträger ersetzte CA-Bundle- oder CRL-Datei innerhalb einer Stunde übernommen wird. Er protokolliert einen Fehler für eine abgelaufene CRL (jeder Client der CA, die sie signiert hat, wird abgewiesen, bis eine neue CRL veröffentlicht ist) und für ein abgelaufenes CA-Zertifikat. Er protokolliert eine Warnung für eine CRL, die innerhalb von 7 Tagen abläuft, für ein CA-Zertifikat, das innerhalb von 30 Tagen abläuft, für ein Zertifikat des Bundles, das keine CA ist, und, sobald mindestens eine CRL konfiguriert ist, für jede CA des Bundles ohne CRL. Die Warnung für eine fehlende CRL nennt jede CA ohne CRL: Jede CA, die ein Zertifikat der Kette ausstellt, auch die Root-CA, muss ihre CRL in der Menge haben, sonst werden Clients abgewiesen, deren Kette ein von ihr ausgestelltes Zertifikat enthält. Der Job veröffentlicht das Material in jedem dieser Fälle trotzdem: NGINX weist die betroffenen Clients ohnehin ab, und ältere Daten zu behalten wäre nicht besser.

### Was jeder Modus schützt

"Erreicht Ihr Backend" bedeutet: Die Anfrage wird an den Dienst weitergeleitet, nachdem auch die übrigen BunkerWeb-Plugins sie akzeptiert haben.

- **`on`:** Jede HTTPS-Anfrage braucht ein Zertifikat, das sich gegen das CA-Bundle validieren lässt. Eine Anfrage ohne Zertifikat oder mit ungültigem Zertifikat erhält von NGINX eine `400` und erreicht Ihr Backend nie. Einfaches HTTP folgt `MTLS_HTTP_POLICY`, auf jedem Pfad.
- **`optional` ohne `MTLS_URL`:** Erzwingt von sich aus nichts. Ein Client ohne Zertifikat erreicht Ihr Backend, über HTTPS und über einfaches HTTP. Ein Client, der ein ungültiges Zertifikat vorlegt, wird über HTTPS weiterhin abgewiesen (`400`). Nutzen Sie diesen Modus, wenn Ihre Anwendung die weitergeleiteten `X-SSL-Client-*`-Header liest und selbst entscheidet.
- **`optional` mit `MTLS_URL`:** Nur die Pfade, die zu einer Regel passen, brauchen ein gültiges Zertifikat. Über HTTPS erhält ein Client ohne Zertifikat auf diesen Pfaden eine `403`. Über einfaches HTTP folgen diese Pfade `MTLS_HTTP_POLICY`. Jeder andere Pfad erreicht Ihr Backend mit oder ohne Zertifikat, über HTTPS und über HTTP. Ein Client, der ein ungültiges Zertifikat vorlegt, wird auf jedem Pfad abgewiesen (`400`).
- **`optional_no_ca`:** Zur Diagnose, nicht zum Schutz. NGINX fordert ein Zertifikat an und toleriert die Fehler der Vertrauenskette (selbst signiertes Zertifikat, unbekannter Aussteller, nicht vertrauenswürdige Kette), sodass ein Client, für den keine CA bürgt, den Handshake trotzdem besteht. Jeder andere Prüffehler weist den Client über HTTPS weiterhin mit `400` ab, zum Beispiel ein abgelaufenes oder gesperrtes Zertifikat. Ohne `MTLS_URL` erzwingt der Modus nichts. Mit `MTLS_URL` brauchen die passenden Pfade weiterhin ein Zertifikat, das sich gegen ein CA-Bundle validieren lässt; ist kein CA-Bundle konfiguriert, kann nichts validiert werden, sodass diese Pfade jeden Client ablehnen.

Mit `SECURITY_MODE=detect` werden die Ablehnungen und Weiterleitungen, die BunkerWeb selbst ausspricht (Pfadregel, Richtlinie für einfaches HTTP, ungültige `MTLS_URL`-Regel), nur protokolliert und nicht durchgesetzt; die Anfrage geht an das nächste Plugin weiter. Die Prüfung auf Handshake-Ebene bei `on` und `optional` übernimmt NGINX, der Sicherheitsmodus beeinflusst sie nicht.

### Einfache HTTP-Anfragen

Ein Client-Zertifikat wird nur innerhalb von TLS übertragen, daher kann die Handshake-Prüfung einfaches HTTP nicht schützen. Für einen Dienst mit `USE_MTLS` auf `yes` legt `MTLS_HTTP_POLICY` fest, was mit einer einfachen HTTP-Anfrage geschieht, die mTLS hätte schützen sollen: jeder Pfad, wenn `MTLS_VERIFY_CLIENT` auf `on` steht, sonst die `MTLS_URL`-Pfade. Mit `optional` oder `optional_no_ca` ohne `MTLS_URL` schützt mTLS über HTTPS nichts, also auch über HTTP nichts.

- `redirect` (Standard): Der Client erhält eine `301` auf dieselbe URL über HTTPS. Eine Anfrage ohne brauchbaren `Host`-Header wird stattdessen abgelehnt. Sie behält den Port des `Host`-Headers bei, wie die Weiterleitung des SSL-Plugins: Wo sich HTTP- und HTTPS-Port unterscheiden und nicht das Standardpaar 80/443 sind, wird der Client über HTTPS auf die HTTP-Portnummer weitergeleitet. Verwenden Sie dort `MTLS_HTTP_POLICY=deny` oder leiten Sie vor BunkerWeb weiter.
- `deny`: Die Anfrage wird mit dem Ablehnungsstatus abgewiesen (`DENY_HTTP_STATUS`, standardmäßig `403`).
- `allow`: Einfaches HTTP wird wie zuvor ausgeliefert, wenn `MTLS_VERIFY_CLIENT` auf `on` steht. Die `MTLS_URL`-Pfade bleiben abgelehnt.

Eine HTTPS-Weiterleitung, die das SSL-Plugin bereits ausgibt (`REDIRECT_HTTP_TO_HTTPS`, oder `AUTO_REDIRECT_HTTP_TO_HTTPS`, wenn es HTTPS erkennt), hat Vorrang; die Richtlinie sieht daher nur die einfachen HTTP-Anfragen, die diese Weiterleitung durchlässt. ACME-HTTP-01-Challenges bleiben erreichbar: Ein einfaches HTTP-`GET` oder `HEAD` auf `/.well-known/acme-challenge/<token>` wird nicht angetastet, wenn ein Solver es besitzt, also der lokale Let's-Encrypt-Solver mit vorhandenem Token oder `LETS_ENCRYPT_PASSTHROUGH` bzw. `ACME_PASSTHROUGH` auf `yes`. Jeder andere Pfad unter `/.well-known/acme-challenge/` folgt der Richtlinie. Setzen Sie `LISTEN_HTTP` für den Dienst auf `no`, um den HTTP-Port ganz zu schließen.

### Konfigurationseinstellungen

| Einstellung                    | Standardwert | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------ | ------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_MTLS`                     | `no`         | multisite | nein     | **Mutual TLS verwenden:** Aktiviert die Client-Zertifikatsauthentifizierung für die aktuelle Site.                                                                                                                                                                                                                                                                                                                                                                        |
| `MTLS_CA_CERTIFICATE_PRIORITY` | `file`       | multisite | nein     | **Priorität des Client-CA-Bundles:** Quelle des Client-CA-Bundles: `file` (Pfad) oder `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                |
| `MTLS_CA_CERTIFICATE`          |              | multisite | nein     | **Client-CA-Bundle-Pfad:** Pfad zum vertrauenswürdigen Client-CA-Bundle (PEM), lesbar für den Scheduler. Erforderlich, wenn `MTLS_VERIFY_CLIENT` `on` oder `optional` ist.                                                                                                                                                                                                                                                                                                |
| `MTLS_CA_CERTIFICATE_DATA`     |              | multisite | nein     | **Client-CA-Bundle-Daten:** Vertrauenswürdiges Client-CA-Bundle direkt als base64 oder PEM (z. B. über die Web-UI).                                                                                                                                                                                                                                                                                                                                                       |
| `MTLS_VERIFY_CLIENT`           | `on`         | multisite | nein     | **Verifizierungsmodus:** `on` verlangt auf jeder HTTPS-Anfrage ein gültiges Zertifikat. `optional` fordert ein Zertifikat an, weist ein ungültiges ab und erzwingt nichts weiter, solange `MTLS_URL` nicht gesetzt ist. `optional_no_ca` fordert ein Zertifikat an, ohne es gegen eine CA zu validieren (nur zur Diagnose). Siehe "Was jeder Modus schützt".                                                                                                              |
| `MTLS_URL`                     |              | multisite | ja       | **mTLS-URL:** Regex auf die normalisierte Anfrage-URI, die nur auf passenden Pfaden ein gültiges Client-Zertifikat verlangt, über HTTPS und über einfaches HTTP. Erfordert `MTLS_VERIFY_CLIENT` auf `optional`. Unterscheidet Groß- und Kleinschreibung, auf ein Verzeichnis verankern. Leer lassen für keine Pfadregel: mit `optional` oder `optional_no_ca` wird dann nichts erzwungen, und ein Zertifikat für die gesamte Site verlangt `MTLS_VERIFY_CLIENT` auf `on`. |
| `MTLS_HTTP_POLICY`             | `redirect`   | multisite | nein     | **HTTP-Richtlinie:** Was mit einer einfachen HTTP-Anfrage geschieht, die mTLS hätte schützen sollen: per `redirect` auf HTTPS weiterleiten, per `deny` ablehnen oder per `allow` zulassen (nur im Modus für die ganze Site, die `MTLS_URL`-Pfade bleiben abgelehnt).                                                                                                                                                                                                      |
| `MTLS_COUNT_BAD_BEHAVIOR`      | `no`         | multisite | nein     | **mTLS-Fehler in Bad Behavior zählen:** Bad Behavior zählt die `400`, die NGINX bei fehlendem oder ungültigem Client-Zertifikat antwortet, und die Ablehnungen, die mTLS selbst ausspricht. Bei `no` wird ein Client ohne gültiges Zertifikat dafür allein nicht gesperrt.                                                                                                                                                                                                |
| `MTLS_VERIFY_DEPTH`            | `2`          | multisite | nein     | **Verifizierungstiefe:** Maximale akzeptierte Zertifikatskettentiefe für Client-Zertifikate.                                                                                                                                                                                                                                                                                                                                                                              |
| `MTLS_FORWARD_CLIENT_HEADERS`  | `yes`        | multisite | nein     | **Client-Header weiterleiten:** Gibt Verifizierungsergebnisse (`X-SSL-Client-*`-Header mit Status, DN, Aussteller, Seriennummer, Fingerabdruck, Gültigkeit) weiter. Vom Client gesendete `X-SSL-*`-Header werden beim Eingang stets entfernt, sodass diese Werte nicht gefälscht werden können.                                                                                                                                                                           |
| `MTLS_CRL_PRIORITY`            | `file`       | multisite | nein     | **Priorität der Client-CRL:** Quelle der CRL: `file` (Pfad) oder `data` (base64/PEM).                                                                                                                                                                                                                                                                                                                                                                                     |
| `MTLS_CRL`                     |              | multisite | nein     | **Client-CRL-Pfad:** Optionaler Pfad zu einer PEM-codierten Sperrliste, lesbar für den Scheduler. Wird nur angewendet, wenn das CA-Bundle erfolgreich geladen wurde. NGINX braucht eine CRL von jeder CA, die ein Zertifikat der Kette ausstellt, einschließlich der Root-CA. Eine abgelaufene CRL weist die Clients ihrer CA ab.                                                                                                                                         |
| `MTLS_CRL_DATA`                |              | multisite | nein     | **Client-CRL-Daten:** Sperrliste direkt als base64 oder PEM.                                                                                                                                                                                                                                                                                                                                                                                                              |

!!! info "Eine neue CRL oder eine geänderte Client-CA verwirft die zwischengespeicherten TLS-Sitzungen"
    Eine Änderung der CRL oder des Client-CA-Bundles verwirft einmalig alle zwischengespeicherten TLS-Sitzungen der Instanz, weil der Sitzungscache nach einem Hash der veröffentlichten CA-Bundles und CRLs benannt ist. Ein widerrufenes Zertifikat kann keine frühere Sitzung wieder aufnehmen, und alle anderen Clients führen einmal einen vollständigen Handshake durch.

!!! tip "Schreiben Sie `MTLS_URL`-Regeln mit Sorgfalt"
    - Der Abgleich unterscheidet Groß- und Kleinschreibung: `^/admin` trifft `/Admin` nicht. Beginnen Sie das Muster mit `(?i)`, um die Schreibweise zu ignorieren.
    - Die Regex läuft auf der URI, wie NGINX sie normalisiert (dekodiert, Punktsegmente aufgelöst, doppelte Schrägstriche zusammengeführt), ohne Query-String; `/a/../admin` und `//admin` sind daher schon abgedeckt.
    - Verankern Sie auf ein Verzeichnis, nicht auf einen Dateinamen. Schreiben Sie `^/admin(/|$)` statt `^/admin$`, das `/admin/` nicht trifft. Eine auf einen Dateinamen verankerte Regel wie `^/admin/index\.html$` deckt `/admin/` ebenfalls nicht ab: NGINX liefert es per internem Redirect aus dieser Datei aus.
    - Pfadparameter wie `/admin;x=1` und jede weitere Normalisierung, die Ihr Backend zusätzlich zu der von NGINX vornimmt (zum Beispiel `..;/` oder Backslashes), müssen Sie selbst in der Regex abdecken. BunkerWeb gleicht die URI ab, die NGINX sieht.
    - Eine ungültige Regex schlägt geschlossen fehl: Jede Anfrage, auf die keine frühere Regel gepasst hat, wird abgelehnt (`403`), bis Sie sie korrigieren. BunkerWeb protokolliert beim Start und nach jedem Reload einen Fehler, der den Dienst und das Muster nennt.

!!! tip "Einmal konfigurieren, überall verteilt"
    CA-Bundles und Sperrlisten müssen nicht in die BunkerWeb-Container eingehängt werden. Stellen Sie sie nur dem Scheduler bereit, als Dateipfad oder als Inline-Daten; der Scheduler validiert sie, cached sie und verteilt sie an jede Instanz. Aktualisierungen werden beim nächsten Job-Lauf automatisch übernommen und neu verteilt.

!!! warning "CA-Bundle für strenge Modi obligatorisch"
    Sobald `MTLS_VERIFY_CLIENT` auf `on` oder `optional` steht, muss der Scheduler ein Client-CA-Bundle validieren und cachen können. Solange keines validiert und verteilt wurde, greift jede Instanz auf eine Platzhalter-CA zurück, zu der kein Client eine Vertrauenskette bilden kann. Bei `on` wird damit jeder Client abgewiesen, wo der Dienst zuvor ganz ohne Client-Prüfung lief. Bei `optional` wird ein Client ohne Zertifikat weiterhin durchgelassen, denn genau das bedeutet dieser Modus; die Durchsetzung für solche Anfragen kommt aus `MTLS_URL`, sofern es gesetzt ist, und bleibt ganz aus, wenn es leer ist. Ein Client, der ein Zertifikat vorlegt, wird abgewiesen, weil sich gegen die Platzhalter-CA keine Vertrauenskette bilden lässt. Verwenden Sie `optional_no_ca` nur zur Fehlersuche, denn dieser Modus schwächt die Client-Authentifizierung. Nach einem Neustart des Schedulers mit einem nicht persistenten `/var/cache/bunkerweb` bleibt dieser Zustand bestehen, bis der erste Job-Lauf abgeschlossen ist und das CA-Bundle neu verteilt hat; verwenden Sie deshalb ein persistentes Cache-Volume, wenn eine strikte Durchsetzung erforderlich ist.

!!! warning "mTLS läuft vor der Whitelist"
    mTLS wird direkt nach dem SSL-Plugin und vor der Whitelist ausgewertet. Ein Client, der auf `WHITELIST_IP`, `WHITELIST_URI`, `WHITELIST_USER_AGENT` (oder einen Standardeintrag von `WHITELIST_RDNS` oder `WHITELIST_ASN`) passt, braucht dort ein Zertifikat, wo mTLS eines verlangt. Vor 1.6.19 übersprang die Whitelist die `MTLS_URL`-Prüfung. Um diese Rangfolge wiederherzustellen, setzen Sie `PLUGINS_ORDER_ACCESS` auf `ssl whitelist mtls`. Wenn Sie `PLUGINS_ORDER_ACCESS` selbst setzen, global oder pro Service, bleibt Ihr Wert erhalten: Nennt er `mtls` nicht, läuft mTLS dort weiterhin nach der Whitelist. Setzen Sie `mtls` in diesem Wert direkt hinter `ssl`.

!!! info "Bad Behavior zählt Zertifikatsfehler standardmäßig nicht"
    Mit `MTLS_COUNT_BAD_BEHAVIOR` auf `no` zählt das Plugin Bad Behavior die `400`, die NGINX bei fehlendem oder ungültigem Client-Zertifikat antwortet, sowie die Ablehnungen, die mTLS selbst ausspricht (Pfadregel, Richtlinie für einfaches HTTP, ungültige `MTLS_URL`-Regex), nicht mit. Ein Client ohne gültiges Zertifikat wird dafür allein also nicht gesperrt. Jede andere `400` auf demselben Dienst zählt weiterhin. Setzen Sie die Einstellung auf `yes`, um sie wieder mitzuzählen. Die Antwort auf ein fehlendes oder ungültiges Zertifikat ist jetzt die `400`-Fehlerseite von BunkerWeb, wenn das Errors-Plugin `400` behandelt (Standard, sofern `ERRORS` keine eigene Seite für `400` setzt); andernfalls bleibt es die Standardseite von NGINX.

!!! info "Stream-Dienste"
    Auf einem Stream-Dienst gilt nur die Prüfung auf Handshake-Ebene, sodass nur `MTLS_VERIFY_CLIENT` auf `on` etwas erzwingt. `optional` und `optional_no_ca` lassen einen Client ohne Zertifikat durch, und `MTLS_URL` sowie `MTLS_HTTP_POLICY` gelten nur für HTTP.

!!! info "`X-SSL-Client-*`-Header erreichen nur Reverse-Proxy- und gRPC-Upstreams"
    BunkerWeb leitet die Verifizierungsergebnisse an Dienste weiter, die mit den Plugins Reverse Proxy oder gRPC konfiguriert sind. PHP/FastCGI und eigene Locations erhalten sie nicht: Reichen Sie die NGINX-Variablen `$ssl_client_*` in Ihrer Konfiguration selbst weiter.

!!! info "Vertrauensquelle und Verifizierung"
    BunkerWeb nutzt dasselbe CA-Bundle sowohl für die Client-Prüfung als auch für den Aufbau der Vertrauenskette, damit OCSP/CRL-Checks konsistent bleiben.

!!! info "Eingehende `X-SSL-*`-Header werden stets entfernt"
    BunkerWeb entfernt jeden vom Client gesendeten `X-SSL-*`-Request-Header, bevor die Anfrage Ihre Anwendung erreicht, auf jeder Site, unabhängig davon, ob mTLS aktiviert ist, und gleichermaßen unter HTTP/1.1, HTTP/2 und HTTP/3. Weitergegeben werden nur die Werte, die BunkerWeb aus dem verifizierten TLS-Handshake ableitet, und auch nur dann, wenn `MTLS_FORWARD_CLIENT_HEADERS` auf `yes` steht. Ein Client kann `X-SSL-Client-Verify: SUCCESS` somit nicht fälschen.

    Steht BunkerWeb hinter einem weiteren Proxy, der mTLS terminiert und diese Header selbst setzt, müssen Sie den Wert vor dem Entfernen sichern und erneut veröffentlichen. Legen Sie dazu eine eigene `server-http`-Konfiguration an:

    ```nginx
    set $trusted_ssl_verify $http_x_ssl_client_verify;
    ```

    und geben Sie ihn anschließend mit `REVERSE_PROXY_HEADERS: "X-SSL-Client-Verify $trusted_ssl_verify"` weiter. `REVERSE_PROXY_HEADERS` allein genügt nicht: `$http_x_ssl_client_verify` ist bereits leer, wenn `proxy_set_header` ausgewertet wird, während `set` in der Server-Rewrite-Phase und damit vor dem Entfernen läuft.

!!! warning "Pfadbezogenes mTLS erfordert den optionalen Modus"
    Die NGINX-Direktive `ssl_verify_client` ist nur im `server`-Kontext gültig: Sie kann nicht in einem `location`-Block stehen. Um ein Zertifikat nur auf bestimmten Pfaden zu verlangen, setzen Sie `MTLS_VERIFY_CLIENT` auf `optional`, damit der Handshake für jeden Pfad abgeschlossen wird, und listen Sie die geschützten Pfade in `MTLS_URL_n` auf. BunkerWeb erzwingt das Zertifikat dann pro Anfrage in Lua auf den passenden URLs. Verwenden Sie `optional` für echte Durchsetzung: `optional_no_ca` überspringt die CA-Prüfung beim Handshake, und die Pfadprüfung braucht trotzdem ein Zertifikat, das sich gegen ein CA-Bundle validieren lässt; ist kein CA-Bundle konfiguriert, lehnen die passenden Pfade jeden Client ab. Belassen Sie `MTLS_VERIFY_CLIENT` auf `on`, während Sie `MTLS_URL_n` setzen, weist NGINX Clients ohne Zertifikat bereits beim Handshake ab, bevor die pfadbezogene Logik greift, die Erzwingung bleibt dann site-weit (BunkerWeb protokolliert in diesem Fall beim Start eine Warnung).

!!! info "Browser-Zertifikatsabfragen im optionalen Modus"
    Der TLS-Handshake erfolgt, bevor NGINX die angeforderte URL kennt; im Modus `optional` sendet NGINX daher weiterhin bei jeder Verbindung einen `CertificateRequest`. Die Erzwingung wird pfadbezogen, die Einladung auf Handshake-Ebene jedoch nicht: Browser fragen unter Umständen auch auf ungeschützten Pfaden nach einem Zertifikat (Verhalten je nach Browser unterschiedlich). Auf diesen Pfaden lässt BunkerWeb die Anfrage zu, ob ein Zertifikat vorgelegt wird oder nicht.

### Konfigurationsbeispiele

=== "Strikte Zugriffskontrolle"

    Verlangen Sie gültige Client-Zertifikate Ihrer privaten CA und leiten Sie die Verifizierungsergebnisse an das Backend weiter:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/engineering-ca.pem"
    MTLS_VERIFY_CLIENT: "on"
    MTLS_VERIFY_DEPTH: "2"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Optionale Client-Authentifizierung"

    Erlauben Sie anonyme Nutzer, übermitteln Sie aber Zertifikatsdetails, sobald ein Client eines präsentiert. Das erzwingt von sich aus nichts: Ihre Anwendung entscheidet anhand der weitergeleiteten Header:

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

=== "Diagnose ohne CA"

    Lassen Sie Verbindungen auch dann zu, wenn ein Zertifikat nicht zu einem vertrauenswürdigen CA-Bundle verknüpft werden kann. Nur für Fehlersuche geeignet:

    ```yaml
    USE_MTLS: "yes"
    MTLS_VERIFY_CLIENT: "optional_no_ca"
    MTLS_FORWARD_CLIENT_HEADERS: "no"
    ```

=== "Pfadbezogenes mTLS (z. B. nur `/login`)"

    Verlangen Sie Client-Zertifikate nur auf ausgewählten Pfaden und lassen Sie den Rest der Site offen. Die Verifizierung läuft im Modus `optional`, damit der Handshake auf nicht authentifizierten Pfaden abgeschlossen wird; BunkerWeb erzwingt das Zertifikat anschließend pro Anfrage auf URLs, die zu `MTLS_URL_n` passen (eine Regex pro Eintrag):

    ```yaml
    USE_MTLS: "yes"
    MTLS_CA_CERTIFICATE: "/etc/bunkerweb/mtls/partner-ca.pem"
    MTLS_VERIFY_CLIENT: "optional"
    MTLS_URL_1: "^/login(/|$)"
    MTLS_URL_2: "^/admin(/|$)"
    MTLS_FORWARD_CLIENT_HEADERS: "yes"
    ```

    | Anfrage             | Zertifikat            | Ergebnis                                                     |
    | ------------------- | --------------------- | ------------------------------------------------------------ |
    | `GET /`             | keines                | Erlaubt (Pfad ohne mTLS)                                     |
    | `GET /login`        | keines                | Abgelehnt (`403`)                                            |
    | `GET /login`        | gültig                | Erlaubt, `X-SSL-Client-*` weitergeleitet                     |
    | beliebiger Pfad     | ungültig / abgelaufen | Von NGINX abgewiesen (`400`)                                 |
    | `GET /login` (HTTP) | keines                | Auf HTTPS weitergeleitet (`MTLS_HTTP_POLICY` ist `redirect`) |
