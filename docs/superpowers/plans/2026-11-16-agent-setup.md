# Agent Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Die Einrichtung erfolgt direkt in dieser Sitzung; weder Produktcode noch Commit sind Teil des Auftrags.

**Goal:** Ein geprüftes Getty-Projektteam mit skilletor und kompakten Projektanweisungen einrichten.
**Architecture:** skilletor verwaltet gemeinsame Regeln und Skills; projektspezifische Agenten und `briefing-core` bleiben eigene Quellen. CLAUDE.md verweist auf das benötigte Wissen.
**Tech Stack:** Markdown/YAML, JSON, skilletor, briefing, Python unittest.
**Spec:** `docs/superpowers/specs/2026-11-16-agent-setup-design.md`

## Global Constraints

- Python 3.8+ für gemeinsame und Claude-Code-Pfade, ausschließlich Standardbibliothek.
- Keine Hook-, Produkt-Skill-, Binärdatei- oder Manifeständerung. Kein Commit oder Push.
- Fünf Rollen: scout, worker, test-writer, reviewer, release-manager.
- Bestehendes Karr-Board unverändert; k5 bleibt die eigenständige Binary-Aufgabe.

## Review Focus

- Frischer Checkout: Quellen und Plugin-Voraussetzungen sind versionierbar, installierte Kopien ignoriert.
- Fehlender Skill: ein vollständiges Briefing oder eine explizite Verweigerung, nie Teilkontext.
- Verlagerte Dokumentation: bisherige Schutzregeln und Live-Test-Fallen bleiben erreichbar.
- Zuständigkeiten: Git-/Release-Wissen ausschließlich im Release-Manager, lesende Rollen ohne Schreibwerkzeuge.
- Falscher Erfolg: getesteten Checkout, installierte Plugin-Version und echte Harness-Starts unterscheiden.

## Task 1: Einrichtung und Dokumentationsmigration

**Files:** `.claude/skilletor.json`, `.claude/settings.json`, `.claude/.gitignore`,
`.worktreeinclude`, `.claude/skills/briefing-core/SKILL.md` mit `references/`,
`.claude/agents/briefing-*.md`, `.claude/rules/briefing-rules.md`, `CLAUDE.md`, `.gitignore`.
**Interfaces:** Agenten deklarieren `briefing-core`, Rollen-Skills und Karr-Ticket-Skill;
Settings aktivieren briefing, skilletor und superpowers.

- [x] Ausgangszustand prüfen: ack-team meldet fehlende Agenten, Regeln und Settings; 95 unittest-Tests bestehen.
- [x] Bestehendes Ticket lesen: k5 behandelt Binaries, nicht die Einrichtung.
- [x] Quellen und Hausregeln mit skilletor installieren; vorhandene lokale Quellen nutzen.
- [x] Projektwissen in `briefing-core` und Referenzen verlagern, fünf Agenten und kurze Regeln schreiben.
- [x] CLAUDE.md auf Einstieg und eindeutige Verweise kürzen; lokale Dateien und Karr-Materialisierung korrekt ignorieren.
- [x] `skilletor check --scope project`, `ack-team check` und beide Doctor-Versionen ohne fehlende Skills.
- [x] Positiven Hook-Output pro Rolle und negativen Probe-Agenten prüfen.
- [x] Markdown-Verweise, Git-Sichtbarkeit und `git diff --check` prüfen.
- [x] `python3 -m unittest discover tests` ausführen; erwartet: 95 bestandene Tests.
- [x] Ergebnis prüfen und nicht ausgeführte Live-/Plattformprüfungen nennen; keine Veröffentlichung.

## Ausführungsnotizen

- Entscheidung: direkt im bestehenden Checkout arbeiten, wie für die Teameinrichtung genehmigt; keine Produktcode-Änderung und kein Commit.
- Entscheidung: Konfigurationsmigration mit vorhandenen Prüfwerkzeugen statt neuer Produkt-Tests; die rote Ausgangslage ist der fehlgeschlagene Team-Check.
- Entscheidung: `targets: [claude]` bildet das vorhandene Entwicklungssetup ab; kein zweites Codex-Team ohne Auftrag.
- Entscheidung: `skilletor check` darf bei den lokalen Quellen `changed` melden. Der installierte `LocalSource.check()` liefert absichtlich immer `true`; bestanden sind ein unverändernder Sync und acht installierte Einträge ohne Orphans, Warnungen oder Trust-Anfragen. Kein Eingriff in die Benutzerkonfiguration, um einen künstlich grünen Exit zu erzwingen.
- Korrigierte Prüfannahmen: `bin/briefing-doctor` ist ein Shell-Wrapper (`sh -n`), kein Python-Skript. Der erste Compile-Versuch darauf schlug entsprechend fehl. Der installierte Hook injiziert erst bei `SubagentStart`, der Checkout noch über `PreToolUse.updatedInput`; ein gemeinsamer Positivtest mit dem alten Event war deshalb ungeeignet. Beide Verträge wurden anschließend getrennt erfolgreich geprüft.

## Verifiziert

- `ack-team check`: alle fünf Agenten, Rollen, Lesebeschränkungen, Settings, Board und Hook `ok`.
- Checkout-Doctor und installierter `briefing-doctor`: alle fünf Rollen auflösbar; maximal 28 KiB Briefing.
- Je Hook-Version fünf positive Payload-Tests; fehlender Skill wird verweigert, kein Teil-Briefing. Installierter SubagentStart liefert bei fehlendem Skill ausschließlich Abbruchkontext.
- Relative Markdown-Verweise erreichbar; eigene Quellen nicht ignoriert, installierte und lokale Dateien ignoriert; Karr-Ignore nur im Root.
- Python-Syntaxprüfung der beiden Hooks und `sh -n bin/briefing-doctor` bestanden.
- `python3 -m unittest discover tests`: 95 Tests bestanden, keine übersprungen.
- `git diff --check` bestanden; keine Produktdateien verändert, kein Commit, Push oder Board-Schreibzugriff.

## Offen beziehungsweise nicht ausgeführt

- Der erste Reviewer-Start war noch mit „Agent type not found“ abgelehnt worden. Nach Freigabe des lokalen Commits durch den Nutzer war `briefing-reviewer` verfügbar: unabhängiges Review ohne Befunde, 95/95 Tests, beide Doctors, alle fünf Rollen über beide Hook-Kanäle und ack-team bestanden. Keine Datei- oder Board-Mutationen durch den Reviewer. Der reale Verhaltenstest mit Kontrollagent steht weiterhin aus.
- Echte Claude-Code-/Codex-Spawns mit Positiv-/Kontrollphrase und native Windows-/macOS-Läufe nicht ausgeführt. Erfolgreiche Payload-Tests sind kein Ersatz für diese Integrationsnachweise.
