# Projektagenten und skilletor

## Ziel und Umfang

Den Entwicklungs-Checkout von briefing auf das aktuelle Getty-Preset bringen:
fünf Projektagenten, verwaltete gemeinsame Regeln und kurze Einstiegshinweise.
Die bestehende Hook-Implementierung und ihre öffentlichen Verträge bleiben unverändert.
Der Nutzer hat diesen Umfang am 2026-11-16 bestätigt.

## Gewählter Ansatz

Gemeinsame Regeln und Git-/Karr-Skills kommen über skilletor aus ihren Eigentümer-Repositories;
`briefing-core` und die Agenten bleiben versionierte, projektspezifische Quellen.
Eine weitere handgepflegte Kopie der Hausregeln würde wieder auseinanderlaufen.
Ein umfassender Umbau beider Harnesses wäre dagegen mehr als die beauftragte Einrichtung.
Das Entwicklungsteam richtet sich nach dem vorhandenen skilletor-Ziel `claude`;
die Produktunterstützung für Codex bleibt unverändert.

## Struktur

- `.claude/skilletor.json`: portable Quellen, `getty-house`, Git- und Karr-Skills.
- `.claude/settings.json`: benötigte Plugins und Marketplace, keine neuen Berechtigungen.
- `.claude/skills/briefing-core/`: kompakte Projektkonventionen mit ausgelagerten Referenzen.
- `.claude/agents/briefing-{scout,worker,test-writer,reviewer,release-manager}.md`:
  getrennte Zuständigkeiten, Wissen ausschließlich über `briefing.skills`.
- `.claude/rules/briefing-rules.md`: Zuständigkeiten und projektspezifische Prüfhinweise.
- `CLAUDE.md`: kurzer Einstieg mit bedingten Verweisen statt vollständigem Handbuch.

## Grenzen und Nachweise

Python 3.8+ für gemeinsame und Claude-Code-Pfade, ausschließlich Standardbibliothek.
Keine Hook-, Produkt-Skill-, Binärdatei- oder Manifeständerung. Kein Commit oder Push.
Das bestehende Karr-Board bleibt erhalten. k5 betrifft eigenständige Binaries ohne Python
und wird nicht als Einrichtungsticket umgewidmet oder abgeschlossen.
Prüfung mit skilletor check, ack-team check, briefing-doctor, negativem Hook-Test,
Link-/Git-Prüfung und der bestehenden unittest-Suite. Native Windows-Tests und echte
Harness-Spawns nur als bestanden melden, wenn sie tatsächlich ausgeführt wurden.
