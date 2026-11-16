# Echte Harness-Integration prüfen

Subprozess-Tests beweisen „Payload → Ausgabe“, nicht „Harness ruft Hook auf und
übergibt den Kontext“. Ein Integrationstest muss so gebaut sein, dass er ohne
Briefing nicht versehentlich bestehen kann.

## Positivprobe und Kontrolle

1. Eine Testphrase ausschließlich in den Body eines Test-Skills schreiben.
   Weder Prompt noch Agentenbeschreibung nennen die Phrase oder verraten sie.
2. Den deklarierenden Agenten bitten, sie aus seinem bereits vorhandenen Kontext
   zu produzieren, ohne Dateien oder den Skill nachzuladen.
3. Denselben Agenten ohne `briefing.skills` beziehungsweise ohne
   `# briefing: skills = [...]` als Kontrolle starten. Erwartet: `UNKNOWN`.
4. Tool-Aufrufe und tatsächlichen Hook-Austausch mitprüfen. Ein Agent, der die
   Datei selbst liest, beweist keine Injektion. Ein „Ist Phrase X im Kontext?“
   im Prompt verrät die Antwort und ist kein Test.

Eine verlockende Skill-Beschreibung kann die Kontrolle zum Nachlesen bringen:
Name und Beschreibung sind auch ohne injizierten Body sichtbar.

## Codex: zwei getrennte Vertrauensentscheidungen

- Plugin-Hooks laufen erst nach erteiltem Hook-Vertrauen. Vorher werden sie
  still übersprungen. `codex exec` kann dieses Vertrauen nicht interaktiv erteilen;
  für einen ausdrücklich genehmigten Integrationstest gibt es
  `--dangerously-bypass-hook-trust`.
- Das Projekt muss separat vertraut sein, sonst lädt Codex keine Projektrollen
  und spawnt `default`. Vertrauen auf `$HOME` deckt ein darunter liegendes,
  separates Git-Repository nicht ab. Die Hook-Ausnahme löst das nicht.
- Pro Lauf funktioniert `-c 'projects={"<abs path>"={trust_level="trusted"}}'`.
  Die gepunktete Form `projects."<path>".trust_level=...` wurde im verifizierten
  Codex-Stand still ignoriert. Das protokollierte `agent_type` unterscheidet
  einen falschen Default-Agenten von einem fehlgeschlagenen Briefing.
- Immer das echte `CODEX_HOME` verwenden, andere Testeinstellungen über `-c`.
  **Niemals `auth.json` in ein zweites Home kopieren:** parallele Homes mit
  demselben Refresh-Token können den Login ungültig machen.

## Beobachtbarkeit und installierter Stand

`codex exec` verwirft Hook-`systemMessage` auch mit `--json`; die TUI zeigt sie
als Warnung. Fehlende sichtbare Ausgabe ist daher kein Beleg für einen fehlenden Hook.
Wenn Instrumentierung nötig ist, nach Freigabe die tatsächlich installierte
Cache-Kopie sichern und deren stdin/stdout protokollieren; danach wiederherstellen.
Eine Markierung allein im Repository beweist nichts über das installierte Plugin.
Keine Auth-Dateien, Umgebungs-Secrets oder unnötigen Projektinhalte protokollieren.

Claude Code kann den Checkout mit `claude -p --plugin-dir <checkout>` testen.
Eine parallel installierte briefing-Kopie für diesen Lauf mit
`--settings '{"enabledPlugins":{"briefing@getty":false}}'` deaktivieren,
damit der Test nicht zweimal beziehungsweise gegen die falsche Version läuft.
Neue Agentendateien verlangen eine neue Sitzung; Doctor-/Hook-Simulationen bleiben
auch ohne Neustart möglich. Einen solchen Check nicht als echten Spawn ausgeben.

## Historische Evidenz, keine aktuelle Prüfaussage

Die frühere CLAUDE.md hielt folgende erfolgreiche Läufe fest:

- Codex 0.153.4: abweichender Dateiname unter `agents/team/`, Spawn aus einem
  Repository-Unterverzeichnis und eine `config_file`-Rolle lieferten die Phrase;
  die Kontrolle lieferte `UNKNOWN`.
- briefing 0.4.0: Codex nannte das injizierte `<skill>`-Element; ein protokollierter
  SessionStart meldete die kaputte Deklaration. Claude Code fand einen Agenten
  nach `name` in einem Unterverzeichnis, lieferte die Phrase ohne Tool-Aufruf,
  die Kontrolle `UNKNOWN`; Audit und Pre-flight erschienen als Systemmeldungen.
- Der ursprüngliche Codex-Vergleich protokollierte `SubagentStart` in beiden
  Läufen; nur der deklarierende Agent kannte die Phrase.
- Ein gemeinsames `hooks.json` wurde mit Claude Code geprüft: der zusätzliche
  SubagentStart-Block war akzeptiert, absichtlich kaputtes JSON lieferte dagegen
  `Failed to load hooks`.

Diese Befunde begründen die Teststrategie. Aktuelle Plattform-/Harness-Ergebnisse
müssen erneut ausgeführt werden; nicht verfügbare Läufe ausdrücklich auslassen.
