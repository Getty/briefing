# Hook-Vertrag dieses Checkouts

Gilt für `hooks/briefing-preload`, nicht ungeprüft für installierte Plugin-Versionen.
`main()` routet `SubagentStart` zum gemeinsamen Briefing, `SessionStart` zum
Pre-flight und ansonsten nur `tool_name == "Agent"` zum Claude-Code-Guard.
Als `briefing-doctor` oder mit erstem Argument `doctor` läuft dieselbe Auflösung als CLI.
`bin/briefing-doctor` ist der ausführbare Wrapper dafür.

## Claude Code: PreToolUse-Guard

```json
{
  "hook_event_name": "PreToolUse", "cwd": "/abs/path", "tool_name": "Agent",
  "permission_mode": "auto",
  "tool_input": { "subagent_type": "my-agent", "prompt": "...", "model": "sonnet" }
}
```

Fehlender deklarierter Skill: `hookSpecificOutput` mit
`hookEventName: "PreToolUse"`, `permissionDecision: "deny"` und
`permissionDecisionReason`. Sonst Exit 0, leeres stdout — auch bei Erfolg.
Der Guard verändert den Aufruf nie und gibt niemals `updatedInput` aus.
Auto-mode prüft den Aufruf vor den Hooks und kann nachträgliche Änderungen
verweigern: `a hook changed this call's input after auto mode reviewed it`.
Das frühere Prompt-Rewrite bis briefing 0.5.x deshalb nicht wieder einführen.

## SubagentStart: beide Harnesses

Claude Code, beobachteter Payload in 2.1.318 (ohne `permission_mode`):

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "session_id": "...", "transcript_path": "/home/u/.claude/projects/.../x.jsonl",
  "prompt_id": "...", "agent_id": "...", "agent_type": "my-agent"
}
```

Codex:

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "agent_type": "my_agent", "agent_id": "...", "turn_id": "..."
}
```

`spawn_harness` unterscheidet zuerst über `transcript_path` (`/.claude/` versus
`/.codex/` beziehungsweise `$CODEX_HOME`), dann über das Vorhandensein von
Codex' `turn_id`. Ohne eindeutiges Signal gewinnt ein gefundener Claude-Code-Agent,
sonst wird Codex verwendet. `agent_type` ist der deklarierte Agentenname, nicht
zwingend der Dateiname. Kein passender Agent oder keine Deklaration bedeutet
Exit 0 und leeres stdout; Built-ins ohne Agentendatei sind ebenfalls No-op.

Erfolg: `hookSpecificOutput.hookEventName: "SubagentStart"` und
`additionalContext` mit vollständigem Briefing.
Fehlender Skill: stattdessen eine Anweisung, die Aufgabe nicht zu bearbeiten und
zum Auftraggeber mit dem Fehler zurückzukehren; zusätzlich `systemMessage`.
Auch bereits auflösbare Skills bleiben bei einem Fehler draußen. Das gilt auch,
wenn unter Claude Code ein Skill zwischen Guard und `SubagentStart` verschwindet.

Bei `SubagentStart` kann keiner der Harnesses den Spawn sperren. Codex ignoriert
`continue: false` trotz Kompatibilitätsparser; ein Teil-Briefing ist kein Ersatz.
`additionalContextLimit: 0` in `hooks/hooks.json` verhindert, dass Codex lange
Ausgaben auf Disk auslagert und nur eine Vorschau in den Modellkontext gibt
(der Standard liegt ungefähr bei 2500 Tokens).

**Legacyharness-Falle:** Claude Code muss Kontext aus `SubagentStart` übernehmen
können; geprüft wurde 2.1.318, nicht die frühestmögliche Version. Alte Versionen
ohne diese Unterstützung starten den Agenten still unbriefed: ein erfolgreicher
Guard injiziert nichts und ist kein Fallback.

## Gemeinsame Ausgabe

`SubagentStart` schreibt bei Erfolg eine Audit-Zeile für den Menschen in `systemMessage`:
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

`hooks/hooks.json` bleibt gemeinsam: `SubagentStart` bedient beide Harnesses,
`PreToolUse` nur den Claude-Code-Guard. Codex löst auch `${CLAUDE_PLUGIN_ROOT}` auf.
Die Windows-Aufrufweise ist
exec-form (`command` mit `args: []`); der `.exe`-Launcher läuft dort statt des
extensionlosen Skripts. Hintergrund und native Tests: `winlaunch/README.md`.

`hooks/briefing-marketplace-notice` ist ein separater SessionStart-Hinweis mit
eigener Zustandsspeicherung; die Lesend-/Seiteneffektfrei-Garantie des Preload-Hooks
ist keine Behauptung über diesen Notice-Hook.
