# Wegwerf-Prototyp für Perl-Packaging

Frage: Taugt die vorhandene native Perl/pp-Strecke für einen kleinen JSON-Hook
ohne separat installierte Laufzeit?

**Kein Produktcode, keine Distribution, kein festgelegter Modulname. Das eigene
Protokoll ist NICHT mit den echten Harness-Protokollen kompatibel.** Keine
Agenten-/Skill-Auflösung, Frontmatter-Verarbeitung oder Hook-Integration;
gelesen werden ausschließlich ausdrücklich übergebene Fixture-Dateien. Das
Artefakt enthält eine Perl-Laufzeit, startet aber weder das Python des Testhosts
noch ein separat installiertes Perl.

## Einzeiler

Vom Repository-Root aus. Buildhost: Perl mit PAR::Packer 1.064 und Path::Tiny
(lokal 0.150); Python 3.8+ nur für die Build-/Testhelfer. JSON::PP ist ausdrücklich
Teil des Experiments; Path::Tiny folgt der Perl-Datei-I/O-Hausregel. Das
skilletor-Buildvorbild liefert die pp-Strecke samt PAR_VERBATIM=1. Keine
Modul-Ausdünnung oder Größenoptimierung.

- Nativer Build pro OS: `python prototypes/perl-packaging/build.py`
- Linux/macOS: `python prototypes/perl-packaging/smoke.py prototypes/perl-packaging/build/probe --expect-arch x86_64 --report prototypes/perl-packaging/build/smoke.json`
- Windows: `python prototypes/perl-packaging/smoke.py prototypes/perl-packaging/build/probe.exe --expect-arch x86_64 --report prototypes/perl-packaging/build/smoke.json`
- Metadaten des Artefakts: `prototypes/perl-packaging/build/probe --version` (Windows: `.exe` anhängen).

Lokal auf Linux heißt der Python-Aufruf `python3`. `build.py --perl /absoluter/perl`
wählt den Buildinterpreter. Der Helfer protokolliert sein portables pp-Kommando:
`perl -Mpp -e 'pp->go()' -- -o AUSGABE probe.pl`, mit PAR_VERBATIM=1 in der
Umgebung. Der Helfer installiert keine globalen Abhängigkeiten.

Anfrage: `{"skills":[{"name":"beispiel","path":"/absoluter/Fixture SKILL.md"}]}`

Erfolg: `{"ok":true,"skills":[{"name":"beispiel","body":"vollständige UTF-8-Datei"}]}`.
Fehler: `{"ok":false,"error":{"code":"missing_skill","name":"beispiel"}}`.
**Kein Fehler enthält Skill-Inhalte**, auch wenn vorherige Dateien schon gelesen
wurden. Kaputtes JSON ergibt `invalid_json`, eine ungültige Anfrage
`invalid_request`, eine nicht lesbare Datei `unreadable_skill`.
Behandelte Anfragen liefern Exit 0 und genau ein UTF-8-JSON-Objekt. Das sind
Prototyp-Semantiken, keine Aussage über das Verhalten echter Hooks.

## Prüfungen und Messgrenzen

Der Python-Testhost erzeugt Unicode-Inhalte und Pfade mit Leerzeichen, Umlauten
und Zeichen außerhalb Windows-1252 (`Pfad ä 技能`). Er kopiert das Artefakt in
einen Pfad mit Leerzeichen/Umlaut und startet es über einen absoluten Pfad mit
frischer Minimalumgebung und leerem PATH. Geprüft werden striktes JSON auf
stdout, leeres stderr, vollständige Inhalte, vorhandene plus fehlende Skills
und ungültige Eingaben. Der Anwendungscode startet kein externes Perl/Python.

Jeder Lauf bekommt ein neues Arbeitsverzeichnis unter `.work/`.
**PAR_GLOBAL_TEMP** bestimmt den tatsächlichen **PAR_TEMP**-Cache: pp setzt
ein übergebenes PAR_TEMP zurück; PAR_TEMP allein isoliert daher keinen Cache.
Der Runner prüft, dass die gewählten Verzeichnisse tatsächlich gefüllt werden.
Gemessen werden Erststart, fünf Wiederholungen mit demselben Cache und ein
weiterer Start mit einem zweiten leeren Cache. Ein leerer PAR-Cache ist kein
leerer OS-Seitencache. Das sind lokale Wandzeiten, kein belastbarer Benchmark.

