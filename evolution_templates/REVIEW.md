# Independent template-family review

Nine independent tests pass. The two accepted originals are the exact pinned
Blocker and Feint source files. Default exports reproduce their original bytes
and SHA256 values. The mutable sets contain **12 Blocker genes and 10 Feint
genes**: Feint uses its own HOP_RISK override, while Blocker uses the inherited
core value. The shadowed Feint core threshold is excluded.

The final prospective `BlockerBot.LEADER_BUMP` cap is [0, 0.2], with the original
default 0.15 unchanged. A focused final check verified the cap, default and exact
original default-export hash after that bound adjustment. The final reviewed
space source SHA256 is
`bce6dd1fa5950a8752182ce4c70e17ea10d74245a7fe650cc735b3483b2ae041`.

An independent AST reader masks only the approved class-qualified literal
spans. Original and exported bytes then agree everywhere else, including
comments, imports, loops, architecture switches, budgets, seed initialization
and the direct `player.act(state)` entry point. Inspection reconstructs the
candidate exactly from its parsed numbers; semantic equivalence alone does
not authorize changed comments, line endings or alternate expression syntax.

Tests reject inactive-class changes, duplicate classes/assignments, extra or
missing genes, wrong classes, Boolean/nonfinite/huge-integer values, expression
or arbitrary-code values and foreign-family genotypes. Candidate inspection
does not execute injected code. Every public source operation rejects changed
original source bytes. Bounds/default metadata copies cannot relax the fixed
internal contract. Mutation and crossover are deterministic, bounded and
family-specific; mutations change one through three approved values.

The real templates are ASCII with LF line endings. Tests preserve those exact
bytes and reject CRLF or Unicode comment rewrites. A separate synthetic parser
fixture places non-ASCII text before a literal on the same line and uses CRLF;
replacement changes only the correct UTF-8 byte span and preserves every
comment, Unicode character and line ending. This fixture does not authorize an
alternate source template.

Thirty-two short synthetic public-prefix callbacks exercised default and small
mutated exports in memory. All decisions were legal and inputs unchanged. The
broad exception-catching `__call__` wrapper was made unusable, and raw policy
decisions were checked before the existing legal-action STAY normalization.
No candidate file, full strength match, GPU probe, current study outcome,
runtime qualification, primary credit or BMCTS audit was produced.

These are source-family and bounded mechanics checks. Numeric bounds do not
establish strategic quality, broad correctness, runtime qualification or a
better bot. New exported source hashes still require their own applicable
qualification and fresh complete-match evidence. The active study's runtime
and original source files remain unchanged.

Validation: `python -m unittest evolution_templates.test_independent -v`
passed all nine tests in 1.704 seconds, with no skips.
