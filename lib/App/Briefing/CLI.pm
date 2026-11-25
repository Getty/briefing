package App::Briefing::CLI;
# ABSTRACT: Retired stub, see App::Briefing

use strict;
use warnings;

our $VERSION = '0.007001';

our $NOTICE = q{briefing is retired: Claude Code now preloads agent skills natively. Replace the `briefing:` block in an agent's frontmatter by a top-level `skills:` list, then run `/plugin uninstall briefing`. How: https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents};

sub run {
  print STDERR "$NOTICE\n";
  return 1;
}

=method run

    exit App::Briefing::CLI->run(\@ARGV);

Prints the retirement notice to standard error and returns 1. A C<briefing>
command left over from an earlier release calls this and so says what to do.

=cut

1;

=description

A stub: briefing is retired. L<App::Briefing> names the replacement.

=seealso

=over

=item * L<App::Briefing>

=item * L<https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents>

=back

=cut
