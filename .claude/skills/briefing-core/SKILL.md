---
name: briefing-core
description: Use when working in briefing — Hooks, Skill-Auflösung, Doctor, SessionStart, Tests oder Windows-Launcher dieses Plugins ändern oder prüfen.
---

# briefing entwickeln

`briefing` lädt deklarierte Skills beim Subagent-Start vollständig vor.
Produkt-Skill: `skills/briefing/SKILL.md`; dieser Skill betrifft die Entwicklung,
nicht die Nutzung des Plugins. Produktüberblick: `README.md` im Repository-Root.

## Verbindliche Grenzen

- Gemeinsame und Claude-Code-Pfade bleiben Python 3.8+, ausschließlich Standardbibliothek.
  Versionsabhängige Imports bleiben funktionslokal; der Hook läuft bei jedem Spawn.
- `hooks/briefing-preload` bleibt lesend, idempotent und ohne Seiteneffekte.
  Ungültige Eingaben enden sauber mit Exit 0; nur ein tatsächlich fehlender,
  ausdrücklich deklarierter Skill darf einen Claude-Code-Spawn verweigern.
  Der Doctor ist eine CLI: fehlgeschlagene Prüfungen liefern Exit 1.
- Eine Deklaration wird durch `Briefing` einmal aufgelöst; Spawn, Pre-flight
  und Doctor verwenden dasselbe Ergebnis, keine getrennten Resolver.
- Beide Harnesses injizieren bei `SubagentStart` über `additionalContext`.
  Claude Codes `PreToolUse` ist nur Guard: `deny` oder leer, niemals `updatedInput`
  oder Prompt-Rewrite; sonst kann auto-mode den veränderten Aufruf verweigern.
- Fehlende Skills ergeben niemals ein Teil-Briefing. Bei `SubagentStart` kann
  keiner der Harnesses den Spawn sperren: nur Abbruchanweisung, auch wenn ein
  Skill erst nach dem Claude-Code-Guard verschwindet.
- Nur `SKILL.md` wird injiziert, Frontmatter entfernt. Das absolute `dir` am
  `<skill>`-Element macht `references/` und `scripts/` auffindbar; diese nicht mitladen.
- Ein `hooks/hooks.json` bedient beide Harnesses. Codex benötigt
  `additionalContextLimit: 0`, sonst landet langer Kontext als Vorschau statt Volltext.
- Die Auflösung folgt dem jeweiligen Harness. Claude-Code-Plugin-Caches sind
  kein Installationsindex; ausgeschaltete Plugins liefern keine Skills.
- Hauptsitzungen, beliebige Tool-Prompts und spätere Skill-Aufrufe bleiben
  außerhalb dieses Plugins. Welche Skills ein Agent deklariert, entscheidet das Projekt.

## Vor Änderungen gezielt lesen

| Änderung | Referenz |
|---|---|
| Events, JSON-Ausgaben, Fehlerpolitik, Pre-flight | [Hook-Vertrag](references/hook-contract.md) |
| Agenten finden, Deklarationen parsen, Skills oder Plugins auflösen | [Auflösung](references/resolution.md) |
| Harness-Integration beweisen oder „briefing tut nichts“ untersuchen | [Live-Verifikation](references/live-verification.md) |

Den wirksamen Vertrag an `hooks/hooks.json` und `hooks/briefing-preload` der
wirklich geladenen Version prüfen: Checkout, installierte Cache-Kopie und
Harness-Version können auseinanderliegen. Legacyharness-Falle: [Hook-Vertrag](references/hook-contract.md).

## Prüfungen

Im Repository-Root:

```sh
python3 -m py_compile hooks/briefing-preload hooks/briefing-marketplace-notice
sh -n bin/briefing-doctor
python3 -m unittest discover tests -v
python3 hooks/briefing-preload doctor --cwd . --harness both
```

Die unittest-Suite startet Hooks als Subprozesse mit isoliertem `HOME` und `cwd`.
`tests/test_briefing_codex.py` erzwingt den Python-3.10-Fallback durch ein
`tomllib.py`, das beim Import fehlschlägt: ein Lauf nur mit echtem `tomllib`
beweist diesen Pfad nicht. CI-Matrix: `.github/workflows/test.yml`.

Der lokale Doctor prüft den Checkout, `briefing-doctor` auf dem Plugin-PATH die
installierte Version; beide können auseinanderliegen. Der Doctor und simulierte
Hook-Payloads beweisen die Auflösung, nicht die tatsächliche Einbindung im Harness.

## Windows

`bin/briefing-doctor` ist ein Shell-Wrapper, kein Symlink: POSIX startet damit
Python; Windows verwendet die `# winlaunch:`-Direktive über die benachbarte `.exe`.
Die `.exe`-Dateien
unter `hooks/` und `bin/` sind Launcher und benötigen weiterhin Python; sie sind
keine eigenständigen Pakete mit eingebettetem Interpreter.
Bei Launcher-/Hook-Aufrufänderungen `winlaunch/README.md`, den Header von
`winlaunch/winlaunch.c` und `.cicd/python+3.12+test.winlaunch.sh` lesen.
Die gemeinsame Launcher-Quelle liegt laut README im windows-developer-Hub.
Linux-unittest und reproduzierbarer Build ersetzen keinen nativen Windows-Lauf.
Jeder Bericht nennt die tatsächlich geprüften Plattformen und ausgelassene Tests.
