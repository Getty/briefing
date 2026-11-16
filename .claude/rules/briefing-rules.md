<!-- ack: shape=project manager=none board=karr committer=release-manager outside_input=on headless=off -->
# briefing: Projektregeln

## Zuständigkeiten

| Arbeit | Agent |
|---|---|
| Code und Historie lesen, Zusammenhänge finden | `briefing-scout` |
| `hooks/`, `bin/`, `winlaunch/` ohne Tests; Produkt-Skill `skills/`, Beispiele, Projekt-Skills | `briefing-worker` |
| `tests/`, `winlaunch/test_winlaunch.py` | `briefing-test-writer` |
| Fertige Änderungen prüfen und Tests selbst ausführen | `briefing-reviewer` |
| Freigegebene Commits, `Changes`, Release-Prüfung | `briefing-release-manager` |

Verhaltensrelevant sind diese Code-/Skill-Pfade sowie Hook-Konfiguration und
Plugin-Manifeste: Änderungen daran gehen an den Worker, auch wenn es JSON ist.
Die Hauptsitzung übernimmt Koordination, reine Prosa-Dokumentation und
Team-Konfiguration.

## Prüfen und Committen

`python3 -m unittest discover tests -v` prüft die Hook-Verträge ohne echte Konten.
Bei Änderungen an Auflösung oder Agenten zusätzlich beide Doctor-Versionen prüfen:
`python3 hooks/briefing-preload doctor --cwd . --harness both` und `briefing-doctor`.
Der Release-Manager übernimmt als einzige Rolle genehmigte Commits und den Abschluss
zugehöriger Karten; der Arbeitsbaum anderer Sitzungen bleibt unberührt.

## Board

Das bestehende Board liegt in `refs/karr/*`; `karr list --compact` zeigt offene Arbeit.
Karr-Mutationen synchronisieren mit `origin`: vor dem ersten Schreiben die Freigabe
für diesen Board-Austausch klären. Das Anlegen des Teams allein erteilt sie nicht.

## Mit superpowers

Umsetzung im bestehenden Checkout; eine Isolation nur nach ausdrücklicher Wahl.
Code-Aufträge laufen über Worker/Test-Writer, dann prüft der Reviewer den
uncommitteten Diff; ein genehmigter Commit folgt durch den Release-Manager.
Brainstorming und Planung bleiben in der Hauptsitzung, weil sie den Nutzer brauchen.

## Projektspezifische Fallen

- Checkout und installiertes briefing können verschiedene Hook-Verträge haben:
  vor Hook-Arbeit `briefing-core` und dessen passende Referenz lesen.
- Die Windows-`.exe` sind Python-Launcher, keine Standalone-Binaries; native Tests
  stehen in `winlaunch/README.md`, Linux-unittest beweist keinen Windows-Start.
- `hooks/briefing-preload` bleibt seiteneffektfrei; der separate Marketplace-Notice
  besitzt dagegen Zustand. Diese beiden Verträge nicht vermischen.
- `Changes` folgt dem CPAN-Format, obwohl dieses Projekt keine Perl-Distribution
  ist; Release-Konventionen gehören ausschließlich zum Release-Manager.