Im JSON sind `functional_status` und `separate_interpreter_absence.status`
getrennt. Letzteres bleibt beim normalen Host-Runner **NOT_PROVEN**: Ein leerer
PATH versteckt weder absolute Interpreterpfade noch System-Perl-Bibliotheken
oder macOS-System-Perl. Ein grüner Smoke-Test beweist deshalb keine Umgebung
ohne externe Laufzeit. Die unten separat dokumentierte Linux-Isolation stammt
aus der Hauptsitzung; dieser Runner erzeugt/startet keine Container.

Berichtet werden Host-OS/Architektur/libc, Architektur/Version des eingebetteten
Perl, Artefakt- und Cachegröße sowie Systembibliotheken (Linux ldd, macOS otool,
Windows objdump, sofern verfügbar). Diese Werkzeuge laufen auf dem Testhost mit
dessen normalem PATH außerhalb der Zeitmessungen. Statische Bibliotheksanalyse
ist kein vollständiger Laufzeit-Trace. pp kann optionale, auf dem Buildhost
vorhandene Module einpacken; die Größe ist keine Reproduzierbarkeitsgarantie.

## Zielmatrix mit getrennten Statusfeldern

| Ziel | Nativer CI-Runner | Tatsächlich getestet | Build / Funktions-Smoke | Ohne separates Perl |
|---|---|---|---|---|
| Linux | ubuntu-24.04, x86_64 | CI: glibc 2.39; lokal: glibc 2.41 | PASS / PASS | Separate lokale Isolation PASS, Details unten |
| macOS | macos-15-intel, x86_64 | nativer Intel-Runner, Darwin 24.6 | PASS / PASS | NICHT BELEGT: Host-Test mit leerem PATH |
| Windows | windows-2022, x86_64 / Strawberry Perl | nativer Windows-Server-2022-Runner | Build PASS; Smoke FAIL bei Unicode-Dateipfad | NICHT BELEGT |

