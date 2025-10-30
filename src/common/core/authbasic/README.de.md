Das Auth Basic-Plugin bietet eine HTTP-Basisauthentifizierung zum Schutz Ihrer Website oder bestimmter Ressourcen. Diese Funktion fügt eine zusätzliche Sicherheitsebene hinzu, indem sie von den Benutzern die Eingabe eines Benutzernamens und eines Passworts verlangt, bevor sie auf geschützte Inhalte zugreifen können. Diese Art der Authentifizierung ist einfach zu implementieren und wird von den Browsern weitgehend unterstützt.

**So funktioniert es:**

1.  Wenn ein Benutzer versucht, auf einen geschützten Bereich Ihrer Website zuzugreifen, sendet der Server eine Authentifizierungsaufforderung.
2.  Der Browser zeigt ein Anmeldedialogfeld an, in dem der Benutzer zur Eingabe von Benutzername und Passwort aufgefordert wird.
3.  Der Benutzer gibt seine Anmeldedaten ein, die an den Server gesendet werden.
4.  Wenn die Anmeldeinformationen gültig sind, erhält der Benutzer Zugriff auf den angeforderten Inhalt.
5.  Wenn die Anmeldeinformationen ungültig sind, wird dem Benutzer eine Fehlermeldung mit dem Statuscode 401 Unauthorized angezeigt.

### Wie man es benutzt

Führen Sie die folgenden Schritte aus, um die Auth Basic-Authentifizierung zu aktivieren und zu konfigurieren:

1.  **Aktivieren Sie die Funktion:** Setzen Sie die Einstellung `USE_AUTH_BASIC` in Ihrer BunkerWeb-Konfiguration auf `yes`.
2.  **Wählen Sie den Schutzumfang:** Entscheiden Sie, ob Sie Ihre gesamte Website oder nur bestimmte URLs schützen möchten, indem Sie die Einstellung `AUTH_BASIC_LOCATION` konfigurieren.
3.  **Anmeldeinformationen definieren:** Richten Sie mindestens ein Paar aus Benutzername und Passwort mit den Einstellungen `AUTH_BASIC_USER` und `AUTH_BASIC_PASSWORD` ein.
4.  **Passen Sie die Nachricht an:** Ändern Sie optional den `AUTH_BASIC_TEXT`, um eine benutzerdefinierte Nachricht in der Anmeldeaufforderung anzuzeigen.

### Konfigurationseinstellungen

| Einstellung           | Standard          | Kontext   | Mehrfach | Beschreibung                                                                                                                                                     |
| --------------------- | ----------------- | --------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | nein     | **Auth Basic aktivieren:** Auf `yes` setzen, um die Basisauthentifizierung zu aktivieren.                                                                        |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | nein     | **Schutzumfang:** Auf `sitewide` setzen, um die gesamte Website zu schützen, oder einen URL-Pfad angeben (z.B. `/admin`), um nur bestimmte Bereiche zu schützen. |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | ja       | **Benutzername:** Der für die Authentifizierung erforderliche Benutzername. Sie können mehrere Paare aus Benutzername und Passwort definieren.                   |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | ja       | **Passwort:** Das für die Authentifizierung erforderliche Passwort. Jedes Passwort korrespondiert mit einem Benutzernamen.                                       |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | nein     | **Aufforderungstext:** Die Nachricht, die in der dem Benutzer angezeigten Authentifizierungsaufforderung erscheint.                                              |

!!! warning "Sicherheitshinweise"
    Die HTTP-Basisauthentifizierung überträgt Anmeldeinformationen, die in Base64 kodiert (nicht verschlüsselt) sind. Obwohl dies bei Verwendung über HTTPS akzeptabel ist, sollte es über reines HTTP nicht als sicher angesehen werden. Aktivieren Sie immer SSL/TLS, wenn Sie die Basisauthentifizierung verwenden.

!!! tip "Verwendung mehrerer Anmeldeinformationen"
    Sie können mehrere Paare aus Benutzername/Passwort für den Zugriff konfigurieren. Jede `AUTH_BASIC_USER`-Einstellung sollte eine entsprechende `AUTH_BASIC_PASSWORD`-Einstellung haben.

### Beispielkonfigurationen

=== "Schutz der gesamten Website"

    So schützen Sie Ihre gesamte Website mit einem einzigen Satz von Anmeldeinformationen:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Schutz bestimmter Bereiche"

    Um nur einen bestimmten Pfad zu schützen, wie z.B. ein Admin-Panel:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Mehrere Benutzer"

    So richten Sie mehrere Benutzer mit unterschiedlichen Anmeldeinformationen ein:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # Erster Benutzer
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Zweiter Benutzer
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Dritter Benutzer
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```
