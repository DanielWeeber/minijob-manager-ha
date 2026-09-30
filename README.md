# Minijob-Manager für Home Assistant

Inoffizielle Integration für das Arbeitgeberportal [minijob-manager.de](https://www.minijob-manager.de/) der Minijob-Zentrale. Es gibt keine öffentliche API; die Integration nutzt dieselben Endpunkte wie die Portal-Webseite. Nicht mit der Minijob-Zentrale/Knappschaft-Bahn-See verbunden – Nutzung auf eigene Verantwortung.

## Installation (HACS)
1. HACS → Drei-Punkte-Menü → **Benutzerdefinierte Repositories** → `https://github.com/DanielWeeber/minijob-manager-ha`, Kategorie **Integration**.
2. Installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → *Minijob-Manager*.
4. E-Mail und Passwort eingeben, dann den 6-stelligen Code aus der E-Mail der Minijob-Zentrale.

## Anmeldung
Das Portal verlangt bei jedem Login einen E-Mail-Code. Der Code wird nur einmal bei der Einrichtung benötigt; danach hält die Integration die Sitzung per Refresh-Token am Leben (Abfrage alle 10 Minuten, Sitzung läuft nach 30 Minuten Inaktivität ab). Ist HA länger offline, verlangt die Integration per Reauth-Dialog erneut Passwort und Code. Das Passwort wird nicht gespeichert, nur die Tokens.

## Entitäten
Konto: Kontosaldo, Anzahl Beschäftigte, ungelesene Nachrichten, Portalmeldungen, nächste Fälligkeit und nächster Beitrag, SEPA-Mandat.
Je Beschäftigte/r: Monatsentgelt, Jahresentgelt (aus den gemeldeten Entgelten) und verbleibender Betrag bis zur Jahresgrenze (12 × 603 € für 2026).

Stunden liefert das Portal nicht. Das Jahresentgelt ist eine Schätzung auf Monatsbasis.

## Nicht enthalten
Meldungen (An-/Abmeldung) auslösen: laufen im Portal über einen mehrstufigen Wizard und sind bewusst noch nicht umgesetzt.

## Entwicklung
```
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest
.venv/bin/python scripts/login_test.py   # Live-Test, fragt Passwort und Code ab
```