[Zweiter nativer Lauf](https://github.com/Getty/briefing/actions/runs/43799294737):
Linux und macOS bestehen alle Smoke-Prüfungen; Windows baut und startet die EXE,
meldet aber eine vorhandene Datei unter `Pfad ä 技能` als `missing_skill`.
Die ergänzende [native Gegenprobe](https://github.com/Getty/briefing/actions/runs/43800137154)
vergleicht ASCII-, Umlaut- und CJK-Pfade mit unverändertem Code:

| Windows-Dateipfad | Ungepacktes Skript | PAR-Binary |
|---|---|---|
| ASCII | PASS | PASS |
| `Grüße` | FAIL: `missing_skill` | FAIL: `missing_skill` |
| `技能` | FAIL: `missing_skill` | FAIL: `missing_skill` |

Alle sechs Prozesse starten und liefern reines JSON mit Exit 0. Auf ASCII-Pfaden
wird derselbe Unicode-Dateiinhalt korrekt gelesen. Die Dateien existieren nach
Anlage durch den Testhost; der Prototyp scheitert an seiner `-f`-Prüfung vor
`Path::Tiny->slurp_utf8`. Der Fehler ist somit bereits im ungepackten Windows-
Dateizugriff vorhanden, nicht erst nach PAR-Verpackung. Eine Portierung braucht
hier eine ausdrücklich Unicode-fähige Lösung; dieser Versuch repariert sie nicht.
Die Diagnose ersetzt den strengen Smoke-Test nicht: dessen Windows-FAIL bleibt
auch im letzten CI-Lauf bestehen, während Linux und macOS erneut PASS melden.

Der erste Windows-Versuch scheiterte noch vor dem Build: Git Bash stellte sein
eigenes `/usr/bin/perl` vor Strawberry Perl. Der korrigierte Workflow verwendet
unter Windows PowerShell, unter Linux/macOS weiterhin Bash.

Keine Aussage über ARM, Cross-Compilation oder ältere Systembibliotheken.
Der Workflow prüft RUNNER_ARCH; der Runner prüft platform.machine() und berichtet
die eingebettete Perl-Architektur, statt das Runner-Label als Beweis zu nehmen.

CI-Messwerte des zweiten Laufs, jeweils auf unterschiedlichen Hosts:

| Ziel | Binary-Bytes | Erster leerer PAR-Cache | Median fünf warmer Starts |
|---|---:|---:|---:|
| Linux | 7.516.032 | 125,728 ms | 80,846 ms |
| macOS | 6.950.067 | 848,640 ms | 221,138 ms |
| Windows | 12.915.092 | nicht ausgewertet: Funktionsfehler | nicht ausgewertet |

Das sind keine direkt vergleichbaren OS-Benchmarks. JSON-Prüfberichte liegen im
CI-Lauf als kurzlebige Artefakte; es wurden keine Binaries veröffentlicht.

Lokaler Stand: Perl 5.40.1, pp 1.064, Artefakt 9.758.529 Byte (etwa 9,31 MiB),
208 Cachedateien / 16.197.654 Byte. Letzter Lauf mit erweitertem Unicode-Pfad:
Erststart 632,066 ms, fünf Wiederholungen 272,364–385,379 ms
(Median 286,473 ms), zweiter leerer Cache 767,009 ms. Build 2,676 Sekunden.
ldd zeigt eingebettetes libperl.so.5.40 und externe libc, libm, libcrypt, libz
sowie den ELF-Loader über Artefakt und extrahierte Bibliotheken hinweg.
**Kein statisches Binary.** Lokale Rohdaten stehen ignoriert unter
`build/build.json` und `build/smoke-linux.json`.

Zusätzlicher kleiner Vergleich mit identischem Ein-Skill-Minimalrequest, gleicher
Minimalumgebung und je einem ungemessenen Vorlauf: fünf abwechselnde Starts von
`/usr/bin/perl prototypes/perl-packaging/probe.pl` und dem warmen Artefakt ergaben
Mediane von 70,036 ms gegenüber 293,180 ms (Differenz 223,144 ms). Rohdaten samt
exakten Kommandos, Eingabe und Umgebung: `build/baseline-linux.json`. Das ordnet
die möglichen Packaging-Kosten ein, ist aber kein allgemeiner Benchmark.

### Separater Linux-Isolationsbeleg der Hauptsitzung

Die Hauptsitzung prüfte dasselbe Artefakt mit SHA256
`9b926bc29ccd47cddfd3cb41532e32b695dd9bdbd849f4121db189e9aa6a46c4`
in einem lokalen debian:trixie-slim-Derivat (Linux x86_64, glibc 2.41).
Laut gelesenem Dockerfile/Bericht wurden Perl-Programme, perl-base-Dateien und
/usr/share/perl5 entfernt; Python und Node fehlen ebenfalls. Netzwerk aus,
Root-Dateisystem schreibgeschützt, PAR_GLOBAL_TEMP im tmpfs. Unicode-Dateipfad
außerhalb Windows-1252, vollständiger Unicode-Inhalt, fehlender Skill ohne
Teilantwort und ungültiges JSON bestanden. Der Binary-Hash wurde hier mit dem
geprüften Artefakt abgeglichen; der Containerlauf selbst wurde nicht vom Worker
wiederholt. Beleg der Hauptsitzung:
`/tmp/briefing-no-runtime.CDFih0/linux-no-runtime.json` und benachbartes Dockerfile
(temporäre lokale Dateien, nicht Bestandteil dieses Prototyps).
Container-Wandzeiten enthalten den Containerstart und sind **keine**
Binary-Startzeiten. Dieser Nachweis gilt für genau dieses Artefakt und diese
Linux-Umgebung, nicht für alle Distributionen oder andere Betriebssysteme.

Der Workflow läuft nach ausdrücklicher Freigabe manuell oder bei einem Push
auf `spike/perl-packaging`, mit `contents: read`, nativen Builds und joblokalen
CPAN-Abhängigkeiten. Er sichert ausschließlich JSON-Prüfberichte für sieben Tage;
keine Binaries, Releases oder Änderungen an `main`. Die oben verlinkten nativen
CI-Läufe wurden tatsächlich ausgeführt. Die Build-/Testhelfer selbst pushen oder
starten keine CI.

Fazit: Der native Build funktioniert auf allen drei getesteten x86_64-Plattformen.
Linux und macOS bestehen den Funktions-Smoke; unter Windows blockieren bereits
Umlaut-Dateipfade die Eignung dieses unveränderten Prototyps, sowohl ungepackt als
auch paketiert. Nur für die separate lokale Linux-Umgebung ist zusätzlich das
Fehlen externer Interpreter nachgewiesen. ARM, eine native Umgebung ohne externes
Perl auf macOS/Windows und echte Harness-Integration bleiben ungeprüft.
Für einen winzigen Hook sind Archiv-/Startkosten und die Cache-Extraktion relevant:
die Anwendung liest nur, der PAR-Launcher schreibt beim Erststart dagegen Dateien.
Das ist noch keine Freigabe für eine vollständig portable, strikt lesende Hook-Auslieferung.
Der Versuch endet bei diesen Befunden; Modulname und produktive Umsetzung bleiben offen.
