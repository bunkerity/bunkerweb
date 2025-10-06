Das Bad Behavior-Plugin schützt Ihre Website, indem es IP-Adressen, die innerhalb eines bestimmten Zeitraums zu viele Fehler oder „schlechte“ HTTP-Statuscodes erzeugen, automatisch erkennt und sperrt. Dies hilft bei der Abwehr von Brute-Force-Angriffen, Web-Scrapern, Schwachstellen-Scannern und anderen böswilligen Aktivitäten, die zahlreiche Fehlerantworten erzeugen könnten.

Angreifer erzeugen oft „verdächtige“ HTTP-Statuscodes, wenn sie nach Schwachstellen suchen oder diese ausnutzen – Codes, die ein typischer Benutzer innerhalb eines bestimmten Zeitrahmens wahrscheinlich nicht auslösen würde. Durch die Erkennung dieses Verhaltens kann BunkerWeb die betreffende IP-Adresse automatisch sperren und den Angreifer zwingen, eine neue IP-Adresse zu verwenden, um seine Versuche fortzusetzen.

**So funktioniert es:**

1.  Das Plugin überwacht die HTTP-Antworten Ihrer Website.
2.  Wenn ein Besucher einen „schlechten“ HTTP-Statuscode (wie 400, 401, 403, 404 usw.) erhält, wird der Zähler für diese IP-Adresse erhöht.
3.  Wenn eine IP-Adresse den konfigurierten Schwellenwert für schlechte Statuscodes innerhalb des angegebenen Zeitraums überschreitet, wird die IP automatisch gesperrt.
4.  Gesperrte IPs können je nach Konfiguration entweder auf Dienstebene (nur für die spezifische Website) oder global (über alle Websites hinweg) blockiert werden.
5.  Sperren laufen automatisch nach der konfigurierten Sperrdauer ab oder bleiben dauerhaft, wenn sie mit `0` konfiguriert sind.

!!! success "Wichtige Vorteile"

      1. **Automatischer Schutz:** Erkennt und blockiert potenziell bösartige Clients ohne manuellen Eingriff.
      2. **Anpassbare Regeln:** Passen Sie genau an, was als „schlechtes Verhalten“ gilt, basierend auf Ihren spezifischen Anforderungen.
      3. **Ressourcenschonung:** Verhindert, dass böswillige Akteure Serverressourcen durch wiederholte ungültige Anfragen verbrauchen.
      4. **Flexibler Geltungsbereich:** Wählen Sie, ob Sperren nur für den aktuellen Dienst oder global für alle Dienste gelten sollen.
      5. **Kontrolle der Sperrdauer:** Legen Sie temporäre Sperren fest, die automatisch nach der konfigurierten Dauer ablaufen, oder permanente Sperren, die bis zur manuellen Aufhebung bestehen bleiben.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Bad Behavior-Funktion zu konfigurieren und zu verwenden:

1.  **Aktivieren Sie die Funktion:** Die Bad Behavior-Funktion ist standardmäßig aktiviert. Bei Bedarf können Sie dies mit der Einstellung `USE_BAD_BEHAVIOR` steuern.
2.  **Statuscodes konfigurieren:** Definieren Sie mit der Einstellung `BAD_BEHAVIOR_STATUS_CODES`, welche HTTP-Statuscodes als „schlecht“ gelten sollen.
3.  **Schwellenwerte festlegen:** Bestimmen Sie mit der Einstellung `BAD_BEHAVIOR_THRESHOLD`, wie viele „schlechte“ Antworten eine Sperre auslösen sollen.
4.  **Zeiträume konfigurieren:** Geben Sie die Dauer für die Zählung schlechter Antworten und die Sperrdauer mit den Einstellungen `BAD_BEHAVIOR_COUNT_TIME` und `BAD_BEHAVIOR_BAN_TIME` an.
5.  **Sperrbereich wählen:** Entscheiden Sie mit der Einstellung `BAD_BEHAVIOR_BAN_SCOPE`, ob die Sperren nur für den aktuellen Dienst oder global für alle Dienste gelten sollen.

!!! tip "Stream-Modus"
    Im **Stream-Modus** wird nur der Statuscode `444` als „schlecht“ angesehen und löst dieses Verhalten aus.

### Konfigurationseinstellungen

