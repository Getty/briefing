# Hook-Vertrag dieses Checkouts

Gilt für `hooks/briefing-preload`, nicht ungeprüft für installierte Plugin-Versionen.
`main()` routet `SubagentStart` nach Codex, `SessionStart` zum gemeinsamen Pre-flight
und ansonsten nur `tool_name == "Agent"` zu Claude Code.
Als `briefing-doctor` oder mit erstem Argument `doctor` läuft dieselbe Auflösung als CLI.
`bin/briefing-doctor` ist der ausführbare Wrapper dafür.

## Claude Code: PreToolUse

```json
{
  "cwd": "/abs/path", "tool_name": "Agent",
  "tool_input": { "subagent_type": "my-agent", "prompt": "...", "model": "sonnet" }
}
```

Erfolg: `hookSpecificOutput` mit `hookEventName: "PreToolUse"` und
`updatedInput`; der ursprüngliche Prompt steht hinter dem vorangestellten Briefing.
Die übrigen Felder von `tool_input` bleiben erhalten.
Fehlender Skill: `permissionDecision: "deny"` mit `permissionDecisionReason`.
Kein passender Agent oder keine Deklaration: Exit 0, leeres stdout.

## Codex: SubagentStart

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "agent_type": "my_agent", "agent_id": "...", "turn_id": "..."
}
```

Erfolg: `hookSpecificOutput.hookEventName: "SubagentStart"` und
`additionalContext` mit vollständigem Briefing.
Fehlender Skill: stattdessen eine Anweisung, die Aufgabe nicht zu bearbeiten und
zum Auftraggeber mit dem Fehler zurückzukehren; zusätzlich `systemMessage`.
Auch bereits auflösbare Skills bleiben bei einem Fehler draußen.

Codex ignoriert `continue: false` trotz Kompatibilitätsparser. Deshalb gibt es
keine echte Spawn-Sperre und keinen ehrlichen Ersatz durch ein Teil-Briefing.
`additionalContextLimit: 0` in `hooks/hooks.json` verhindert, dass Codex lange
Ausgaben auf Disk auslagert und nur eine Vorschau in den Modellkontext gibt
(der Standard liegt ungefähr bei 2500 Tokens).

## Gemeinsame Ausgabe

Erfolg schreibt eine Audit-Zeile ausschließlich für den Menschen in `systemMessage`:
`briefing: my-agent ← skill-a, skill-b (N kB)`; Warnungen folgen als weitere Zeilen.
Über 64 KiB Skill-Text wird gewarnt, aber nicht verweigert.
Jeder Skill wird ohne Frontmatter so eingebettet:

```xml
<skill name="skill-a" dir="/abs/path/to/skill-a">
…SKILL.md-Inhalt…
</skill>
```

`dir` ist absolut; nur der Haupttext wird vorgeladen. Weitere Dateien bleiben
progressiv zugänglich. Ein Skill lädt keine weiteren `briefing.skills` rekursiv.

## SessionStart: beide Harnesses

```json
{
  "hook_event_name": "SessionStart", "cwd": "/abs/path", "session_id": "...",
  "source": "startup", "transcript_path": "/home/u/.codex/sessions/..."
}
```

Nur ein top-level `systemMessage` für nicht funktionierende Deklarationen, sonst
keine Ausgabe. Niemals `hookSpecificOutput`, das hier Modellkontext erzeugen würde.
`transcript_path` unterscheidet `/.codex/` beziehungsweise `$CODEX_HOME` und
`/.claude/`; ohne eindeutiges Signal werden beide geprüft.
`startup`, `resume` und fehlendes `source` werden geprüft; andere Quellen wie
Compaction bleiben still. Überlange, aber funktionierende Briefings werden hier
nicht erneut gemeldet. Der Doctor zeigt dagegen Fehler und Budgetwarnungen.

## Gemeinsame Hook-Datei

`hooks/hooks.json` bleibt gemeinsam: Claude Code akzeptiert den Codex-Block;
Codex löst auch `${CLAUDE_PLUGIN_ROOT}` auf. Die Windows-Aufrufweise ist
exec-form (`command` mit `args: []`); der `.exe`-Launcher läuft dort statt des
extensionlosen Skripts. Hintergrund und native Tests: `winlaunch/README.md`.

`hooks/briefing-marketplace-notice` ist ein separater SessionStart-Hinweis mit
eigener Zustandsspeicherung; die Lesend-/Seiteneffektfrei-Garantie des Preload-Hooks
ist keine Behauptung über diesen Notice-Hook.
