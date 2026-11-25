package App::Briefing;
# ABSTRACT: Retired: Claude Code preloads agent skills natively

use strict;
use warnings;

our $VERSION = '0.007000';

1;

=description

briefing is retired. It put the skills an agent declared into a subagent's
context at spawn time. Claude Code does that itself now: a top-level C<skills:>
list in the agent's frontmatter preloads each named skill, C<plugin:skill> names
included, when the subagent starts. See
L<https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents>.

Before:

    ---
    name: my-agent
    briefing:
      skills:
        - perl-core
    ---

After:

    ---
    name: my-agent
    skills:
      - perl-core
    ---

Then remove the plugin with C</plugin uninstall briefing>.

This last release of the distribution ships its modules as empty stubs, so an
upgrade replaces the earlier library code.

=seealso

=over

=item * L<https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents>

=back

=cut