| Einstellung                 | Standard                      | Kontext   | Mehrfach | Beschreibung                                                                                                                                                                 |
| --------------------------- | ----------------------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_BAD_BEHAVIOR`          | `yes`                         | multisite | nein     | **Bad Behavior aktivieren:** Auf `yes` setzen, um die Funktion zur Erkennung und Sperrung von schlechtem Verhalten zu aktivieren.                                            |
| `BAD_BEHAVIOR_STATUS_CODES` | `400 401 403 404 405 429 444` | multisite | nein     | **Schlechte Statuscodes:** Liste der HTTP-Statuscodes, die als „schlechtes“ Verhalten gezählt werden, wenn sie an einen Client zurückgegeben werden.                         |
| `BAD_BEHAVIOR_THRESHOLD`    | `10`                          | multisite | nein     | **Schwellenwert:** Die Anzahl der „schlechten“ Statuscodes, die eine IP innerhalb des Zählzeitraums erzeugen kann, bevor sie gesperrt wird.                                  |
| `BAD_BEHAVIOR_COUNT_TIME`   | `60`                          | multisite | nein     | **Zählzeitraum:** Das Zeitfenster (in Sekunden), in dem schlechte Statuscodes auf den Schwellenwert angerechnet werden.                                                      |
| `BAD_BEHAVIOR_BAN_TIME`     | `86400`                       | multisite | nein     | **Sperrdauer:** Wie lange (in Sekunden) eine IP nach Überschreiten des Schwellenwerts gesperrt bleibt. Standard ist 24 Stunden (86400 Sekunden). `0` für permanente Sperren. |
| `BAD_BEHAVIOR_BAN_SCOPE`    | `service`                     | global    | nein     | **Sperrbereich:** Legt fest, ob Sperren nur für den aktuellen Dienst (`service`) oder für alle Dienste (`global`) gelten.                                                    |

!!! warning "Falsch-Positive"
    Seien Sie vorsichtig bei der Einstellung des Schwellenwerts und der Zählzeit. Zu niedrige Werte können versehentlich legitime Benutzer sperren, die beim Surfen auf Ihrer Website auf Fehler stoßen.

!!! tip "Anpassen Ihrer Konfiguration"
    Beginnen Sie mit konservativen Einstellungen (höherer Schwellenwert, kürzere Sperrzeit) und passen Sie diese je nach Ihren spezifischen Bedürfnissen und Verkehrsmustern an. Überwachen Sie Ihre Protokolle, um sicherzustellen, dass legitime Benutzer nicht fälschlicherweise gesperrt werden.

### Beispielkonfigurationen

=== "Standardkonfiguration"

    Die Standardkonfiguration bietet einen ausgewogenen Ansatz, der für die meisten Websites geeignet ist:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "86400"
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Strikte Konfiguration"

    Für Hochsicherheitsanwendungen, bei denen Sie potenzielle Bedrohungen aggressiver sperren möchten:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444 500 502 503"
    BAD_BEHAVIOR_THRESHOLD: "5"
    BAD_BEHAVIOR_COUNT_TIME: "120"
    BAD_BEHAVIOR_BAN_TIME: "604800"  # 7 Tage
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Sperre über alle Dienste hinweg
    ```

=== "Nachsichtige Konfiguration"

    Für Websites mit hohem legitimen Datenverkehr, bei denen Sie Falsch-Positive vermeiden möchten:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "401 403 429"  # Nur unautorisierte, verbotene und ratenlimitierte zählen
    BAD_BEHAVIOR_THRESHOLD: "20"
    BAD_BEHAVIOR_COUNT_TIME: "30"
    BAD_BEHAVIOR_BAN_TIME: "3600"  # 1 Stunde
    BAD_BEHAVIOR_BAN_SCOPE: "service"
    ```

=== "Konfiguration für permanente Sperren"

    Für Szenarien, in denen erkannte Angreifer dauerhaft gesperrt werden sollen, bis sie manuell entsperrt werden:

    ```yaml
    USE_BAD_BEHAVIOR: "yes"
    BAD_BEHAVIOR_STATUS_CODES: "400 401 403 404 405 429 444"
    BAD_BEHAVIOR_THRESHOLD: "10"
    BAD_BEHAVIOR_COUNT_TIME: "60"
    BAD_BEHAVIOR_BAN_TIME: "0"  # Permanente Sperre (läuft nie ab)
    BAD_BEHAVIOR_BAN_SCOPE: "global" # Sperre über alle Dienste hinweg
    ```
