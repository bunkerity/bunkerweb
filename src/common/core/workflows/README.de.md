Das Workflows-Plugin ergänzt eine Richtlinienebene zwischen einzelnen Einstellungen und Lua-Schutzfunktionen:
wiederverwendbare, geordnete Regeln, die Sie Diensten zuweisen. Jede verbindet einen Bedingungsbaum
mit genau einer Aktion.

Eine Regel beantwortet Fragen, die einzelne Einstellungen allein nicht ausdrücken können:

> **Wenn** eine Anfrage aus Frankreich kommt **und** `/login` aufruft **und** 10 Anfragen pro Minute
> überschreitet, **dann** eine hCaptcha-Challenge anzeigen.

Workflows **koordinieren** bestehende Schutzfunktionen. `challenge` übergibt die Anfrage an Antibot;
ein Ratenschwellwert verwendet denselben Zählmechanismus wie Limit. Bestehende Einstellungen bleiben wirksam.

### Auswertung einer Regel

Für jeden Dienst werden Workflows in Zuordnungsreihenfolge ausgewertet, ihre Regeln in der von Ihnen
festgelegten Reihenfolge. **Die erste tatsächlich zutreffende Regel gewinnt**, führt ihre einzelne
Aktion aus und beendet die Auswertung.

Bedingungen bilden einen Baum aus `ALL` / `ANY` / `NOT` über:

| Bedingung | Prüft |
| --------- | ----- |
| IP / CIDR | Effektive Client-IP nach Real-IP-Auflösung |
| Land | ISO-Land aus der GeoIP-Datenbank |
| ASN | Nummer des autonomen Systems der Client-IP |
| URI | Normalisierten Pfad: exakt, Präfix oder regulärer Ausdruck |
| HTTP-Methode | Methode der Anfrage |
| Ressourcengruppe | Anderswo gepflegte IP-, Länder- oder ASN-Gruppe, per ID referenziert |
| CrowdSec-Urteil | Entscheidung über die Anfrage: Quelle (`appsec` oder `lapi`) und verlangte Maßnahme (`ban` oder `captcha`) |

Bedingungen sind **dreiwertig**: wahr, falsch oder *unbekannt*, wenn benötigte Informationen fehlen,
etwa eine GeoIP-Datenbank. Eine Regel trifft nur bei einem insgesamt wahren Baum zu. Ein Datenbankfehler
lässt sie damit nicht mehr zutreffen, statt sie versehentlich passend zu machen.

Eine **CrowdSec-Urteil**-Bedingung ist unentschieden, wenn CrowdSec den Dienst nicht bewertet hat,
und falsch, wenn CrowdSec die Anfrage bewertet und nichts beanstandet hat. Das sind unterschiedliche
Fälle; keiner trifft zu. Damit ein Workflow *anstelle* von CrowdSec antwortet, setzen Sie
`CROWDSEC_DEFER_TO_WORKFLOWS=yes` auf dem Dienst. CrowdSec übergibt dann sein Urteil, statt es selbst
anzuwenden; trifft keine Regel zu, wird es unverändert durchgesetzt.

### Ratenschwellwerte entscheiden über den Treffer

Eine Regel kann einen Schwellwert tragen. Dieser ist keine Aktion „Rate begrenzen“, sondern entscheidet,
**ob die Regel überhaupt zutrifft**. Unterhalb des Schwellwerts wird die nächste Regel geprüft.

Damit lässt sich „über 10 Anfragen pro Minute mit 429 antworten, sonst eine Challenge anzeigen“
als zwei geordnete Regeln mit gleichen Bedingungen ausdrücken: zuerst mit Schwellwert und Blockierung,
danach ohne Schwellwert.

Der Zähler gilt je Dienst + Regel + Client-IP und beeinflusst die `LIMIT_REQ_*`-Zähler nicht.

### Aktionen

- **challenge** — einen bestimmten Antibot-Provider anzeigen (`captcha`, `hcaptcha`, `turnstile`, …).
  Dies funktioniert auch bei `USE_ANTIBOT=no` und übergeht Antibots Ignorierlisten. Gewünschte
  Ausnahmen gehören in die Regelbedingungen. Die Zugangsdaten des Providers müssen bereits im Dienst vorliegen.
- **block** — mit dem Ablehnungsstatus der Instanz antworten, beziehungsweise `429` bei einer Regel zur Ratenbegrenzung.
- **redirect** — den Client mit 301/302/303/307/308 an eine feste URL weiterleiten.

### Erkennungsmodus

`SECURITY_MODE=detect` verwendet dieselben Bäume, dieselbe Reihenfolge und dieselben Ratenzähler,
setzt jedoch nichts durch. Die Aktion, die erfolgt *wäre*, wird in den Berichten gespeichert,
sodass Sie eine Richtlinie vor der Aktivierung mit echtem Verkehr prüfen können.

### Fehlerverhalten

Hat eine Instanz noch keine kompilierte Richtlinie erhalten — beim ersten Start oder nach einem
fehlgeschlagenen Push —, protokolliert sie einen Fehler und bedient den Verkehr mit ihren üblichen
Schutzfunktionen. Eine auf der Control Plane nicht kompilierbare Richtlinie wird dagegen überhaupt
nicht verteilt: Der Push wird abgebrochen und alle Instanzen behalten ihre bisherige Richtlinie.
Das Löschen einer referenzierten Ressourcengruppe wird abgelehnt, solange die Regel existiert.

### Regex-Budget

| Einstellung | Standard | Kontext | Mehrfach | Beschreibung |
| ----------- | -------- | ------- | -------- | ------------ |
| `WORKFLOWS_REGEX_BUDGET` | `512` | global | nein | **Regex-Budget:** Maximale Anzahl verschiedener kompilierter regulärer Ausdrücke über alle Workflow-Regeln. NGINX teilt einen Regex-Cache zwischen allen Plugins. Regeln oberhalb dieses Budgets werden deaktiviert, statt unbemerkt die gesamte Instanz zu verlangsamen. |

Die Kompilierung verarbeitet Workflows nach ID sortiert und verbraucht das Budget schrittweise.
Wird es innerhalb eines Artefakts erschöpft, deaktiviert die Instanz die restlichen Regeln, nicht
sich selbst. Durch die feste Reihenfolge deaktivieren zwei Instanzen mit demselben Artefakt dieselben Regeln.

### Workflows verwalten

Die Verwaltung erfolgt auf der **Workflows**-Seite der Web-UI oder über die API-Endpunkte `/workflows`.
Regeln werden zentral gespeichert, in ein gemeinsames Artefakt kompiliert und mit dem üblichen
Konfigurations-Push an alle Instanzen verteilt.
