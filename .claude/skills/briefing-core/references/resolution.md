# Agenten, Deklarationen und Skill-Auflösung

Maßgeblich: `hooks/briefing-preload`; Verhalten mit `tests/test_briefing.py`,
`tests/test_briefing_codex.py` und `tests/test_briefing_doctor.py` absichern.
Jeder Harness bekommt seine eigenen Suchorte, nicht eine gemeinsame globale Liste.

## Claude Code

Agenten: `.claude/agents/` im `cwd`, danach im Benutzer-Home, rekursiv nach `.md`.
Identität ist das Frontmatter-`name`; der Dateiname ist Fallback und schneller Suchpfad,
kein Ersatz für ein abweichendes `name`. Deklaration unter `briefing.skills`,
als YAML-Block oder Flow-Liste. Ein top-level `skills:` gehört dem Harness.

Bare Skills: `<cwd>/.claude/skills` → `~/.claude/skills` → installierte Plugins.
`plugin:skill` geht direkt zur Plugin-Auflösung.

- Installationsindex: `~/.claude/plugins/installed_plugins.json`, nicht Cache-Globs.
  Alte Versionen und Commit-Hashes bleiben im Cache; Sortierung findet nicht den Live-Stand.
- `installPath` ist die Plugin-Wurzel. Projekt-/Local-Einträge gelten nur innerhalb
  ihres `projectPath` und haben vor Benutzerinstallationen Vorrang.
- `enabledPlugins` wird pro Schlüssel aus Benutzer-, Projekt- und
  `.claude/settings.local.json` zusammengeführt, spätere Ebene gewinnt.
  Nur `true` aktiviert ein Marketplace-Plugin; fehlend und `false` deaktivieren es.
- `--settings` und Managed Settings sind dem Hook nicht zugänglich. Ein nur dort
  gesetzter Zustand ist keine auflösbare Konfiguration für diesen Hook.
- Skills: `skills/<name>/` sowie Manifest-`skills`-Pfade. Jeder zusätzliche Pfad
  bezeichnet einen Skill oder ein Verzeichnis unmittelbar enthaltener Skills.
  Tiefere, nicht deklarierte Strukturen sind keine impliziten Skills.
- Namespace ist der Manifestname, nicht zwingend der Verzeichnisname.
  Zusätzliche `skills` aus Marketplace-Einträgen liest dieser Checkout noch nicht.

## Codex-Deklaration

```toml
name = "my_agent"
description = "..."
# briefing: skills = ["skill-a", "plugin:skill-b"]
developer_instructions = """
Die Aufgabe dieses Agenten.
"""
```

Die Kommentarzeile steht außerhalb mehrzeiliger Strings. `parse_skills_comment`
verfolgt deren Zustand, damit Beispieltext keine Deklaration wird.
Codex 0.153 verwirft Agenten mit unbekannten TOML-Feldern (`deny_unknown_fields`),
auch `[briefing]`; das ist kein freier Metadaten-Namespace. Eine Sidecar-`.toml`
unter `agents/` wäre selbst eine Agentendefinition.

Die Legacy-Tabelle bleibt für ältere Harnesses lesbar, mit Migrationswarnung.
Der Kommentar hat Vorrang; eine vorhandene Legacy-Deklaration wird weiter diagnostiziert.
`parse_skills_toml` importiert `tomllib` lokal (Python 3.11+), sonst nutzt es den
engen Regex-Fallback für diese Tabelle und diesen Schlüssel.

`[[skills.config]]` bedeutet Sichtbarkeit für den Agenten, nicht Vorladen.
Diese unabhängige Entscheidung bleibt unberührt.

## Codex-Agenten finden

Konfigurationsebenen: jede `.codex/` von `cwd` zur nächsten `.git`-Projektwurzel,
danach `$CODEX_HOME` (Standard `~/.codex`), danach `/etc/codex`.
Ohne gefundene Projektwurzel wird nur `cwd` als Projektebene verwendet.

Pro Ebene hat `[agents.<name>] config_file` in `config.toml` Vorrang; relative
Pfade beziehen sich auf die Konfigurationsdatei. Zusätzlich werden alle `*.toml`
unter `agents/` rekursiv nach ihrem `name` durchsucht.
`<name>.toml` ist nur schneller Suchpfad und wird bei abweichendem `name` übersprungen.
Die nächstgelegene Ebene gewinnt. Upstream-Referenz:
`codex-rs/agent-roles/src/{loader,discovery}.rs`.

## Codex-Skills finden

Pro Projektverzeichnis von `cwd` bis zur nächsten `.git`, nächstgelegen zuerst:
`.codex/skills` → `.agents/skills`. Danach:

1. `$CODEX_HOME/skills`
2. `~/.agents/skills`
3. `$CODEX_HOME/skills/.system`
4. `/etc/codex/skills`

`plugin:skill` ist auch in Codex gültig; verifiziert mit `briefing:briefing` in
`codex debug prompt-input`. Der typische Plugin-Pfad ist
`$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/`.
Der Codex-Resolver dieses Checkouts nutzt Cache-Globs; die indexbasierte
Claude-Code-Auflösung nicht ungeprüft als bereits implementiert dokumentieren.
