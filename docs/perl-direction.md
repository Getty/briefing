# Perl-Zielrichtung

Am 2026-11-16 wurde der **Perl-Port beschlossen**: **App::Briefing** wird die
wiederverwendbare Library, **App-Briefing** die Distribution und **briefing** das CLI.
Derselbe Perl-Kern ist die Basis der Binaries. Offen sind Auslieferungsdetails,
nicht mehr die Sprachwahl; implementiert oder veröffentlicht ist die Distribution
mit dieser Zielentscheidung noch nicht.

## Ein Kern, mehrere Zugänge

- Die Library stellt die wiederverwendbare Briefing-Logik bereit; sie ist nicht
  nur eine Verpackung um einen schwer wiederverwendbaren CLI-Hauptprozess.
- Das CLI `briefing` verwendet dieselbe Library, einschließlich der Diagnose.
- CPAN ist der optionale Quell-Installationsweg für Perl-Nutzende. Bei einer
  Installation mit `local::lib` werden Library und CLI über `PERL5LIB` und den
  lokalen `bin`-Eintrag im `PATH` auffindbar.
- Plugin-Nutzende sollen weder Perl noch CPAN zusätzlich installieren müssen.
  Plattformpakete enthalten die benötigte Runtime; CPAN und Binärpaket sind
  Auslieferungswege desselben Kerns, keine getrennten Implementierungen.
- Claude Code und Codex behalten dünne, passende Adapter. Die Unterschiede bei
  Events, Deklarationen, Suchorten und Fehlerpolitik werden nicht wegnormalisiert.
- Hermes ist ein zusätzliches Integrationsziel, noch keine vorhandene Unterstützung.
  Sein Adapter und die Zuordnung delegierter Agenten zu Deklarationen sind zu prüfen.
- Plugins müssen den zu ihrer Version gehörenden Kern eindeutig aufrufen.
  Ein zufällig zuerst im `PATH` gefundenes anderes `briefing` ist kein sicherer
  Ersatz für die mitgelieferte Version. Eine externe Installation wäre explizit zu konfigurieren.

## Umsetzungsaufgaben für Port und Auslieferung

Die [Packaging-Probe](../prototypes/perl-packaging/README.md) hat native Builds
auf Linux, macOS und Windows x86_64 geliefert. Sie hat auch offene Punkte gezeigt:

1. Windows-Dateipfade mit Umlaut oder CJK scheitern bereits im ungepackten
   Prototyp. Der neue Kern benötigt nachgewiesen Unicode-fähige Dateioperationen.
2. Das selbstentpackende PAR-Binary verursacht Startkosten und schreibt einen
   Cache. Ob es die Auslieferungsform wird oder ein beim Installieren entpacktes
   Paket besser passt, ist noch nicht entschieden.
3. Der Lauf ohne separat installierte Runtime wurde nur auf Linux isoliert
   bewiesen. Native macOS-/Windows-Isolation, ARM und die endgültige
   System-/Architekturmatrix stehen noch aus.
4. Die bestehenden Verhaltenstests sollen den Port prüfen; die realen
   Harness-Verträge bleiben die Referenz. Die Probe ist kein Ersatz dafür.
5. Vor einer CPAN-Veröffentlichung Namespace und PAUSE-Berechtigungen prüfen.
   Die Namenswahl behauptet keine Reservierung; Upload und Release benötigen
   ihre eigene Freigabe.

Die Integration von Team-Setup und Prototyp ändert den produktiven Python-Hook
nicht in eine Perl-Implementierung. Sie übernimmt zusätzlich den bereits vorhandenen
Upstream-Fix für `SubagentStart`. Als nächster Umsetzungsschritt folgt der
beschlossene Perl-Port gegen die bestehenden Verhaltenstests; Windows-Dateizugriff
und Packaging werden dabei als konkrete Aufgaben gelöst, nicht als neue Sprachwahl.
