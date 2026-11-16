# briefing

> Programmatic briefing beats prompt stuffing.

Plugin für Claude Code und Codex: deklarierte Skills gelangen beim Subagent-Start
vollständig in den Kontext. Nutzung und Installation: [README.md](README.md).

## Vor der Arbeit

- **Hooks, Auflösung, Doctor, Tests oder Windows-Launcher:**
  [briefing-core](.claude/skills/briefing-core/SKILL.md) lesen; die Referenzen dort
  trennen Hook-Vertrag, Suchregeln und echte Harness-Verifikation.
- **Zuständigkeiten und Prüfgrenzen:**
  [.claude/rules/briefing-rules.md](.claude/rules/briefing-rules.md).
- **Agenten für Plugin-Nutzer verfassen:**
  [Produkt-Skill](skills/briefing/SKILL.md); nicht mit dem Entwicklungs-Skill verwechseln.
- **Perl-Port oder Auslieferung planen:**
  [App::Briefing-Zielrichtung](docs/perl-direction.md) und die dort verlinkte Packaging-Probe lesen.

## Das Agententeam

- `briefing-scout`: liest und berichtet, verändert nichts.
- `briefing-worker`: implementiert und pflegt Code sowie Skills, committet nicht.
- `briefing-test-writer`: schreibt Tests, verändert nicht die Implementierung.
- `briefing-reviewer`: prüft Änderungen und führt Tests aus, verändert keine Dateien.
- `briefing-release-manager`: übernimmt genehmigte Commits, `Changes` und Release-Prüfungen.

Arbeit liegt im bestehenden Karr-Board (`karr list --compact`), nicht in einem
zweiten Dateiboard. Neue Agenten benötigen einen Neustart von Claude Code.

## Gemeinsame Regeln und Skills

`.claude/skilletor.json` deklariert die Quellen und das Bundle `getty-house`.
`skilletor sync --scope project` installiert die gemeinsamen Dateien;
`skilletor check --scope project` prüft den Stand. Verwaltete Kopien werden
an ihrer Quelle geändert. Dieses Entwicklungsteam nutzt das Ziel `claude`;
das Plugin selbst unterstützt weiterhin beide Harnesses.

Projektagenten, `briefing-core`, Settings und skilletor-Konfiguration bleiben
versioniert; installierte Regeln/Skills, Lock und lokale Settings nicht.
Hausregeln kommen aus skilletor und werden hier nicht noch einmal kopiert.
