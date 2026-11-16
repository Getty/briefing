# Perl direction

On 2026-11-16 the **Perl port was approved**: **App::Briefing** is the reusable
library, **App-Briefing** the distribution and **briefing** the CLI. The same Perl
core is the basis of the binaries. Delivery details remain open, not the language
choice; this decision does not claim the distribution is implemented or published.

## One core, several entry points

- The library provides reusable briefing logic, not merely a wrapper around a CLI process.
- The `briefing` CLI uses that same library, including diagnostics.
- CPAN is the optional source-installation route for Perl users. With `local::lib`,
  the library and command are found through `PERL5LIB` and the local `bin` entry in `PATH`.
- Plugin users should not need to install Perl or CPAN separately. Platform packages
  include the runtime; CPAN and binaries distribute the same core, not separate implementations.
- Claude Code and Codex retain thin, appropriate adapters. Events, declarations,
  search locations and failure policies are not normalized away.
- Hermes is an additional integration target, not existing support. Its adapter
  and the mapping from delegated agents to declarations still need verification.
- Plugins must invoke the core matching their own version. A different `briefing`
  found first on `PATH` is not a safe substitute for the bundled version.
  Using an external installation would require explicit configuration.

## Work for the port and delivery

The [packaging probe](../prototypes/perl-packaging/README.md) produced native
builds on Linux, macOS and Windows x86_64. It also established open work:

1. Windows paths containing umlauts or CJK fail in the unpacked prototype too.
   The new core needs verified Unicode-capable file operations.
2. The self-extracting PAR binary adds startup cost and writes a cache. Whether
   delivery uses that form or a package extracted during installation remains open.
3. Operation without a separately installed runtime was proved only in isolated
   Linux. Native macOS/Windows isolation, ARM and the final platform matrix remain open.
4. Existing behavior tests should verify the port; real harness contracts remain
   the reference. The probe is not a substitute for those tests.
5. Check the namespace and PAUSE permissions before publishing to CPAN. Choosing
   the name does not reserve it; uploads and releases require separate authorization.

Integrating the team setup and probe does not turn the production Python hook into
a Perl implementation. It also includes the existing upstream `SubagentStart` fix.
The next implementation step is the approved Perl port against the existing
behavior tests; Windows file access and packaging are concrete work items, not
another language-selection exercise.
